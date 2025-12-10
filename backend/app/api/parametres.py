from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db import get_db
from app.models import Parametre
from app.schemas import ParametreResponse, ParametreUpdate

router = APIRouter(prefix="/api/parametres", tags=["Parametres"])


@router.get("", response_model=List[ParametreResponse])
def list_parametres(db: Session = Depends(get_db)):
    """Liste tous les parametres."""
    return db.query(Parametre).all()


@router.get("/{cle}", response_model=ParametreResponse)
def get_parametre(cle: str, db: Session = Depends(get_db)):
    """Recupere un parametre par cle."""
    param = db.query(Parametre).filter(Parametre.cle == cle).first()
    if not param:
        raise HTTPException(status_code=404, detail="Parametre non trouve")
    return param


@router.put("/{cle}", response_model=ParametreResponse)
def update_parametre(cle: str, param: ParametreUpdate, db: Session = Depends(get_db)):
    """Met a jour un parametre."""
    db_param = db.query(Parametre).filter(Parametre.cle == cle).first()
    if not db_param:
        # Creer le parametre s'il n'existe pas
        db_param = Parametre(cle=cle, valeur=param.valeur)
        db.add(db_param)
    else:
        db_param.valeur = param.valeur

    db.commit()
    db.refresh(db_param)
    return db_param
