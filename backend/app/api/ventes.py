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
