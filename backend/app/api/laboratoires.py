from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db import get_db
from app.models import Laboratoire, CatalogueProduit, RegleRemontee
from app.schemas import (
    LaboratoireCreate,
    LaboratoireUpdate,
    LaboratoireResponse,
    CatalogueProduitResponse,
    RegleRemonteeResponse,
)

router = APIRouter(prefix="/api/laboratoires", tags=["Laboratoires"])


@router.get("", response_model=List[LaboratoireResponse])
def list_laboratoires(db: Session = Depends(get_db)):
    """Liste tous les laboratoires."""
    return db.query(Laboratoire).order_by(Laboratoire.nom).all()


@router.get("/{labo_id}", response_model=LaboratoireResponse)
def get_laboratoire(labo_id: int, db: Session = Depends(get_db)):
    """Recupere un laboratoire par ID."""
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")
    return labo


@router.post("", response_model=LaboratoireResponse)
def create_laboratoire(labo: LaboratoireCreate, db: Session = Depends(get_db)):
    """Cree un nouveau laboratoire."""
    # Verifier unicite du nom
    existing = db.query(Laboratoire).filter(Laboratoire.nom == labo.nom).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un laboratoire avec ce nom existe deja")

    db_labo = Laboratoire(**labo.model_dump())
    db.add(db_labo)
    db.commit()
    db.refresh(db_labo)
    return db_labo


@router.put("/{labo_id}", response_model=LaboratoireResponse)
def update_laboratoire(labo_id: int, labo: LaboratoireUpdate, db: Session = Depends(get_db)):
    """Met a jour un laboratoire."""
    db_labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not db_labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    update_data = labo.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_labo, field, value)

    db.commit()
    db.refresh(db_labo)
    return db_labo


@router.delete("/{labo_id}")
def delete_laboratoire(labo_id: int, db: Session = Depends(get_db)):
    """Supprime un laboratoire."""
    db_labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not db_labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    db.delete(db_labo)
    db.commit()
    return {"message": "Laboratoire supprime"}


@router.get("/{labo_id}/catalogue", response_model=List[CatalogueProduitResponse])
def get_catalogue(labo_id: int, db: Session = Depends(get_db)):
    """Recupere le catalogue d'un laboratoire."""
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    produits = (
        db.query(CatalogueProduit)
        .filter(CatalogueProduit.laboratoire_id == labo_id)
        .order_by(CatalogueProduit.nom_commercial)
        .all()
    )
    return produits


@router.get("/{labo_id}/regles-remontee", response_model=List[RegleRemonteeResponse])
def get_regles_remontee(labo_id: int, db: Session = Depends(get_db)):
    """Recupere les regles de remontee d'un laboratoire."""
    labo = db.query(Laboratoire).filter(Laboratoire.id == labo_id).first()
    if not labo:
        raise HTTPException(status_code=404, detail="Laboratoire non trouve")

    regles = (
        db.query(RegleRemontee)
        .filter(RegleRemontee.laboratoire_id == labo_id)
        .order_by(RegleRemontee.created_at.desc())
        .all()
    )

    # Ajouter le count de produits
    result = []
    for regle in regles:
        regle_dict = {
            "id": regle.id,
            "laboratoire_id": regle.laboratoire_id,
            "nom_regle": regle.nom_regle,
            "type_regle": regle.type_regle,
            "remontee_pct": regle.remontee_pct,
            "created_at": regle.created_at,
            "produits_count": len(regle.produits),
        }
        result.append(regle_dict)

    return result
