"""
Optimisation multi-labos avec OR-Tools (Google).

Probleme: Repartir les achats entre N labos pour maximiser les remises
tout en respectant les objectifs minimums par labo.

Variables:
  x[v,l] = 1 si vente v est achetee chez labo l, 0 sinon

Objectif:
  MAXIMISER sum(x[v,l] * quantite[v] * prix_labo[v,l] * remise[l])

Contraintes:
  - Chaque vente achetee chez UN SEUL labo (ou aucun si pas dispo)
  - Chiffre labo_l >= objectif_l (si specifie)
  - Produits exclus du labo l ne peuvent pas etre achetes chez l
"""

import logging
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from ortools.linear_solver import pywraplp
from sqlalchemy.orm import Session

from app.models import (
    MesVentes, CatalogueProduit, VenteMatching, Laboratoire,
    RegleRemontee, RegleRemonteeProduit
)

optimizer_logger = logging.getLogger("optimizer")
optimizer_logger.setLevel(logging.INFO)


@dataclass
class LaboObjective:
    """Configuration objectif pour un labo."""
    labo_id: int
    labo_nom: str
    # Objectif: soit % du potentiel, soit montant fixe
    objectif_pct: Optional[float] = None  # Ex: 60 = 60% du potentiel
    objectif_montant: Optional[Decimal] = None  # Ex: 30000 euros min
    # Potentiel = chiffre total possible chez ce labo (calcule automatiquement)
    potentiel_ht: Decimal = Decimal("0")
    # Remise negociee pour ce labo
    remise_negociee: Decimal = Decimal("0")
    # Produits exclus (IDs de ventes ou produits a exclure)
    exclusions: list[int] = None  # Liste de produit_ids

    def __post_init__(self):
        if self.exclusions is None:
            self.exclusions = []

    def get_objectif_minimum(self) -> Decimal:
        """Retourne l'objectif minimum en euros."""
        if self.objectif_montant is not None:
            return self.objectif_montant
        elif self.objectif_pct is not None and self.potentiel_ht > 0:
            return self.potentiel_ht * Decimal(str(self.objectif_pct)) / 100
        return Decimal("0")


@dataclass
class OptimizationResult:
    """Resultat de l'optimisation."""
    success: bool
    message: str
    # Par labo: {labo_id: {ventes: [...], chiffre_ht, remise_totale, nb_produits}}
    repartition: dict
    # Totaux
    chiffre_total_ht: Decimal
    remise_totale: Decimal
    couverture_pct: float
    # Stats solver
    solver_time_ms: float
    status: str


def get_vente_matching_data(
    db: Session,
    import_id: int,
    labo_ids: list[int]
) -> tuple[list[MesVentes], dict, dict]:
    """
    Recupere les ventes et leurs matchings pour les labos specifies.

    Returns:
        (ventes, matching_map, produits_map)
        - ventes: Liste des MesVentes
        - matching_map: {(vente_id, labo_id): VenteMatching}
        - produits_map: {produit_id: CatalogueProduit}
    """
    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()

    if not ventes:
        return [], {}, {}

    vente_ids = [v.id for v in ventes]

    # Recuperer les matchings pour tous les labos
    matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id.in_(labo_ids)
    ).all()

    matching_map = {(m.vente_id, m.labo_id): m for m in matchings}

    # Recuperer les produits
    produit_ids = list(set(m.produit_id for m in matchings if m.produit_id))
    produits = db.query(CatalogueProduit).filter(
        CatalogueProduit.id.in_(produit_ids)
    ).all() if produit_ids else []

    produits_map = {p.id: p for p in produits}

    return ventes, matching_map, produits_map


def get_exclusions_for_labos(db: Session, labo_ids: list[int]) -> dict:
    """
    Recupere les exclusions par labo.

    Returns:
        {labo_id: set(produit_ids exclus)}
    """
    exclusions_query = (
        db.query(
            RegleRemontee.laboratoire_id,
            RegleRemonteeProduit.produit_id,
            RegleRemontee.remontee_pct
        )
        .join(RegleRemonteeProduit)
        .filter(RegleRemontee.laboratoire_id.in_(labo_ids))
        .all()
    )

    exclusions = {lid: set() for lid in labo_ids}
    for labo_id, produit_id, remontee_pct in exclusions_query:
        # Exclu = remontee_pct == 0
        if remontee_pct == 0:
            exclusions[labo_id].add(produit_id)

    return exclusions


