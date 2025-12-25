from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from decimal import Decimal

from app.db import get_db
from app.models import (
    Scenario, ResultatSimulation, MesVentes, CatalogueProduit,
    Laboratoire, VenteMatching, Import, RegleRemontee, RegleRemonteeProduit
)
from app.schemas import (
    ScenarioCreate,
    ScenarioResponse,
    ResultatSimulationResponse,
    TotauxSimulation,
    ComparaisonScenarios,
    ScenarioTotaux,
    SimulationWithMatchingRequest,
    SimulationWithMatchingResponse,
    SimulationLineResult,
    LaboratoireResponse,
)
from app.services.simulation import run_simulation, calculate_totaux

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])


@router.get("", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)):
    """Liste tous les scenarios."""
    return (
        db.query(Scenario)
        .options(joinedload(Scenario.laboratoire))
        .order_by(Scenario.created_at.desc())
        .all()
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Recupere un scenario par ID."""
    scenario = (
        db.query(Scenario)
        .options(joinedload(Scenario.laboratoire))
        .filter(Scenario.id == scenario_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario non trouve")
    return scenario


@router.post("", response_model=ScenarioResponse)
def create_scenario(scenario: ScenarioCreate, db: Session = Depends(get_db)):
    """Cree un nouveau scenario."""
    # Verifier que le labo existe
    labo = db.query(Laboratoire).filter(Laboratoire.id == scenario.laboratoire_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    db_scenario = Scenario(**scenario.model_dump())
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Supprime un scenario."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario non trouve")

    db.delete(scenario)
    db.commit()
    return {"message": "Scenario supprime"}


@router.post("/{scenario_id}/run")
def run_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Execute la simulation pour un scenario."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario non trouve")

    # Supprimer les anciens resultats
    db.query(ResultatSimulation).filter(ResultatSimulation.scenario_id == scenario_id).delete()

    # Lancer la simulation
    resultats = run_simulation(db, scenario)

    # Sauvegarder les resultats
    for r in resultats:
        db_result = ResultatSimulation(**r)
        db.add(db_result)

    db.commit()
    return {"message": f"Simulation terminee: {len(resultats)} resultats"}


@router.get("/{scenario_id}/resultats", response_model=List[ResultatSimulationResponse])
def get_resultats(scenario_id: int, db: Session = Depends(get_db)):
    """Recupere les resultats d'une simulation."""
    return (
        db.query(ResultatSimulation)
        .options(joinedload(ResultatSimulation.presentation))
        .filter(ResultatSimulation.scenario_id == scenario_id)
        .order_by(ResultatSimulation.montant_total_remise.desc())
        .all()
    )


@router.get("/{scenario_id}/totaux", response_model=TotauxSimulation)
def get_totaux(scenario_id: int, db: Session = Depends(get_db)):
    """Recupere les totaux d'une simulation."""
    resultats = (
        db.query(ResultatSimulation)
        .filter(ResultatSimulation.scenario_id == scenario_id)
        .all()
    )

    if not resultats:
        raise HTTPException(status_code=404, detail="Aucun resultat pour ce scenario")

    return calculate_totaux(resultats)


# Endpoint de comparaison
@router.post("/comparaison", response_model=ComparaisonScenarios)
def compare_scenarios(scenario_ids: List[int], db: Session = Depends(get_db)):
    """Compare plusieurs scenarios."""
    if len(scenario_ids) < 2:
        raise HTTPException(status_code=400, detail="Au moins 2 scenarios requis")

    scenarios_data = []
    for sid in scenario_ids:
        scenario = (
            db.query(Scenario)
            .options(joinedload(Scenario.laboratoire))
            .filter(Scenario.id == sid)
            .first()
        )
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario {sid} non trouve")

        resultats = (
            db.query(ResultatSimulation)
            .filter(ResultatSimulation.scenario_id == sid)
            .all()
        )

        if not resultats:
            raise HTTPException(status_code=400, detail=f"Scenario {sid} n'a pas de resultats")

        totaux = calculate_totaux(resultats)
        scenarios_data.append(ScenarioTotaux(scenario=scenario, totaux=totaux))

    # Trouver le gagnant (plus grand total_remise_globale)
    scenarios_data.sort(key=lambda x: x.totaux.total_remise_globale, reverse=True)
    gagnant = scenarios_data[0]
    second = scenarios_data[1] if len(scenarios_data) > 1 else None

    ecart = gagnant.totaux.total_remise_globale - (second.totaux.total_remise_globale if second else Decimal(0))

    return ComparaisonScenarios(
        scenarios=scenarios_data,
        gagnant_id=gagnant.scenario.id,
        ecart_gain=ecart,
    )


# =====================
# SIMULATION AVEC MATCHING INTELLIGENT
# =====================

@router.post("/run-with-matching", response_model=SimulationWithMatchingResponse)
def run_simulation_with_matching(
    request: SimulationWithMatchingRequest,
    db: Session = Depends(get_db)
):
    """
    Execute une simulation en utilisant le matching intelligent.

    Utilise la table vente_matching pour trouver les produits equivalents
    au lieu de presentation_id.

    Calcule:
    - Remise facture (remise_pct du produit)
    - Remontee (complement vers remise_negociee, apres exclusions)

    Args:
        request: import_id, labo_principal_id, optionnel remise_negociee

    Returns:
        Totaux + details par ligne avec info matching
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == request.import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == request.labo_principal_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Remise negociee (override ou celle du labo)
    remise_negociee = request.remise_negociee if request.remise_negociee is not None else labo.remise_negociee
    if remise_negociee is None:
        remise_negociee = Decimal("0")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == request.import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente trouvee")

    vente_ids = [v.id for v in ventes]

    # Recuperer les matchings pour ce labo
    matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id == request.labo_principal_id
    ).all()

    if not matchings:
        raise HTTPException(
            status_code=400,
            detail="Matching non effectue. Lancez d'abord POST /api/matching/process-sales"
        )

    matching_map = {m.vente_id: m for m in matchings}

    # Recuperer les exclusions pour ce labo
    exclusions_query = (
        db.query(RegleRemonteeProduit.produit_id, RegleRemontee.remontee_pct)
        .join(RegleRemontee)
        .filter(RegleRemontee.laboratoire_id == request.labo_principal_id)
        .all()
    )
    # Map produit_id -> remontee_pct de la regle (0 = exclu, X = partiel)
    exclusion_map = {p_id: r_pct for p_id, r_pct in exclusions_query}

    # Calculer pour chaque vente
    details = []
    totaux_data = {
        "chiffre_total_ht": Decimal("0"),
        "chiffre_realisable_ht": Decimal("0"),
        "chiffre_perdu_ht": Decimal("0"),
        "chiffre_eligible_remontee_ht": Decimal("0"),
        "chiffre_exclu_remontee_ht": Decimal("0"),
        "total_remise_ligne": Decimal("0"),
        "total_remontee": Decimal("0"),
        "total_remise_globale": Decimal("0"),
        "nb_produits_total": 0,
        "nb_produits_disponibles": 0,
        "nb_produits_manquants": 0,
        "nb_produits_exclus": 0,
        "nb_produits_eligibles": 0,
        "nb_lignes_ignorees": 0,
    }

    matching_stats = {
        "exact_cip": 0,
        "groupe_generique": 0,
        "fuzzy_molecule": 0,
        "fuzzy_commercial": 0,
        "no_match": 0,
        "avg_score": []
    }

    for vente in ventes:
        quantite = vente.quantite_annuelle or 0
        totaux_data["nb_produits_total"] += 1

        matching = matching_map.get(vente.id)
        produit = None
        disponible = False
        match_score = None
        match_type = None

        if matching and matching.produit_id:
            produit = db.query(CatalogueProduit).filter(
                CatalogueProduit.id == matching.produit_id
            ).first()
            disponible = produit is not None
            match_score = float(matching.match_score or 0)
            match_type = matching.match_type
            matching_stats["avg_score"].append(match_score)
            if match_type:
                matching_stats[match_type] = matching_stats.get(match_type, 0) + 1

        if not disponible:
            matching_stats["no_match"] += 1

        # === CALCUL DES PRIX (PFHT uniquement) ===
        # Prix BDPM vente = PFHT de la vente (reference marche)
        # Prix labo = PFHT du catalogue (prix_fabricant)
        prix_bdpm = vente.prix_bdpm or Decimal("0")

        # Prix labo = prix_fabricant (PFHT du catalogue BDPM)
        prix_labo = Decimal("0")
        if disponible and produit and produit.prix_fabricant:
            prix_labo = Decimal(str(produit.prix_fabricant))

        # Si pas de prix_bdpm ET pas de prix_labo → ignorer cette ligne
        if prix_bdpm == 0 and prix_labo == 0:
            totaux_data["nb_lignes_ignorees"] += 1
            # Ajouter quand meme aux details pour affichage
            details.append(SimulationLineResult(
                vente_id=vente.id,
                designation=vente.designation or "",
                quantite=quantite,
                montant_ht=Decimal("0"),
                groupe_generique_id=vente.groupe_generique_id,
                disponible=False,
                match_type="sans_prix",
                prix_bdpm=None,
                prix_labo=None,
            ))
            continue

        # Montant labo = valeur au prix du catalogue labo (si matche)
        montant_labo = prix_labo * quantite if disponible and produit and prix_labo > 0 else Decimal("0")

        # Montant BDPM = valeur marche de la vente (si pas matche)
        montant_bdpm = prix_bdpm * quantite if prix_bdpm > 0 else Decimal("0")

        # Le montant_ht affiche: prix_labo si matche, sinon prix_bdpm
        montant_ht = montant_labo if (disponible and produit and prix_labo > 0) else montant_bdpm

        # === CHIFFRE TOTAL = Realisable + Perdu (pas de double comptage) ===
        # On n'ajoute PAS ici, on ajoute dans les sections specifiques

        # Calcul des remises
        remise_ligne_pct = Decimal("0")
        montant_remise_ligne = Decimal("0")
        statut_remontee = "indisponible"
        remontee_cible = Decimal("0")
        montant_remontee = Decimal("0")
        remise_totale_pct = Decimal("0")
        montant_total_remise = Decimal("0")

        # Difference de prix pour indicateur UI
        price_diff = prix_bdpm - prix_labo if prix_bdpm and prix_labo else None
        price_diff_pct = (price_diff / prix_bdpm * 100) if price_diff and prix_bdpm > 0 else None

        if disponible and produit and prix_labo > 0:
            # === CHIFFRE REALISABLE = prix labo (ce qu'on va vraiment payer) ===
            totaux_data["chiffre_realisable_ht"] += montant_labo
            totaux_data["chiffre_total_ht"] += montant_labo  # Ajoute au total
            totaux_data["nb_produits_disponibles"] += 1

            # Remise ligne (du catalogue produit)
            remise_ligne_pct = produit.remise_pct or Decimal("0")
            montant_remise_ligne = montant_ht * remise_ligne_pct / 100
            totaux_data["total_remise_ligne"] += montant_remise_ligne

            # Determiner statut remontee
            # Priorite: exclusion via regle > remontee_pct du produit > normal
            if produit.id in exclusion_map:
                r_pct = exclusion_map[produit.id]
                if r_pct == 0:
                    statut_remontee = "exclu"
                    totaux_data["nb_produits_exclus"] += 1
                    totaux_data["chiffre_exclu_remontee_ht"] += montant_ht
                else:
                    statut_remontee = "partiel"
                    remontee_cible = r_pct
            elif produit.remontee_pct is not None:
                if produit.remontee_pct == 0:
                    statut_remontee = "exclu"
                    totaux_data["nb_produits_exclus"] += 1
                    totaux_data["chiffre_exclu_remontee_ht"] += montant_ht
                else:
                    statut_remontee = "partiel"
                    remontee_cible = produit.remontee_pct
            else:
                statut_remontee = "normal"
                remontee_cible = remise_negociee
                totaux_data["nb_produits_eligibles"] += 1
                totaux_data["chiffre_eligible_remontee_ht"] += montant_ht

            # Calculer montant remontee si applicable
            if statut_remontee in ("normal", "partiel"):
                # Complement = (cible - remise_ligne) * montant
                # Seulement si cible > remise_ligne
                if remontee_cible > remise_ligne_pct:
                    complement_pct = remontee_cible - remise_ligne_pct
                    montant_remontee = montant_ht * complement_pct / 100
                    totaux_data["total_remontee"] += montant_remontee

            # Remise totale
            remise_totale_pct = remise_ligne_pct + (remontee_cible - remise_ligne_pct if remontee_cible > remise_ligne_pct else Decimal("0"))
            if statut_remontee == "exclu":
                remise_totale_pct = remise_ligne_pct  # Pas de remontee
            montant_total_remise = montant_remise_ligne + montant_remontee
            totaux_data["total_remise_globale"] += montant_total_remise

        else:
            # Non disponible chez ce labo - ajouter au chiffre perdu (prix BDPM)
            if prix_bdpm > 0:
                totaux_data["chiffre_perdu_ht"] += montant_bdpm
                totaux_data["chiffre_total_ht"] += montant_bdpm  # Ajoute au total
            totaux_data["nb_produits_manquants"] += 1

        details.append(SimulationLineResult(
            vente_id=vente.id,
            designation=vente.designation or "",
            quantite=quantite,
            montant_ht=montant_ht,
            produit_id=produit.id if produit else None,
            produit_nom=produit.nom_commercial if produit else None,
            produit_cip=produit.code_cip if produit else None,
            groupe_generique_id=produit.groupe_generique_id if produit else vente.groupe_generique_id,
            disponible=disponible,
            match_score=match_score,
            match_type=match_type,
            # Prix pour indicateurs visuels
            prix_bdpm=prix_bdpm if prix_bdpm > 0 else None,
            prix_labo=prix_labo if prix_labo > 0 else None,
            price_diff=price_diff,
            price_diff_pct=round(price_diff_pct, 2) if price_diff_pct is not None else None,
            # Remises
            remise_ligne_pct=remise_ligne_pct,
            montant_remise_ligne=montant_remise_ligne,
            statut_remontee=statut_remontee,
            remontee_cible=remontee_cible,
            montant_remontee=montant_remontee,
            remise_totale_pct=remise_totale_pct,
            montant_total_remise=montant_total_remise
        ))

    # === CHIFFRE PERDU deja calcule dans la boucle ===
    # Pas de recalcul ici, on a ajoute directement les montants BDPM des non-matches

    # Calculer moyennes et pourcentages
    taux_couverture = Decimal("0")
    if totaux_data["chiffre_total_ht"] > 0:
        taux_couverture = totaux_data["chiffre_realisable_ht"] / totaux_data["chiffre_total_ht"] * 100

    remise_ligne_moyenne = Decimal("0")
    if totaux_data["chiffre_realisable_ht"] > 0:
        remise_ligne_moyenne = totaux_data["total_remise_ligne"] / totaux_data["chiffre_realisable_ht"] * 100

    remise_totale_ponderee = Decimal("0")
    if totaux_data["chiffre_realisable_ht"] > 0:
        remise_totale_ponderee = totaux_data["total_remise_globale"] / totaux_data["chiffre_realisable_ht"] * 100

    # Construire TotauxSimulation
    totaux = TotauxSimulation(
        chiffre_total_ht=totaux_data["chiffre_total_ht"],
        chiffre_realisable_ht=totaux_data["chiffre_realisable_ht"],
        chiffre_perdu_ht=totaux_data["chiffre_perdu_ht"],
        chiffre_eligible_remontee_ht=totaux_data["chiffre_eligible_remontee_ht"],
        chiffre_exclu_remontee_ht=totaux_data["chiffre_exclu_remontee_ht"],
        total_remise_ligne=totaux_data["total_remise_ligne"],
        total_remontee=totaux_data["total_remontee"],
        total_remise_globale=totaux_data["total_remise_globale"],
        taux_couverture=round(taux_couverture, 2),
        remise_ligne_moyenne=round(remise_ligne_moyenne, 2),
        remise_totale_ponderee=round(remise_totale_ponderee, 2),
        nb_produits_total=totaux_data["nb_produits_total"],
        nb_produits_disponibles=totaux_data["nb_produits_disponibles"],
        nb_produits_manquants=totaux_data["nb_produits_manquants"],
        nb_produits_exclus=totaux_data["nb_produits_exclus"],
        nb_produits_eligibles=totaux_data["nb_produits_eligibles"],
        nb_lignes_ignorees=totaux_data["nb_lignes_ignorees"],
    )

    # Stats matching
    avg_score = sum(matching_stats["avg_score"]) / len(matching_stats["avg_score"]) if matching_stats["avg_score"] else 0
    matching_stats["avg_score"] = round(avg_score, 1)

    return SimulationWithMatchingResponse(
        labo=LaboratoireResponse.model_validate(labo),
        totaux=totaux,
        details=details,
        matching_stats=matching_stats
    )
