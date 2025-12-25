"""
API Optimisation Multi-Labos.

Endpoints pour configurer et executer l'optimisation de repartition
des achats entre plusieurs laboratoires.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

from app.db import get_db
from app.models import Laboratoire, CatalogueProduit, MesVentes, VenteMatching, Import
from app.services.optimizer import optimize_multi_labo, LaboObjective

router = APIRouter(prefix="/api/optimization", tags=["Optimization"])


# =====================
# SCHEMAS
# =====================

class LaboObjectiveInput(BaseModel):
    """Configuration objectif pour un labo."""
    labo_id: int
    # Objectif: soit % du potentiel, soit montant fixe (un seul)
    objectif_pct: Optional[float] = None  # Ex: 60 = 60% du potentiel
    objectif_montant: Optional[float] = None  # Ex: 30000 euros min
    # Exclusions: liste de produit_ids a exclure pour ce labo
    exclusions: Optional[list[int]] = None


class OptimizeRequest(BaseModel):
    """Request pour lancer l'optimisation."""
    import_id: int
    objectives: list[LaboObjectiveInput]
    max_time_seconds: int = 30


class LaboRepartitionResponse(BaseModel):
    """Repartition pour un labo."""
    labo_id: int
    labo_nom: str
    chiffre_ht: float
    remise_totale: float
    nb_produits: int
    objectif_atteint: bool
    objectif_minimum: float
    potentiel_ht: float
    # Details ventes (optionnel, peut etre gros)
    ventes: Optional[list[dict]] = None


class OptimizeResponse(BaseModel):
    """Response de l'optimisation."""
    success: bool
    message: str
    repartition: list[LaboRepartitionResponse]
    chiffre_total_ht: float
    remise_totale: float
    couverture_pct: float
    solver_time_ms: float
    status: str


# =====================
# ENDPOINTS
# =====================