def calculate_potentiels(
    ventes: list[MesVentes],
    matching_map: dict,
    produits_map: dict,
    labo_ids: list[int],
    exclusions: dict
) -> dict:
    """
    Calcule le potentiel (chiffre max possible) par labo.

    Returns:
        {labo_id: potentiel_ht}
    """
    potentiels = {lid: Decimal("0") for lid in labo_ids}

    for vente in ventes:
        quantite = vente.quantite_annuelle or 0
        if quantite <= 0:
            continue

        for labo_id in labo_ids:
            matching = matching_map.get((vente.id, labo_id))
            if not matching or not matching.produit_id:
                continue

            produit = produits_map.get(matching.produit_id)
            if not produit:
                continue

            # Verifier exclusion
            if produit.id in exclusions.get(labo_id, set()):
                continue

            prix = produit.prix_ht or Decimal("0")
            potentiels[labo_id] += prix * quantite

    return potentiels


def optimize_multi_labo(
    db: Session,
    import_id: int,
    objectives: list[LaboObjective],
    max_time_seconds: int = 30
) -> OptimizationResult:
    """
    Optimise la repartition des achats entre plusieurs labos.

    Args:
        db: Session SQLAlchemy
        import_id: ID de l'import ventes
        objectives: Liste des objectifs par labo
        max_time_seconds: Temps max pour le solver

    Returns:
        OptimizationResult avec la repartition optimale
    """
    labo_ids = [obj.labo_id for obj in objectives]

    # Recuperer les donnees
    ventes, matching_map, produits_map = get_vente_matching_data(db, import_id, labo_ids)

    if not ventes:
        return OptimizationResult(
            success=False,
            message="Aucune vente trouvee pour cet import",
            repartition={},
            chiffre_total_ht=Decimal("0"),
            remise_totale=Decimal("0"),
            couverture_pct=0.0,
            solver_time_ms=0,
            status="NO_DATA"
        )

    # Recuperer les exclusions
    exclusions = get_exclusions_for_labos(db, labo_ids)

    # Ajouter les exclusions supplementaires des objectifs
    for obj in objectives:
        if obj.exclusions:
            exclusions.setdefault(obj.labo_id, set())
            exclusions[obj.labo_id].update(obj.exclusions)

    # Calculer les potentiels
    potentiels = calculate_potentiels(ventes, matching_map, produits_map, labo_ids, exclusions)

    # Mettre a jour les potentiels dans les objectifs
    for obj in objectives:
        obj.potentiel_ht = potentiels.get(obj.labo_id, Decimal("0"))

    # Recuperer les infos labo pour les remises
    labos = {l.id: l for l in db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()}
    for obj in objectives:
        labo = labos.get(obj.labo_id)
        if labo:
            obj.labo_nom = labo.nom
            obj.remise_negociee = labo.remise_negociee or Decimal("0")

    # === CREATION DU SOLVER ===
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        solver = pywraplp.Solver.CreateSolver('CBC')
    if not solver:
        return OptimizationResult(
            success=False,
            message="Impossible de creer le solver OR-Tools",
            repartition={},
            chiffre_total_ht=Decimal("0"),
            remise_totale=Decimal("0"),
            couverture_pct=0.0,
            solver_time_ms=0,
            status="SOLVER_ERROR"
        )

    solver.SetTimeLimit(max_time_seconds * 1000)

    # === VARIABLES DE DECISION ===
    # x[v,l] = 1 si vente v achetee chez labo l
    x = {}

    # Coefficient objectif (remise totale)
    objective = solver.Objective()
    objective.SetMaximization()

    # Chiffre par labo (pour contraintes)
    chiffre_labo = {lid: solver.Sum([]) for lid in labo_ids}

    # Construire variables et contraintes
    for vente in ventes:
        quantite = vente.quantite_annuelle or 0
        if quantite <= 0:
            continue

        vars_vente = []  # Variables pour cette vente

        for labo_id in labo_ids:
            matching = matching_map.get((vente.id, labo_id))
            if not matching or not matching.produit_id:
                continue

            produit = produits_map.get(matching.produit_id)
            if not produit:
                continue

            # Verifier exclusion
            if produit.id in exclusions.get(labo_id, set()):
                continue

            # Creer variable
            var_name = f"x_{vente.id}_{labo_id}"
            x[(vente.id, labo_id)] = solver.BoolVar(var_name)
            var = x[(vente.id, labo_id)]
            vars_vente.append(var)

            # Prix et remise
            prix = float(produit.prix_ht or 0)
            remise_ligne = float(produit.remise_pct or 0)
            remise_nego = float(labos[labo_id].remise_negociee or 0)

            # Remise totale = max(remise_ligne, remise_negociee)
            # Simplification: on prend la remise negociee si > remise_ligne
            remise_effective = max(remise_ligne, remise_nego)

            montant = prix * quantite
            gain_remise = montant * remise_effective / 100

            # Coefficient objectif = gain remise
            objective.SetCoefficient(var, gain_remise)

            # Contribution au chiffre du labo
            chiffre_labo[labo_id] = solver.Sum([
                chiffre_labo[labo_id],
                var * montant
            ])

        # Contrainte: au plus 1 labo par vente
        if vars_vente:
            solver.Add(solver.Sum(vars_vente) <= 1)

    # === CONTRAINTES OBJECTIFS PAR LABO ===
    for obj in objectives:
        min_chiffre = float(obj.get_objectif_minimum())
        if min_chiffre > 0:
            solver.Add(chiffre_labo[obj.labo_id] >= min_chiffre)

    # === RESOLUTION ===
    optimizer_logger.info(f"Solving with {len(x)} variables...")
    status = solver.Solve()

    status_names = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }
    status_name = status_names.get(status, "UNKNOWN")

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return OptimizationResult(
            success=False,
            message=f"Pas de solution trouvee (status: {status_name}). "
                    "Les objectifs sont peut-etre trop eleves par rapport au potentiel.",
            repartition={},
            chiffre_total_ht=Decimal("0"),
            remise_totale=Decimal("0"),
            couverture_pct=0.0,
            solver_time_ms=solver.wall_time(),
            status=status_name
        )

    # === EXTRACTION RESULTATS ===
    repartition = {}
    chiffre_total = Decimal("0")
    remise_totale = Decimal("0")

    for obj in objectives:
        repartition[obj.labo_id] = {
            "labo_id": obj.labo_id,
            "labo_nom": obj.labo_nom,
            "ventes": [],
            "chiffre_ht": Decimal("0"),
            "remise_totale": Decimal("0"),
            "nb_produits": 0,
            "objectif_atteint": False,
            "objectif_minimum": obj.get_objectif_minimum(),
            "potentiel_ht": obj.potentiel_ht,
        }

    for (vente_id, labo_id), var in x.items():
        if var.solution_value() > 0.5:  # Variable selectionnee
            vente = next(v for v in ventes if v.id == vente_id)
            matching = matching_map.get((vente_id, labo_id))
            produit = produits_map.get(matching.produit_id) if matching else None

            if produit:
                quantite = vente.quantite_annuelle or 0
                prix = produit.prix_ht or Decimal("0")
                montant = prix * quantite

                remise_ligne = produit.remise_pct or Decimal("0")
                remise_nego = labos[labo_id].remise_negociee or Decimal("0")
                remise_effective = max(remise_ligne, remise_nego)
                gain = montant * remise_effective / 100

                repartition[labo_id]["ventes"].append({
                    "vente_id": vente_id,
                    "designation": vente.designation,
                    "produit_id": produit.id,
                    "produit_nom": produit.nom_commercial,
                    "quantite": quantite,
                    "prix_unitaire": float(prix),
                    "montant_ht": float(montant),
                    "remise_pct": float(remise_effective),
                    "gain_remise": float(gain),
                })
                repartition[labo_id]["chiffre_ht"] += montant
                repartition[labo_id]["remise_totale"] += gain
                repartition[labo_id]["nb_produits"] += 1

                chiffre_total += montant
                remise_totale += gain

    # Verifier objectifs atteints
    for obj in objectives:
        labo_data = repartition[obj.labo_id]
        labo_data["objectif_atteint"] = labo_data["chiffre_ht"] >= obj.get_objectif_minimum()

    # Calculer couverture
    chiffre_bdpm_total = sum(
        (v.prix_bdpm or Decimal("0")) * (v.quantite_annuelle or 0)
        for v in ventes
    )
    couverture = float(chiffre_total / chiffre_bdpm_total * 100) if chiffre_bdpm_total > 0 else 0.0

    return OptimizationResult(
        success=True,
        message=f"Solution {status_name} trouvee",
        repartition=repartition,
        chiffre_total_ht=chiffre_total,
        remise_totale=remise_totale,
        couverture_pct=round(couverture, 2),
        solver_time_ms=solver.wall_time(),
        status=status_name
    )
