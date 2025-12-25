"""API endpoints pour la generation de rapports PDF."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from decimal import Decimal

from app.db import get_db
from app.models import (
    MesVentes, Import, Laboratoire, VenteMatching, CatalogueProduit
)
from app.services.report_generator import generate_pdf_report
from app.services.combo_optimizer import ComboOptimizer

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/simulation/pdf")
def export_simulation_pdf(
    import_id: int = Query(..., description="ID de l'import ventes"),
    labo_principal_id: int = Query(..., description="ID du laboratoire principal"),
    pharmacie_nom: str = Query("Ma Pharmacie", description="Nom de la pharmacie"),
    db: Session = Depends(get_db)
):
    """
    Exporte un rapport PDF de simulation avec graphiques.

    Le rapport inclut:
    - Resume des chiffres cles (couverture, remises)
    - Graphique camembert de couverture
    - Graphique barres des remises
    - Comparaison des labos complementaires
    - Liste des produits non couverts avec alternatives
    - Recommandation de la meilleure combinaison

    Args:
        import_id: ID de l'import ventes
        labo_principal_id: ID du labo principal
        pharmacie_nom: Nom de la pharmacie pour le rapport

    Returns:
        Fichier PDF en telechargement
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_principal_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee")

    vente_ids = [v.id for v in ventes]
    ventes_map = {v.id: v for v in ventes}

    # Verifier que le matching a ete fait
    matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id == labo_principal_id
    ).all()

    if not matchings:
        raise HTTPException(
            status_code=400,
            detail="Matching non effectue. Lancez d'abord POST /api/matching/process-sales"
        )

    matching_map = {m.vente_id: m for m in matchings}

    # Calculer les totaux
    chiffre_total = sum(v.montant_annuel or Decimal("0") for v in ventes)
    chiffre_realisable = Decimal("0")
    chiffre_perdu = Decimal("0")
    total_remise_ligne = Decimal("0")
    total_remontee = Decimal("0")
    nb_disponibles = 0
    nb_manquants = 0

    remise_negociee = labo.remise_negociee or Decimal("0")

    for vente in ventes:
        montant = vente.montant_annuel or Decimal("0")
        matching = matching_map.get(vente.id)

        if matching and matching.produit_id:
            produit = db.query(CatalogueProduit).filter(
                CatalogueProduit.id == matching.produit_id
            ).first()

            if produit:
                chiffre_realisable += montant
                nb_disponibles += 1

                # Remise ligne
                remise_pct = produit.remise_pct or Decimal("0")
                remise_ligne = montant * remise_pct / 100
                total_remise_ligne += remise_ligne

                # Remontee (si pas exclu)
                if produit.remontee_pct != 0:
                    cible = remise_negociee
                    if cible > remise_pct:
                        remontee = montant * (cible - remise_pct) / 100
                        total_remontee += remontee
            else:
                chiffre_perdu += montant
                nb_manquants += 1
        else:
            chiffre_perdu += montant
            nb_manquants += 1

    total_remise_globale = total_remise_ligne + total_remontee
    taux_couverture = float(chiffre_realisable) / float(chiffre_total) * 100 if chiffre_total > 0 else 0
    remise_moyenne = float(total_remise_globale) / float(chiffre_realisable) * 100 if chiffre_realisable > 0 else 0

    totaux = {
        "chiffre_total_ht": float(chiffre_total),
        "chiffre_realisable_ht": float(chiffre_realisable),
        "chiffre_perdu_ht": float(chiffre_perdu),
        "total_remise_ligne": float(total_remise_ligne),
        "total_remontee": float(total_remontee),
        "total_remise_globale": float(total_remise_globale),
        "taux_couverture": taux_couverture,
        "remise_totale_ponderee": remise_moyenne,
        "nb_produits_disponibles": nb_disponibles,
        "nb_produits_manquants": nb_manquants,
    }

    # Calculer les recommandations de labos complementaires
    optimizer = ComboOptimizer(db)
    combo_result = optimizer.find_best_combo_greedy(import_id, labo_principal_id)

    # Formatter les recommendations
    recommendations = []
    if len(combo_result.labos) > 1:
        for labo_cov in combo_result.labos[1:]:  # Skip le principal
            remise_estimee = float(labo_cov.montant_couvert) * float(labo_cov.remise_negociee) / 100
            recommendations.append({
                "lab_id": labo_cov.labo_id,
                "lab_nom": labo_cov.labo_nom,
                "chiffre_recupere_ht": float(labo_cov.montant_couvert),
                "montant_remise_estime": remise_estimee,
                "couverture_additionnelle_pct": labo_cov.nb_produits / nb_manquants * 100 if nb_manquants > 0 else 0,
                "nb_produits_recuperes": labo_cov.nb_produits,
                "remise_negociee": float(labo_cov.remise_negociee)
            })

    # Obtenir les gaps (produits non couverts)
    ventes_non_couvertes = []
    all_matchings = db.query(VenteMatching).filter(VenteMatching.vente_id.in_(vente_ids)).all()
    matchings_by_vente = {}
    for m in all_matchings:
        if m.vente_id not in matchings_by_vente:
            matchings_by_vente[m.vente_id] = []
        if m.produit_id and m.labo_id != labo_principal_id:
            matchings_by_vente[m.vente_id].append(m)

    for vente in ventes:
        matching = matching_map.get(vente.id)
        if not matching or not matching.produit_id:
            alternatives = []
            for m in matchings_by_vente.get(vente.id, []):
                other_labo = db.query(Laboratoire).filter(Laboratoire.id == m.labo_id).first()
                if other_labo:
                    alternatives.append({
                        "labo_nom": other_labo.nom,
                        "remise_negociee": float(other_labo.remise_negociee or 0)
                    })
            alternatives.sort(key=lambda x: x["remise_negociee"], reverse=True)

            ventes_non_couvertes.append({
                "designation": vente.designation,
                "montant_annuel": float(vente.montant_annuel or 0),
                "alternatives": alternatives[:3]
            })

    ventes_non_couvertes.sort(key=lambda x: x["montant_annuel"], reverse=True)

    # Best combo
    best_combo = None
    if combo_result.labos:
        best_combo = {
            "labs": [{"nom": l.labo_nom} for l in combo_result.labos],
            "couverture_totale_pct": combo_result.couverture_totale_pct,
            "chiffre_total_realisable_ht": float(combo_result.chiffre_total_realise),
            "montant_remise_total": float(combo_result.montant_remise_total)
        }

    # Generer le PDF
    pdf_content = generate_pdf_report(
        labo_nom=labo.nom,
        totaux=totaux,
        recommendations=recommendations,
        gaps=ventes_non_couvertes[:20],
        best_combo=best_combo,
        pharmacie_nom=pharmacie_nom
    )

    # Retourner le fichier PDF
    filename = f"rapport_simulation_{labo.nom.lower().replace(' ', '_')}_{import_id}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
