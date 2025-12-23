"""API endpoints pour l'analyse de couverture et recommandation combo labos."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from decimal import Decimal

from app.db import get_db
from app.models import (
    MesVentes, Import, Laboratoire, CatalogueProduit, VenteMatching
)
from app.schemas import (
    BestComboResponse,
    LabRecoveryInfo,
    BestComboResult,
    LaboratoireResponse,
)

router = APIRouter(prefix="/api/coverage", tags=["Coverage & Combo"])


@router.get("/best-combo/{labo_principal_id}", response_model=BestComboResponse)
def get_best_combo(
    labo_principal_id: int,
    import_id: int = Query(..., description="ID de l'import ventes"),
    db: Session = Depends(get_db)
):
    """
    Trouve la meilleure combinaison de labos complementaires.

    Pour le chiffre "perdu" (non realizable chez le labo principal),
    calcule quel(s) labo(s) complementaire(s) peuvent recuperer le plus
    de chiffre, tries par MONTANT de remise total (pas pourcentage).

    Args:
        labo_principal_id: ID du labo principal choisi
        import_id: ID de l'import ventes

    Returns:
        Recommendations de labos complementaires + best combo
    """
    # Verifier le labo principal
    labo_principal = db.query(Laboratoire).filter(Laboratoire.id == labo_principal_id).first()
    if not labo_principal:
        raise HTTPException(status_code=404, detail="Laboratoire principal non trouve")

    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Recuperer toutes les ventes de l'import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee")

    vente_ids = [v.id for v in ventes]
    ventes_map = {v.id: v for v in ventes}

    # Verifier que le matching a ete fait
    matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()
    if not matchings:
        raise HTTPException(
            status_code=400,
            detail="Matching non effectue. Lancez d'abord POST /api/matching/process-sales"
        )

    # Identifier les ventes matchees chez le labo principal
    ventes_matchees_principal = set()
    for m in matchings:
        if m.labo_id == labo_principal_id and m.produit_id:
            ventes_matchees_principal.add(m.vente_id)

    # Ventes "perdues" = non matchees chez le principal
    ventes_perdues_ids = set(vente_ids) - ventes_matchees_principal

    # Calculer le chiffre perdu
    chiffre_perdu = sum(
        ventes_map[vid].montant_annuel or Decimal("0")
        for vid in ventes_perdues_ids
    )

    nb_produits_perdus = len(ventes_perdues_ids)

    if nb_produits_perdus == 0:
        # Couverture 100% - pas besoin de complementaire
        return BestComboResponse(
            labo_principal=LaboratoireResponse.model_validate(labo_principal),
            chiffre_perdu_ht=Decimal("0"),
            nb_produits_perdus=0,
            recommendations=[],
            best_combo=BestComboResult(
                labs=[LaboratoireResponse.model_validate(labo_principal)],
                couverture_totale_pct=100.0,
                chiffre_total_realisable_ht=sum(v.montant_annuel or Decimal("0") for v in ventes),
                montant_remise_total=Decimal("0")  # A calculer via simulation
            )
        )

    # Pour chaque labo complementaire, calculer combien de perdu ils recuperent
    other_labos = db.query(Laboratoire).filter(
        Laboratoire.id != labo_principal_id,
        Laboratoire.actif == True
    ).all()

    recommendations = []

    for labo in other_labos:
        # Ventes perdues qu'ils peuvent matcher
        ventes_recuperees = set()
        montant_recupere = Decimal("0")

        for m in matchings:
            if m.labo_id == labo.id and m.vente_id in ventes_perdues_ids and m.produit_id:
                ventes_recuperees.add(m.vente_id)
                montant_recupere += ventes_map[m.vente_id].montant_annuel or Decimal("0")

        if not ventes_recuperees:
            continue

        # Estimer le montant de remise (remise_negociee du labo)
        remise_negociee = labo.remise_negociee or Decimal("0")
        montant_remise_estime = montant_recupere * remise_negociee / 100

        couverture_add = len(ventes_recuperees) / nb_produits_perdus * 100 if nb_produits_perdus > 0 else 0

        recommendations.append(LabRecoveryInfo(
            lab_id=labo.id,
            lab_nom=labo.nom,
            chiffre_recupere_ht=montant_recupere,
            montant_remise_estime=montant_remise_estime,
            couverture_additionnelle_pct=round(couverture_add, 1),
            nb_produits_recuperes=len(ventes_recuperees),
            remise_negociee=remise_negociee
        ))

    # Trier par montant de remise estime (decroissant)
    recommendations.sort(key=lambda x: x.montant_remise_estime, reverse=True)

    # Calculer la best combo (principal + meilleur complementaire)
    best_combo = None
    if recommendations:
        best_comp = recommendations[0]
        chiffre_total = sum(v.montant_annuel or Decimal("0") for v in ventes)
        chiffre_realise_principal = chiffre_total - chiffre_perdu
        chiffre_total_combo = chiffre_realise_principal + best_comp.chiffre_recupere_ht

        # Estimer remises total (principal + complementaire)
        remise_principal = (labo_principal.remise_negociee or Decimal("0")) * chiffre_realise_principal / 100
        remise_combo = remise_principal + best_comp.montant_remise_estime

        couverture_combo = float(chiffre_total_combo) / float(chiffre_total) * 100 if chiffre_total > 0 else 0

        best_combo = BestComboResult(
            labs=[
                LaboratoireResponse.model_validate(labo_principal),
                LaboratoireResponse(
                    id=best_comp.lab_id,
                    nom=best_comp.lab_nom,
                    remise_negociee=best_comp.remise_negociee,
                    actif=True,
                    created_at=labo_principal.created_at,  # Placeholder
                    updated_at=labo_principal.updated_at
                )
            ],
            couverture_totale_pct=round(couverture_combo, 1),
            chiffre_total_realisable_ht=chiffre_total_combo,
            montant_remise_total=remise_combo
        )

    return BestComboResponse(
        labo_principal=LaboratoireResponse.model_validate(labo_principal),
        chiffre_perdu_ht=chiffre_perdu,
        nb_produits_perdus=nb_produits_perdus,
        recommendations=recommendations,
        best_combo=best_combo
    )


@router.get("/gaps/{labo_id}")
def get_coverage_gaps(
    labo_id: int,
    import_id: int = Query(..., description="ID de l'import ventes"),
    limit: int = Query(50, description="Nombre max de produits manquants"),
    db: Session = Depends(get_db)
):
    """
    Liste les produits manquants chez un labo.

    Pour chaque produit manquant, indique s'il est disponible ailleurs.

    Args:
        labo_id: ID du labo
        import_id: ID de l'import ventes
        limit: Max de produits a retourner

    Returns:
        Liste des produits manquants avec alternatives
    """
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee")

    vente_ids = [v.id for v in ventes]
    ventes_map = {v.id: v for v in ventes}

    # Matchings pour ce labo
    matchings_labo = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id == labo_id
    ).all()

    ventes_matchees = {m.vente_id for m in matchings_labo if m.produit_id}

    # Ventes non matchees
    ventes_manquantes_ids = set(vente_ids) - ventes_matchees

    # Tous les matchings pour trouver alternatives
    all_matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(list(ventes_manquantes_ids))
    ).all()

    # Grouper par vente
    matchings_by_vente = {}
    for m in all_matchings:
        if m.vente_id not in matchings_by_vente:
            matchings_by_vente[m.vente_id] = []
        if m.produit_id:  # Seulement les matches valides
            matchings_by_vente[m.vente_id].append(m)

    # Recuperer les infos labos
    labo_ids = {m.labo_id for m in all_matchings}
    labos = db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()
    labo_map = {l.id: l for l in labos}

    # Construire la liste des gaps
    gaps = []
    for vente_id in ventes_manquantes_ids:
        vente = ventes_map[vente_id]
        alternatives = []

        for m in matchings_by_vente.get(vente_id, []):
            if m.labo_id != labo_id and m.produit_id:
                labo_alt = labo_map.get(m.labo_id)
                produit = db.query(CatalogueProduit).filter(
                    CatalogueProduit.id == m.produit_id
                ).first()
                if labo_alt and produit:
                    alternatives.append({
                        "labo_id": m.labo_id,
                        "labo_nom": labo_alt.nom,
                        "produit_id": m.produit_id,
                        "produit_nom": produit.nom_commercial,
                        "match_score": float(m.match_score or 0),
                        "remise_negociee": float(labo_alt.remise_negociee or 0)
                    })

        # Trier alternatives par remise_negociee decroissante
        alternatives.sort(key=lambda x: x["remise_negociee"], reverse=True)

        gaps.append({
            "vente_id": vente.id,
            "designation": vente.designation,
            "code_cip": vente.code_cip_achete,
            "montant_annuel": float(vente.montant_annuel or 0),
            "quantite_annuelle": vente.quantite_annuelle,
            "alternatives": alternatives[:5]  # Max 5 alternatives
        })

    # Trier par montant decroissant
    gaps.sort(key=lambda x: x["montant_annuel"], reverse=True)

    # Calculer stats
    total_montant_manquant = sum(g["montant_annuel"] for g in gaps)
    with_alternatives = sum(1 for g in gaps if g["alternatives"])

    return {
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "nb_produits_manquants": len(gaps),
        "total_montant_manquant_ht": total_montant_manquant,
        "produits_avec_alternative": with_alternatives,
        "produits_sans_alternative": len(gaps) - with_alternatives,
        "gaps": gaps[:limit]
    }


@router.get("/matrix")
def get_coverage_matrix(
    import_id: int = Query(..., description="ID de l'import ventes"),
    db: Session = Depends(get_db)
):
    """
    Matrice de couverture croisee entre tous les labos.

    Pour chaque paire de labos, montre le chevauchement et la complementarite.

    Utile pour visualiser quelle combinaison couvre le mieux.
    """
    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee")

    vente_ids = [v.id for v in ventes]
    total_ventes = len(ventes)
    total_montant = sum(v.montant_annuel or Decimal("0") for v in ventes)

    # Tous les matchings
    matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()
    if not matchings:
        return {"error": "Matching non effectue"}

    # Grouper par labo: set de vente_ids matchees
    coverage_by_labo = {}
    for m in matchings:
        if m.produit_id:  # Match valide
            if m.labo_id not in coverage_by_labo:
                coverage_by_labo[m.labo_id] = set()
            coverage_by_labo[m.labo_id].add(m.vente_id)

    # Recuperer les labos
    labo_ids = list(coverage_by_labo.keys())
    labos = db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()
    labo_map = {l.id: l for l in labos}

    # Stats individuelles
    individual_stats = []
    for labo_id, vente_set in coverage_by_labo.items():
        labo = labo_map.get(labo_id)
        if not labo:
            continue

        montant_couvert = sum(
            (next((v.montant_annuel for v in ventes if v.id == vid), Decimal("0")) or Decimal("0"))
            for vid in vente_set
        )

        individual_stats.append({
            "labo_id": labo_id,
            "labo_nom": labo.nom,
            "nb_matches": len(vente_set),
            "couverture_count_pct": round(len(vente_set) / total_ventes * 100, 1) if total_ventes > 0 else 0,
            "montant_couvert_ht": float(montant_couvert),
            "couverture_montant_pct": round(float(montant_couvert) / float(total_montant) * 100, 1) if total_montant > 0 else 0
        })

    individual_stats.sort(key=lambda x: x["couverture_montant_pct"], reverse=True)

    # Matrice de complementarite
    matrix = []
    for labo1_id in labo_ids:
        labo1 = labo_map.get(labo1_id)
        if not labo1:
            continue

        set1 = coverage_by_labo[labo1_id]

        for labo2_id in labo_ids:
            if labo2_id <= labo1_id:
                continue  # Eviter doublons

            labo2 = labo_map.get(labo2_id)
            if not labo2:
                continue

            set2 = coverage_by_labo[labo2_id]

            # Calculs ensemblistes
            union = set1 | set2
            intersection = set1 & set2
            only_1 = set1 - set2
            only_2 = set2 - set1

            combo_couverture = len(union) / total_ventes * 100 if total_ventes > 0 else 0

            matrix.append({
                "labo1_id": labo1_id,
                "labo1_nom": labo1.nom,
                "labo2_id": labo2_id,
                "labo2_nom": labo2.nom,
                "couverture_combo_pct": round(combo_couverture, 1),
                "overlap_count": len(intersection),
                "unique_labo1": len(only_1),
                "unique_labo2": len(only_2),
                "total_combo": len(union)
            })

    # Trier par couverture combo decroissante
    matrix.sort(key=lambda x: x["couverture_combo_pct"], reverse=True)

    return {
        "import_id": import_id,
        "total_ventes": total_ventes,
        "total_montant_ht": float(total_montant),
        "individual_stats": individual_stats,
        "combo_matrix": matrix[:20]  # Top 20 combos
    }