@router.get("/labos-disponibles")
def get_labos_disponibles(
    import_id: int = Query(..., description="ID de l'import ventes"),
    db: Session = Depends(get_db)
):
    """
    Liste les labos disponibles pour l'optimisation.

    Un labo est disponible s'il a des matchings pour l'import donne.
    Retourne aussi le potentiel (chiffre max) par labo.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Recuperer les ventes de cet import
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente pour cet import")

    vente_ids = [v.id for v in ventes]

    # Trouver les labos qui ont des matchings
    from sqlalchemy import func

    matchings_by_labo = (
        db.query(
            VenteMatching.labo_id,
            func.count(VenteMatching.id).label("nb_matchings")
        )
        .filter(VenteMatching.vente_id.in_(vente_ids))
        .filter(VenteMatching.produit_id.isnot(None))
        .group_by(VenteMatching.labo_id)
        .all()
    )

    if not matchings_by_labo:
        return {
            "import_id": import_id,
            "labos": [],
            "message": "Aucun matching trouve. Lancez d'abord le matching."
        }

    labo_ids = [m.labo_id for m in matchings_by_labo]
    labos = db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()
    labo_map = {l.id: l for l in labos}

    # Calculer potentiel par labo
    results = []
    for matching_info in matchings_by_labo:
        labo_id = matching_info.labo_id
        labo = labo_map.get(labo_id)
        if not labo:
            continue

        # Calculer le potentiel (somme prix_ht * quantite pour tous les matchings)
        matchings = db.query(VenteMatching).filter(
            VenteMatching.vente_id.in_(vente_ids),
            VenteMatching.labo_id == labo_id,
            VenteMatching.produit_id.isnot(None)
        ).all()

        potentiel = Decimal("0")
        for m in matchings:
            vente = next((v for v in ventes if v.id == m.vente_id), None)
            if not vente:
                continue
            produit = db.query(CatalogueProduit).filter(
                CatalogueProduit.id == m.produit_id
            ).first()
            if produit and produit.prix_ht:
                potentiel += produit.prix_ht * (vente.quantite_annuelle or 0)

        results.append({
            "labo_id": labo_id,
            "labo_nom": labo.nom,
            "remise_negociee": float(labo.remise_negociee or 0),
            "nb_matchings": matching_info.nb_matchings,
            "potentiel_ht": float(potentiel),
        })

    # Trier par potentiel decroissant
    results.sort(key=lambda x: x["potentiel_ht"], reverse=True)

    return {
        "import_id": import_id,
        "nb_ventes": len(ventes),
        "labos": results
    }


@router.get("/produits-labo")
def get_produits_labo(
    import_id: int = Query(..., description="ID de l'import ventes"),
    labo_id: int = Query(..., description="ID du labo"),
    search: Optional[str] = Query(None, description="Recherche par nom (autocomplete)"),
    limit: int = Query(50, description="Nombre max de resultats"),
    db: Session = Depends(get_db)
):
    """
    Liste les produits d'un labo qui sont matches avec les ventes.

    Utile pour l'autocomplete des exclusions.
    """
    # Verifier le labo
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    # Recuperer les ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == import_id).all()
    if not ventes:
        return {"produits": []}

    vente_ids = [v.id for v in ventes]

    # Recuperer les matchings pour ce labo
    matchings = db.query(VenteMatching).filter(
        VenteMatching.vente_id.in_(vente_ids),
        VenteMatching.labo_id == labo_id,
        VenteMatching.produit_id.isnot(None)
    ).all()

    produit_ids = list(set(m.produit_id for m in matchings))

    # Recuperer les produits
    query = db.query(CatalogueProduit).filter(
        CatalogueProduit.id.in_(produit_ids)
    )

    # Filtre recherche
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            CatalogueProduit.nom_commercial.ilike(search_pattern)
        )

    produits = query.limit(limit).all()

    return {
        "labo_id": labo_id,
        "labo_nom": labo.nom,
        "produits": [
            {
                "id": p.id,
                "nom_commercial": p.nom_commercial,
                "code_cip": p.code_cip,
                "prix_ht": float(p.prix_ht or 0),
                "remise_pct": float(p.remise_pct or 0),
            }
            for p in produits
        ]
    }


@router.post("/run", response_model=OptimizeResponse)
def run_optimization(
    request: OptimizeRequest,
    include_ventes: bool = Query(False, description="Inclure details ventes dans response"),
    db: Session = Depends(get_db)
):
    """
    Execute l'optimisation multi-labos.

    Trouve la repartition optimale des achats entre les labos
    pour maximiser les remises tout en respectant les objectifs.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == request.import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Verifier les labos
    labo_ids = [obj.labo_id for obj in request.objectives]
    labos = db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()
    if len(labos) != len(labo_ids):
        missing = set(labo_ids) - {l.id for l in labos}
        raise HTTPException(status_code=404, detail=f"Labos non trouves: {missing}")

    # Convertir en LaboObjective
    objectives = []
    for obj_input in request.objectives:
        objectives.append(LaboObjective(
            labo_id=obj_input.labo_id,
            labo_nom="",  # Sera rempli par optimize_multi_labo
            objectif_pct=obj_input.objectif_pct,
            objectif_montant=Decimal(str(obj_input.objectif_montant)) if obj_input.objectif_montant else None,
            exclusions=obj_input.exclusions or []
        ))

    # Lancer l'optimisation
    result = optimize_multi_labo(
        db=db,
        import_id=request.import_id,
        objectives=objectives,
        max_time_seconds=request.max_time_seconds
    )

    # Convertir en response
    repartition_list = []
    for labo_id, data in result.repartition.items():
        rep = LaboRepartitionResponse(
            labo_id=labo_id,
            labo_nom=data["labo_nom"],
            chiffre_ht=float(data["chiffre_ht"]),
            remise_totale=float(data["remise_totale"]),
            nb_produits=data["nb_produits"],
            objectif_atteint=data["objectif_atteint"],
            objectif_minimum=float(data["objectif_minimum"]),
            potentiel_ht=float(data["potentiel_ht"]),
            ventes=data["ventes"] if include_ventes else None
        )
        repartition_list.append(rep)

    # Trier par chiffre HT decroissant
    repartition_list.sort(key=lambda x: x.chiffre_ht, reverse=True)

    return OptimizeResponse(
        success=result.success,
        message=result.message,
        repartition=repartition_list,
        chiffre_total_ht=float(result.chiffre_total_ht),
        remise_totale=float(result.remise_totale),
        couverture_pct=result.couverture_pct,
        solver_time_ms=result.solver_time_ms,
        status=result.status
    )


