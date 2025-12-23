from sqlalchemy.orm import Session
from typing import List, Dict, Any
from decimal import Decimal

from app.models import Scenario, MesVentes, CatalogueProduit, Laboratoire, ResultatSimulation
from app.schemas import TotauxSimulation


def run_simulation(db: Session, scenario: Scenario) -> List[Dict[str, Any]]:
    """
    Execute la simulation pour un scenario donne.

    Pour chaque ligne de ventes:
    1. Chercher si le produit existe chez le labo cible
    2. Calculer la remise catalogue (propre a cette ligne)
    3. Calculer le complement de remontee selon la regle
    """
    resultats = []

    # Recuperer le % negocie du labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == scenario.laboratoire_id).first()
    remise_negociee = float(scenario.remise_simulee or labo.remise_negociee or 0)

    # Recuperer les ventes
    ventes = db.query(MesVentes).all()

    # Recuperer le catalogue du labo indexe par presentation_id
    catalogue = db.query(CatalogueProduit).filter(
        CatalogueProduit.laboratoire_id == scenario.laboratoire_id
    ).all()
    catalogue_by_presentation = {p.presentation_id: p for p in catalogue if p.presentation_id}

    for vente in ventes:
        montant_ht = float(vente.montant_annuel or 0)
        quantite = vente.quantite_annuelle or 0

        # Chercher le produit dans le catalogue du labo
        produit = None
        if vente.presentation_id:
            produit = catalogue_by_presentation.get(vente.presentation_id)

        if produit:
            # Produit DISPONIBLE
            remise_ligne = float(produit.remise_pct or labo.remise_ligne_defaut or 0)
            montant_remise_ligne = montant_ht * (remise_ligne / 100)

            # Determiner le % cible de remontee
            if produit.remontee_pct is None:
                # Remontee normale -> % negocie du labo
                remontee_cible = remise_negociee
                statut_remontee = "normal"
            elif float(produit.remontee_pct) == 0:
                # Exclu -> pas de remontee
                remontee_cible = remise_ligne
                statut_remontee = "exclu"
            else:
                # Remontee partielle -> % specifique
                remontee_cible = float(produit.remontee_pct)
                statut_remontee = "partiel"

            # Calcul du complement
            complement_pct = max(0, remontee_cible - remise_ligne)
            montant_remontee = montant_ht * (complement_pct / 100)
            montant_total_remise = montant_remise_ligne + montant_remontee
            remise_totale = remise_ligne + complement_pct

            resultats.append({
                "scenario_id": scenario.id,
                "presentation_id": vente.presentation_id,
                "quantite": quantite,
                "montant_ht": Decimal(str(montant_ht)),
                "disponible": True,
                "produit_id": produit.id,
                "remise_ligne": Decimal(str(remise_ligne)),
                "montant_remise_ligne": Decimal(str(montant_remise_ligne)),
                "statut_remontee": statut_remontee,
                "remontee_cible": Decimal(str(remontee_cible)),
                "montant_remontee": Decimal(str(montant_remontee)),
                "remise_totale": Decimal(str(remise_totale)),
                "montant_total_remise": Decimal(str(montant_total_remise)),
            })
        else:
            # Produit NON DISPONIBLE
            resultats.append({
                "scenario_id": scenario.id,
                "presentation_id": vente.presentation_id,
                "quantite": quantite,
                "montant_ht": Decimal(str(montant_ht)),
                "disponible": False,
                "produit_id": None,
                "remise_ligne": Decimal("0"),
                "montant_remise_ligne": Decimal("0"),
                "statut_remontee": "indisponible",
                "remontee_cible": Decimal("0"),
                "montant_remontee": Decimal("0"),
                "remise_totale": Decimal("0"),
                "montant_total_remise": Decimal("0"),
            })

    return resultats


def calculate_totaux(resultats: List[ResultatSimulation]) -> TotauxSimulation:
    """Calcule les totaux a partir des resultats de simulation."""
    disponibles = [r for r in resultats if r.disponible]
    non_disponibles = [r for r in resultats if not r.disponible]
    exclus = [r for r in disponibles if r.statut_remontee == "exclu"]
    eligibles = [r for r in disponibles if r.statut_remontee != "exclu"]

    total_ht_dispo = sum(float(r.montant_ht or 0) for r in disponibles)
    total_ht_eligible = sum(float(r.montant_ht or 0) for r in eligibles)

    chiffre_total = sum(float(r.montant_ht or 0) for r in resultats)
    chiffre_perdu = sum(float(r.montant_ht or 0) for r in non_disponibles)

    total_remise_ligne = sum(float(r.montant_remise_ligne or 0) for r in resultats)
    total_remontee = sum(float(r.montant_remontee or 0) for r in resultats)
    total_remise_globale = sum(float(r.montant_total_remise or 0) for r in resultats)

    taux_couverture = (len(disponibles) / len(resultats) * 100) if resultats else 0

    remise_ligne_moyenne = (total_remise_ligne / total_ht_dispo * 100) if total_ht_dispo else 0
    remise_totale_ponderee = (total_remise_globale / total_ht_dispo * 100) if total_ht_dispo else 0

    return TotauxSimulation(
        chiffre_total_ht=Decimal(str(chiffre_total)),
        chiffre_realisable_ht=Decimal(str(total_ht_dispo)),
        chiffre_perdu_ht=Decimal(str(chiffre_perdu)),
        chiffre_eligible_remontee_ht=Decimal(str(total_ht_eligible)),
        chiffre_exclu_remontee_ht=Decimal(str(sum(float(r.montant_ht or 0) for r in exclus))),
        total_remise_ligne=Decimal(str(total_remise_ligne)),
        total_remontee=Decimal(str(total_remontee)),
        total_remise_globale=Decimal(str(total_remise_globale)),
        taux_couverture=Decimal(str(taux_couverture)),
        remise_ligne_moyenne=Decimal(str(remise_ligne_moyenne)),
        remise_totale_ponderee=Decimal(str(remise_totale_ponderee)),
        nb_produits_total=len(resultats),
        nb_produits_disponibles=len(disponibles),
        nb_produits_manquants=len(non_disponibles),
        nb_produits_exclus=len(exclus),
        nb_produits_eligibles=len(eligibles),
    )
