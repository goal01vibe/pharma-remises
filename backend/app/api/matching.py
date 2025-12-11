"""API endpoints pour le matching intelligent des ventes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import time
from decimal import Decimal

from app.db import get_db
from app.models import MesVentes, Import, Laboratoire, CatalogueProduit, VenteMatching
from app.schemas import (
    ProcessSalesRequest,
    ProcessSalesResponse,
    AnalyzeMatchRequest,
    AnalyzeMatchResponse,
    MatchResultItem,
    ExtractedComponents,
)
from app.services.intelligent_matching import IntelligentMatcher, MoleculeExtractor

router = APIRouter(prefix="/api/matching", tags=["Matching Intelligent"])


# Labos cibles (5 labos generiques principaux)
TARGET_LABS = ["BIOGARAN", "SANDOZ", "ARROW", "ZENTIVA", "VIATRIS"]


@router.post("/process-sales", response_model=ProcessSalesResponse)
def process_sales_matching(
    request: ProcessSalesRequest,
    db: Session = Depends(get_db)
):
    """
    Lance le matching intelligent des ventes importees.

    Pour chaque vente de l'import, trouve l'equivalent dans les 5 labos cibles.
    Stocke les resultats dans la table vente_matching.

    Args:
        request: import_id et min_score

    Returns:
        Stats du matching: nb matches, unmatched, couverture par labo
    """
    start_time = time.time()

    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == request.import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")
    if import_obj.type_import != "ventes":
        raise HTTPException(status_code=400, detail="L'import doit etre de type 'ventes'")

    # Recuperer les ventes de cet import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == request.import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee pour cet import")

    # Recuperer les labos cibles
    labos = db.query(Laboratoire).filter(Laboratoire.nom.in_(TARGET_LABS)).all()
    if not labos:
        raise HTTPException(status_code=404, detail="Aucun labo cible trouve. Lancez d'abord l'import BDPM.")

    labo_ids = [l.id for l in labos]
    labo_map = {l.id: l for l in labos}

    # Initialiser le matcher
    matcher = IntelligentMatcher(db)

    # Supprimer les anciens matchings pour cet import
    db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_([v.id for v in ventes])
    ).delete(synchronize_session=False)
    db.commit()

    # Stats
    total_ventes = len(ventes)
    matched_ventes = set()
    unmatched_products = []
    by_lab_stats = {l.id: {"lab_id": l.id, "lab_nom": l.nom, "matched_count": 0, "total_montant": Decimal("0")} for l in labos}

    # Matcher chaque vente
    for vente in ventes:
        designation = vente.designation or ""
        code_cip = vente.code_cip_achete

        if not designation and not code_cip:
            unmatched_products.append({
                "vente_id": vente.id,
                "designation": designation,
                "montant": float(vente.montant_annuel or 0),
                "reason": "Designation et code CIP manquants"
            })
            continue

        # Trouver les matches dans tous les labos
        has_match = False
        candidates_for_debug = []

        for labo_id in labo_ids:
            matches = matcher.find_matches_for_product(
                designation=designation,
                code_cip=code_cip,
                target_lab_id=labo_id
            )

            if matches:
                # Prendre le meilleur match
                best = matches[0]
                if best.score >= request.min_score:
                    # Stocker le matching
                    vm = VenteMatching(
                        vente_id=vente.id,
                        labo_id=labo_id,
                        produit_id=best.produit_id,
                        match_score=Decimal(str(best.score)),
                        match_type=best.match_type,
                        matched_on=best.matched_on
                    )
                    db.add(vm)
                    has_match = True
                    matched_ventes.add(vente.id)
                    by_lab_stats[labo_id]["matched_count"] += 1
                    by_lab_stats[labo_id]["total_montant"] += vente.montant_annuel or Decimal("0")
                else:
                    candidates_for_debug.append({
                        "lab": labo_map[labo_id].nom,
                        "produit": best.nom_commercial,
                        "score": best.score
                    })

        if not has_match:
            unmatched_products.append({
                "vente_id": vente.id,
                "designation": designation,
                "montant": float(vente.montant_annuel or 0),
                "candidates": candidates_for_debug[:3]  # Top 3 candidats proches
            })

    db.commit()

    # Calculer le montant total des ventes
    total_montant = sum(v.montant_annuel or Decimal("0") for v in ventes)

    # Construire la response
    by_lab_list = []
    for labo_id, stats in by_lab_stats.items():
        couverture = (stats["matched_count"] / total_ventes * 100) if total_ventes > 0 else 0
        by_lab_list.append({
            "lab_id": stats["lab_id"],
            "lab_nom": stats["lab_nom"],
            "matched_count": stats["matched_count"],
            "total_montant_matched": float(stats["total_montant"]),
            "couverture_pct": round(couverture, 1)
        })

    # Trier par couverture decroissante
    by_lab_list.sort(key=lambda x: x["matched_count"], reverse=True)

    elapsed = time.time() - start_time

    return ProcessSalesResponse(
        import_id=request.import_id,
        total_ventes=total_ventes,
        matching_results={
            "matched": len(matched_ventes),
            "unmatched": total_ventes - len(matched_ventes),
            "by_lab": by_lab_list
        },
        unmatched_products=unmatched_products[:50],  # Limiter a 50 pour la response
        processing_time_s=round(elapsed, 2)
    )


@router.post("/analyze", response_model=AnalyzeMatchResponse)
def analyze_match(
    request: AnalyzeMatchRequest,
    db: Session = Depends(get_db)
):
    """
    Analyse le matching pour une designation specifique.

    Utile pour debug et comprendre pourquoi un produit matche ou non.

    Args:
        request: designation et optionnel code_cip

    Returns:
        Composants extraits et matches par labo
    """
    # Extraire les composants
    extractor = MoleculeExtractor()
    components = extractor.extract_from_commercial_name(request.designation)

    # Recuperer les labos cibles
    labos = db.query(Laboratoire).filter(Laboratoire.nom.in_(TARGET_LABS)).all()
    labo_map = {l.id: l for l in labos}

    # Initialiser le matcher
    matcher = IntelligentMatcher(db)

    # Trouver les matches dans tous les labos
    matches_by_lab = []
    for labo in labos:
        matches = matcher.find_matches_for_product(
            designation=request.designation,
            code_cip=request.code_cip,
            target_lab_id=labo.id
        )

        for m in matches[:3]:  # Top 3 par labo
            produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == m.produit_id).first()
            matches_by_lab.append(MatchResultItem(
                produit_id=m.produit_id,
                labo_id=labo.id,
                labo_nom=labo.nom,
                nom_commercial=m.nom_commercial,
                code_cip=produit.code_cip if produit else None,
                score=m.score,
                match_type=m.match_type,
                matched_on=m.matched_on,
                prix_ht=produit.prix_ht if produit else None,
                remise_pct=produit.remise_pct if produit else None
            ))

    # Trier par score decroissant
    matches_by_lab.sort(key=lambda x: x.score, reverse=True)

    return AnalyzeMatchResponse(
        extracted=ExtractedComponents(
            molecule=components.molecule,
            dosage=components.dosage,
            forme=components.forme,
            conditionnement=components.conditionnement
        ),
        matches_by_lab=matches_by_lab
    )


@router.get("/stats/{import_id}")
def get_matching_stats(
    import_id: int,
    db: Session = Depends(get_db)
):
    """
    Recupere les statistiques de matching pour un import.

    Utile pour voir la couverture par labo apres le matching.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    vente_ids = [v.id for v in ventes]

    if not vente_ids:
        return {"import_id": import_id, "total_ventes": 0, "matching_done": False}

    # Recuperer les matchings
    matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()

    if not matchings:
        return {
            "import_id": import_id,
            "total_ventes": len(ventes),
            "matching_done": False,
            "message": "Matching non effectue. Lancez POST /api/matching/process-sales"
        }

    # Stats par labo
    by_lab = {}
    matched_ventes = set()

    for m in matchings:
        if m.labo_id not in by_lab:
            labo = db.query(Laboratoire).filter(Laboratoire.id == m.labo_id).first()
            by_lab[m.labo_id] = {
                "lab_id": m.labo_id,
                "lab_nom": labo.nom if labo else "?",
                "matched_count": 0,
                "total_montant": Decimal("0"),
                "avg_score": []
            }

        vente = next((v for v in ventes if v.id == m.vente_id), None)
        if vente:
            by_lab[m.labo_id]["matched_count"] += 1
            by_lab[m.labo_id]["total_montant"] += vente.montant_annuel or Decimal("0")
            by_lab[m.labo_id]["avg_score"].append(float(m.match_score or 0))
            matched_ventes.add(m.vente_id)

    # Calculer moyennes
    total_montant = sum(v.montant_annuel or Decimal("0") for v in ventes)
    by_lab_list = []
    for lab_id, stats in by_lab.items():
        avg_score = sum(stats["avg_score"]) / len(stats["avg_score"]) if stats["avg_score"] else 0
        couverture_count = stats["matched_count"] / len(ventes) * 100 if ventes else 0
        couverture_montant = float(stats["total_montant"]) / float(total_montant) * 100 if total_montant > 0 else 0

        by_lab_list.append({
            "lab_id": stats["lab_id"],
            "lab_nom": stats["lab_nom"],
            "matched_count": stats["matched_count"],
            "total_montant_matched": float(stats["total_montant"]),
            "couverture_count_pct": round(couverture_count, 1),
            "couverture_montant_pct": round(couverture_montant, 1),
            "avg_match_score": round(avg_score, 1)
        })

    by_lab_list.sort(key=lambda x: x["matched_count"], reverse=True)

    return {
        "import_id": import_id,
        "total_ventes": len(ventes),
        "total_montant_ht": float(total_montant),
        "matching_done": True,
        "matched_ventes": len(matched_ventes),
        "unmatched_ventes": len(ventes) - len(matched_ventes),
        "by_lab": by_lab_list
    }


@router.delete("/clear/{import_id}")
def clear_matching(
    import_id: int,
    db: Session = Depends(get_db)
):
    """
    Supprime les matchings pour un import.

    Utile pour relancer le matching avec de nouveaux parametres.
    """
    # Recuperer les ventes de l'import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    vente_ids = [v.id for v in ventes]

    if not vente_ids:
        return {"deleted": 0}

    # Supprimer les matchings
    deleted = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids)
    ).delete(synchronize_session=False)
    db.commit()

    return {"deleted": deleted}
