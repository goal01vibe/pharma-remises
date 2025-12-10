from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.db import get_db
from app.models import Presentation
from app.schemas import PresentationCreate, PresentationResponse

router = APIRouter(prefix="/api/presentations", tags=["Presentations"])


@router.get("", response_model=List[PresentationResponse])
def list_presentations(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Liste les presentations, avec recherche optionnelle."""
    query = db.query(Presentation)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Presentation.molecule.ilike(search_pattern),
                Presentation.code_interne.ilike(search_pattern),
                Presentation.dosage.ilike(search_pattern),
            )
        )

    return query.order_by(Presentation.molecule, Presentation.dosage).limit(500).all()


@router.get("/{presentation_id}", response_model=PresentationResponse)
def get_presentation(presentation_id: int, db: Session = Depends(get_db)):
    """Recupere une presentation par ID."""
    presentation = db.query(Presentation).filter(Presentation.id == presentation_id).first()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation non trouvee")
    return presentation


@router.post("", response_model=PresentationResponse)
def create_presentation(presentation: PresentationCreate, db: Session = Depends(get_db)):
    """Cree une nouvelle presentation."""
    # Verifier unicite du code_interne
    existing = db.query(Presentation).filter(
        Presentation.code_interne == presentation.code_interne
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce code interne existe deja")

    db_presentation = Presentation(**presentation.model_dump())
    db.add(db_presentation)
    db.commit()
    db.refresh(db_presentation)
    return db_presentation


@router.get("/search", response_model=List[PresentationResponse])
def search_presentations(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db)
):
    """Recherche de presentations pour le matching."""
    search_pattern = f"%{q}%"
    presentations = (
        db.query(Presentation)
        .filter(
            or_(
                Presentation.molecule.ilike(search_pattern),
                Presentation.code_interne.ilike(search_pattern),
            )
        )
        .order_by(Presentation.molecule)
        .limit(20)
        .all()
    )
    return presentations
