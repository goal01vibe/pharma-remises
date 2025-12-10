from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db import get_db
from app.models import CatalogueProduit
from app.schemas import (
    CatalogueProduitCreate,
    CatalogueProduitUpdate,
    CatalogueProduitResponse,
)

router = APIRouter(prefix="/api/catalogue", tags=["Catalogue"])


@router.get("", response_model=List[CatalogueProduitResponse])
def list_catalogue(
    laboratoire_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Liste les produits du catalogue, optionnellement filtre par labo."""
    query = db.query(CatalogueProduit).options(joinedload(CatalogueProduit.presentation))

    if laboratoire_id:
        query = query.filter(CatalogueProduit.laboratoire_id == laboratoire_id)

    return query.order_by(CatalogueProduit.nom_commercial).limit(1000).all()


@router.get("/{produit_id}", response_model=CatalogueProduitResponse)
def get_produit(produit_id: int, db: Session = Depends(get_db)):
    """Recupere un produit par ID."""
    produit = (
        db.query(CatalogueProduit)
        .options(joinedload(CatalogueProduit.presentation))
        .filter(CatalogueProduit.id == produit_id)
        .first()
    )
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")
    return produit


@router.post("", response_model=CatalogueProduitResponse)
def create_produit(produit: CatalogueProduitCreate, db: Session = Depends(get_db)):
    """Cree un nouveau produit dans le catalogue."""
    db_produit = CatalogueProduit(**produit.model_dump())
    db.add(db_produit)
    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.put("/{produit_id}", response_model=CatalogueProduitResponse)
def update_produit(
    produit_id: int,
    produit: CatalogueProduitUpdate,
    db: Session = Depends(get_db)
):
    """Met a jour un produit."""
    db_produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == produit_id).first()
    if not db_produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    update_data = produit.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_produit, field, value)

    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.patch("/{produit_id}/remontee", response_model=CatalogueProduitResponse)
def update_remontee(
    produit_id: int,
    remontee_pct: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Met a jour le pourcentage de remontee d'un produit."""
    db_produit = db.query(CatalogueProduit).filter(CatalogueProduit.id == produit_id).first()
    if not db_produit:
        raise HTTPException(status_code=404, detail="Produit non trouve")

    db_produit.remontee_pct = remontee_pct
    db.commit()
    db.refresh(db_produit)
    return db_produit


@router.patch("/bulk/remontee")
def bulk_update_remontee(
    ids: List[int],
    remontee_pct: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Met a jour le pourcentage de remontee de plusieurs produits."""
    db.query(CatalogueProduit).filter(CatalogueProduit.id.in_(ids)).update(
        {"remontee_pct": remontee_pct},
        synchronize_session=False
    )
    db.commit()
    return {"message": f"{len(ids)} produits mis a jour"}
