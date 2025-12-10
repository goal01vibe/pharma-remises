from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from decimal import Decimal

from app.db import get_db
from app.models import Scenario, ResultatSimulation, MesVentes, CatalogueProduit, Laboratoire
from app.schemas import (
    ScenarioCreate,
    ScenarioResponse,
    ResultatSimulationResponse,
    TotauxSimulation,
    ComparaisonScenarios,
    ScenarioTotaux,
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
