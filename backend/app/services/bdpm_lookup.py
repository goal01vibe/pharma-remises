"""
Service de lookup et enrichissement BDPM pour les ventes.

Permet de:
- Trouver le prix BDPM (PFHT) et groupe generique d'un CIP13
- Enrichir toutes les ventes d'un import avec les donnees BDPM
"""
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import MesVentes, BdpmEquivalence
from app.utils.logger import import_ventes_logger, OperationMetrics


def normalize_cip(cip: Optional[str]) -> Optional[str]:
    """
    Normalise un code CIP en CIP13.

    Extrait uniquement les chiffres et prend les 13 derniers caracteres.
    Gere les formats: CIP13, CIP7, ACL, EAN13, etc.
    """
    if not cip:
        return None

    # Extraire uniquement les chiffres
    digits = ''.join(c for c in str(cip) if c.isdigit())

    if not digits:
        return None

    # Si moins de 13 chiffres, padder a gauche avec des zeros
    if len(digits) < 13:
        digits = digits.zfill(13)

    # Prendre les 13 derniers chiffres (cas EAN14, etc.)
    return digits[-13:]


def lookup_bdpm_by_cip(db: Session, cip: str) -> Tuple[Optional[Decimal], Optional[int], Optional[str]]:
    """
    Recherche les informations BDPM pour un code CIP.

    Args:
        db: Session SQLAlchemy
        cip: Code CIP (sera normalise en CIP13)

    Returns:
        Tuple (prix_bdpm, groupe_generique_id, libelle_groupe)
        Retourne (None, None, None) si non trouve
    """
    cip13 = normalize_cip(cip)

    if not cip13:
        return None, None, None

    bdpm = db.query(BdpmEquivalence).filter(
        BdpmEquivalence.cip13 == cip13
    ).first()

    if bdpm:
        return bdpm.pfht, bdpm.groupe_generique_id, bdpm.libelle_groupe

    return None, None, None


def enrich_ventes_with_bdpm(db: Session, import_id: int) -> dict:
    """
    Enrichit toutes les ventes d'un import avec les donnees BDPM.

    Pour chaque vente, recherche dans BdpmEquivalence via CIP13:
    - prix_bdpm: Prix Fabricant HT de reference
    - groupe_generique_id: Pour matching instantane
    - has_bdpm_price: Flag pour identifier les ventes incompletes

    Args:
        db: Session SQLAlchemy
        import_id: ID de l'import a enrichir

    Returns:
        dict avec stats: {total, enriched, missing, errors}
    """
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()

    stats = {
        "total": len(ventes),
        "enriched": 0,
        "missing": 0,
        "errors": 0
    }

    if not ventes:
        return stats

    # Metrics pour logging
    metrics = OperationMetrics(
        import_ventes_logger,
        "bdpm_enrichment",
        total_items=len(ventes),
        batch_size=500
    )
    metrics.start(import_id=import_id)

    for vente in ventes:
        try:
            if vente.code_cip_achete:
                prix_bdpm, groupe_id, _ = lookup_bdpm_by_cip(db, vente.code_cip_achete)

                if prix_bdpm is not None:
                    vente.prix_bdpm = prix_bdpm
                    vente.has_bdpm_price = True
                    vente.groupe_generique_id = groupe_id
                    stats["enriched"] += 1
                    metrics.increment(success=True)
                else:
                    vente.has_bdpm_price = False
                    vente.groupe_generique_id = groupe_id  # Peut avoir groupe meme sans prix
                    stats["missing"] += 1
                    metrics.increment(success=False)
            else:
                vente.has_bdpm_price = False
                stats["missing"] += 1
                metrics.increment(success=False)

        except Exception as e:
            import_ventes_logger.error(f"Erreur enrichissement vente {vente.id}: {e}")
            stats["errors"] += 1
            metrics.increment(success=False)

    db.commit()
    metrics.finish(**stats)

    return stats


def get_incomplete_ventes(db: Session, import_id: int) -> list:
    """
    Retourne les ventes sans prix BDPM pour un import.
    """
    return db.query(MesVentes).filter(
        MesVentes.import_id == import_id,
        MesVentes.has_bdpm_price == False
    ).all()


def delete_incomplete_ventes(db: Session, import_id: int) -> int:
    """
    Supprime les ventes sans prix BDPM pour un import.

    Returns:
        Nombre de ventes supprimees
    """
    deleted = db.query(MesVentes).filter(
        MesVentes.import_id == import_id,
        MesVentes.has_bdpm_price == False
    ).delete()

    db.commit()
    import_ventes_logger.info(f"Supprime {deleted} ventes incompletes pour import {import_id}")

    return deleted
