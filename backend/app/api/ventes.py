from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db import get_db
from app.models import MesVentes, Import
from app.schemas import MesVentesResponse, ImportResponse

router = APIRouter(prefix="/api/ventes", tags=["Ventes"])


@router.get("", response_model=List[MesVentesResponse])
def list_ventes(
    import_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Liste les ventes, optionnellement filtrees par import."""
    query = db.query(MesVentes).options(joinedload(MesVentes.presentation))

    if import_id:
        query = query.filter(MesVentes.import_id == import_id)

    return query.order_by(MesVentes.montant_annuel.desc()).limit(1000).all()


@router.get("/imports", response_model=List[ImportResponse])
def list_ventes_imports(db: Session = Depends(get_db)):
    """Liste les imports de type ventes reussis uniquement."""
    return (
        db.query(Import)
        .filter(Import.type_import == "ventes")
        .filter(Import.statut == "termine")  # Seulement les imports reussis
        .order_by(Import.created_at.desc())
        .all()
    )


@router.delete("/{vente_id}")
def delete_vente(vente_id: int, db: Session = Depends(get_db)):
    """Supprime une ligne de vente."""
    vente = db.query(MesVentes).filter(MesVentes.id == vente_id).first()
    if not vente:
        raise HTTPException(status_code=404, detail="Vente non trouvee")

    db.delete(vente)
    db.commit()

    return {"success": True, "message": f"Vente {vente_id} supprimee"}


@router.delete("/bulk/by-ids")
def delete_ventes_by_ids(
    vente_ids: List[int],
    db: Session = Depends(get_db)
):
    """Supprime plusieurs ventes par leurs IDs."""
    if not vente_ids:
        raise HTTPException(status_code=400, detail="Liste d'IDs vide")

    deleted = (
        db.query(MesVentes)
        .filter(MesVentes.id.in_(vente_ids))
        .delete(synchronize_session=False)
    )
    db.commit()

    return {"success": True, "deleted": deleted, "message": f"{deleted} ventes supprimees"}


# =====================
# GESTION VENTES INCOMPLETES (sans prix BDPM)
# =====================

@router.get("/incomplete", response_model=List[MesVentesResponse])
def list_incomplete_ventes(
    import_id: int = Query(..., description="ID de l'import"),
    db: Session = Depends(get_db)
):
    """Liste les ventes sans prix BDPM pour un import."""
    return (
        db.query(MesVentes)
        .options(joinedload(MesVentes.presentation))
        .filter(MesVentes.import_id == import_id)
        .filter(MesVentes.has_bdpm_price == False)
        .order_by(MesVentes.designation)
        .all()
    )


@router.get("/incomplete/count")
def count_incomplete_ventes(
    import_id: int = Query(..., description="ID de l'import"),
    db: Session = Depends(get_db)
):
    """Compte les ventes sans prix BDPM pour un import."""
    total = db.query(MesVentes).filter(MesVentes.import_id == import_id).count()
    incomplete = (
        db.query(MesVentes)
        .filter(MesVentes.import_id == import_id)
        .filter(MesVentes.has_bdpm_price == False)
        .count()
    )
    complete = total - incomplete

    return {
        "total": total,
        "complete": complete,
        "incomplete": incomplete,
        "completion_rate": round(complete / total * 100, 1) if total > 0 else 0
    }


@router.delete("/incomplete/bulk")
def delete_incomplete_ventes(
    import_id: int = Query(..., description="ID de l'import"),
    db: Session = Depends(get_db)
):
    """Supprime toutes les ventes sans prix BDPM pour un import."""
    deleted = (
        db.query(MesVentes)
        .filter(MesVentes.import_id == import_id)
        .filter(MesVentes.has_bdpm_price == False)
        .delete()
    )
    db.commit()

    return {"success": True, "deleted": deleted, "message": f"{deleted} ventes incompletes supprimees"}


@router.post("/re-enrich/{import_id}")
def re_enrich_ventes(import_id: int, db: Session = Depends(get_db)):
    """
    Re-execute l'enrichissement BDPM pour un import.
    Utile apres une mise a jour des donnees BDPM.
    """
    from app.services.bdpm_lookup import enrich_ventes_with_bdpm

    # Verifier que l'import existe
    import_obj = db.query(Import).filter(Import.id == import_id).first()
    if not import_obj:
        raise HTTPException(status_code=404, detail="Import non trouve")

    stats = enrich_ventes_with_bdpm(db, import_id)

    return {
        "success": True,
        "import_id": import_id,
        "stats": stats
    }
