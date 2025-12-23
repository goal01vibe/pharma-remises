"""
Service de memoire de matching persistante avec groupes d'equivalence transitifs.

Si A match B et B match C, alors A, B, C sont dans le meme groupe d'equivalence.
Permet un matching instantane pour les futurs rapprochements.
"""
import logging
from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import MatchingMemory, BdpmEquivalence

logger = logging.getLogger(__name__)


def get_next_groupe_id(db: Session) -> int:
    """Obtient le prochain ID de groupe d'equivalence disponible."""
    max_id = db.query(func.max(MatchingMemory.groupe_equivalence_id)).scalar()
    return (max_id or 0) + 1


def get_groupe_for_cip(db: Session, cip13: str) -> Optional[int]:
    """Trouve le groupe d'equivalence d'un CIP13 s'il existe."""
    record = db.query(MatchingMemory).filter(MatchingMemory.cip13 == cip13).first()
    return record.groupe_equivalence_id if record else None


def get_all_cips_in_groupe(db: Session, groupe_id: int) -> List[str]:
    """Retourne tous les CIP13 d'un groupe d'equivalence."""
    records = db.query(MatchingMemory.cip13).filter(
        MatchingMemory.groupe_equivalence_id == groupe_id
    ).all()
    return [r[0] for r in records]


def get_equivalents_for_cip(db: Session, cip13: str) -> List[Dict]:
    """Retourne tous les CIP equivalents a un CIP13 donne."""
    groupe_id = get_groupe_for_cip(db, cip13)
    if not groupe_id:
        return []

    records = db.query(MatchingMemory).filter(
        MatchingMemory.groupe_equivalence_id == groupe_id
    ).all()

    return [
        {
            "cip13": r.cip13,
            "designation": r.designation,
            "source": r.source,
            "groupe_generique_id": r.groupe_generique_id,
            "match_origin": r.match_origin,
            "match_score": float(r.match_score) if r.match_score else None,
            "validated": r.validated,
        }
        for r in records
    ]


def merge_groupes(db: Session, groupe_keep: int, groupe_merge: int) -> int:
    """Fusionne deux groupes d'equivalence. Retourne le nombre de records mis a jour."""
    updated = db.query(MatchingMemory).filter(
        MatchingMemory.groupe_equivalence_id == groupe_merge
    ).update({MatchingMemory.groupe_equivalence_id: groupe_keep})
    db.commit()
    logger.info(f"Fusionné groupe {groupe_merge} dans {groupe_keep} ({updated} CIP)")
    return updated