@router.post("/preview")
def preview_optimization(
    request: OptimizeRequest,
    db: Session = Depends(get_db)
):
    """
    Previsualise l'optimisation sans executer le solver.

    Retourne les potentiels et objectifs calcules pour validation.
    """
    # Verifier l'import
    import_obj = db.query(Import).filter(Import.id == request.import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    # Verifier les labos
    labo_ids = [obj.labo_id for obj in request.objectives]
    labos = db.query(Laboratoire).filter(Laboratoire.id.in_(labo_ids)).all()
    labo_map = {l.id: l for l in labos}

    # Recuperer ventes
    ventes = db.query(MesVentes).filter(MesVentes.import_id == request.import_id).all()
    if not ventes:
        raise HTTPException(status_code=404, detail="Aucune vente pour cet import")

    vente_ids = [v.id for v in ventes]

    # Calculer potentiels
    preview = []
    for obj_input in request.objectives:
        labo = labo_map.get(obj_input.labo_id)
        if not labo:
            continue

        # Matchings pour ce labo
        matchings = db.query(VenteMatching).filter(
            VenteMatching.vente_id.in_(vente_ids),
            VenteMatching.labo_id == obj_input.labo_id,
            VenteMatching.produit_id.isnot(None)
        ).all()

        potentiel = Decimal("0")
        nb_produits = 0
        for m in matchings:
            # Verifier exclusions
            if obj_input.exclusions and m.produit_id in obj_input.exclusions:
                continue

            vente = next((v for v in ventes if v.id == m.vente_id), None)
            if not vente:
                continue

            produit = db.query(CatalogueProduit).filter(
                CatalogueProduit.id == m.produit_id
            ).first()
            if produit and produit.prix_ht:
                potentiel += produit.prix_ht * (vente.quantite_annuelle or 0)
                nb_produits += 1

        # Calculer objectif minimum
        objectif_min = Decimal("0")
        if obj_input.objectif_montant:
            objectif_min = Decimal(str(obj_input.objectif_montant))
        elif obj_input.objectif_pct and potentiel > 0:
            objectif_min = potentiel * Decimal(str(obj_input.objectif_pct)) / 100

        preview.append({
            "labo_id": obj_input.labo_id,
            "labo_nom": labo.nom,
            "remise_negociee": float(labo.remise_negociee or 0),
            "potentiel_ht": float(potentiel),
            "nb_produits_matches": nb_produits,
            "nb_exclusions": len(obj_input.exclusions or []),
            "objectif_pct": obj_input.objectif_pct,
            "objectif_montant": float(obj_input.objectif_montant) if obj_input.objectif_montant else None,
            "objectif_minimum_calcule": float(objectif_min),
            "realisable": float(potentiel) >= float(objectif_min),
        })

    # Calculer totaux
    total_potentiel = sum(p["potentiel_ht"] for p in preview)
    total_objectif = sum(p["objectif_minimum_calcule"] for p in preview)
    tous_realisables = all(p["realisable"] for p in preview)

    return {
        "import_id": request.import_id,
        "nb_ventes": len(ventes),
        "labos": preview,
        "total_potentiel_ht": total_potentiel,
        "total_objectifs_ht": total_objectif,
        "tous_realisables": tous_realisables,
        "message": "Tous les objectifs sont realisables" if tous_realisables else "ATTENTION: Certains objectifs depassent le potentiel"
    }