def add_to_memory(
    db: Session,
    cip13: str,
    designation: Optional[str] = None,
    source: Optional[str] = None,
    source_id: Optional[int] = None,
    groupe_generique_id: Optional[int] = None,
    match_origin: Optional[str] = None,
    match_score: Optional[float] = None,
    groupe_equivalence_id: Optional[int] = None,
) -> MatchingMemory:
    """Ajoute un CIP13 a la memoire de matching."""
    # Verifier si deja present
    existing = db.query(MatchingMemory).filter(MatchingMemory.cip13 == cip13).first()
    if existing:
        return existing

    # Creer nouveau groupe si non specifie
    if groupe_equivalence_id is None:
        groupe_equivalence_id = get_next_groupe_id(db)

    record = MatchingMemory(
        groupe_equivalence_id=groupe_equivalence_id,
        cip13=cip13,
        designation=designation,
        source=source,
        source_id=source_id,
        groupe_generique_id=groupe_generique_id,
        match_origin=match_origin,
        match_score=Decimal(str(match_score)) if match_score else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def register_match(
    db: Session,
    cip_a: str,
    cip_b: str,
    match_type: str,
    score: float,
    designation_a: Optional[str] = None,
    designation_b: Optional[str] = None,
    source_a: Optional[str] = None,
    source_b: Optional[str] = None,
    groupe_generique_id: Optional[int] = None,
) -> Tuple[int, bool]:
    """
    Enregistre un match entre deux CIP et fusionne les groupes si necessaire.

    Returns:
        Tuple (groupe_equivalence_id, is_new_groupe)
    """
    groupe_a = get_groupe_for_cip(db, cip_a)
    groupe_b = get_groupe_for_cip(db, cip_b)

    is_new = False

    if groupe_a and groupe_b:
        if groupe_a != groupe_b:
            # Fusionner les deux groupes
            merge_groupes(db, groupe_a, groupe_b)
        groupe_id = groupe_a
    elif groupe_a:
        # Ajouter cip_b au groupe de cip_a
        add_to_memory(
            db,
            cip13=cip_b,
            designation=designation_b,
            source=source_b,
            groupe_generique_id=groupe_generique_id,
            match_origin=match_type,
            match_score=score,
            groupe_equivalence_id=groupe_a,
        )
        groupe_id = groupe_a
    elif groupe_b:
        # Ajouter cip_a au groupe de cip_b
        add_to_memory(
            db,
            cip13=cip_a,
            designation=designation_a,
            source=source_a,
            groupe_generique_id=groupe_generique_id,
            match_origin=match_type,
            match_score=score,
            groupe_equivalence_id=groupe_b,
        )
        groupe_id = groupe_b
    else:
        # Creer nouveau groupe avec les deux
        groupe_id = get_next_groupe_id(db)
        is_new = True

        add_to_memory(
            db,
            cip13=cip_a,
            designation=designation_a,
            source=source_a,
            groupe_generique_id=groupe_generique_id,
            match_origin=match_type,
            match_score=score,
            groupe_equivalence_id=groupe_id,
        )
        add_to_memory(
            db,
            cip13=cip_b,
            designation=designation_b,
            source=source_b,
            groupe_generique_id=groupe_generique_id,
            match_origin=match_type,
            match_score=score,
            groupe_equivalence_id=groupe_id,
        )

    logger.info(f"Match enregistré: {cip_a} <-> {cip_b} (groupe {groupe_id}, type={match_type}, score={score})")
    return groupe_id, is_new


def validate_groupe(db: Session, groupe_id: int) -> int:
    """Marque tous les CIP d'un groupe comme valides. Retourne le nombre mis a jour."""
    updated = db.query(MatchingMemory).filter(
        MatchingMemory.groupe_equivalence_id == groupe_id
    ).update({
        MatchingMemory.validated: True,
        MatchingMemory.validated_at: datetime.utcnow()
    })
    db.commit()
    return updated


def validate_cip(db: Session, cip13: str) -> bool:
    """Marque un CIP specifique comme valide."""
    record = db.query(MatchingMemory).filter(MatchingMemory.cip13 == cip13).first()
    if record:
        record.validated = True
        record.validated_at = datetime.utcnow()
        db.commit()
        return True
    return False


def check_memory_for_match(db: Session, cip13: str) -> Optional[List[Dict]]:
    """
    Verifie si un CIP13 existe dans la memoire de matching.
    Si oui, retourne tous ses equivalents.
    """
    return get_equivalents_for_cip(db, cip13) or None


def get_memory_stats(db: Session) -> Dict:
    """Retourne des statistiques sur la memoire de matching."""
    total_cips = db.query(func.count(MatchingMemory.id)).scalar() or 0
    total_groupes = db.query(func.count(func.distinct(MatchingMemory.groupe_equivalence_id))).scalar() or 0
    validated = db.query(func.count(MatchingMemory.id)).filter(MatchingMemory.validated == True).scalar() or 0

    return {
        "total_cips": total_cips,
        "total_groupes": total_groupes,
        "validated": validated,
        "pending_validation": total_cips - validated,
    }


def populate_from_bdpm(db: Session) -> Dict:
    """
    Peuple la memoire de matching depuis les groupes generiques BDPM.
    Les CIP d'un meme groupe generique sont consideres equivalents.
    """
    # Recuperer tous les groupes generiques uniques
    groupes = db.query(
        BdpmEquivalence.groupe_generique_id
    ).filter(
        BdpmEquivalence.groupe_generique_id.isnot(None)
    ).distinct().all()

    stats = {"groupes_processed": 0, "cips_added": 0, "groupes_created": 0}

    for (groupe_gen_id,) in groupes:
        # Tous les CIP de ce groupe generique
        cips = db.query(BdpmEquivalence).filter(
            BdpmEquivalence.groupe_generique_id == groupe_gen_id
        ).all()

        if not cips:
            continue

        # Verifier si un des CIP est deja dans la memoire
        existing_groupe_id = None
        for cip in cips:
            groupe_id = get_groupe_for_cip(db, cip.cip13)
            if groupe_id:
                existing_groupe_id = groupe_id
                break

        # Utiliser le groupe existant ou en creer un nouveau
        if existing_groupe_id is None:
            existing_groupe_id = get_next_groupe_id(db)
            stats["groupes_created"] += 1

        # Ajouter tous les CIP au groupe
        for cip in cips:
            if not get_groupe_for_cip(db, cip.cip13):
                add_to_memory(
                    db,
                    cip13=cip.cip13,
                    designation=cip.libelle_groupe,
                    source="bdpm",
                    groupe_generique_id=groupe_gen_id,
                    match_origin="groupe_generique",
                    match_score=100.0,
                    groupe_equivalence_id=existing_groupe_id,
                )
                stats["cips_added"] += 1

        stats["groupes_processed"] += 1

    logger.info(f"Memoire peuplee depuis BDPM: {stats}")
    return stats
