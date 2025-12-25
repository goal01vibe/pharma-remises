"""Groupe (generic group) endpoints for drawer details.

This module provides endpoints for retrieving detailed information
about generic groups, including the princeps and all equivalents.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.database import get_db
from ..services.pharma_preprocessing import extract_labo_from_denomination

router = APIRouter(prefix="/api/groupe", tags=["groupe"])


@router.get("/{groupe_id}/details")
async def get_groupe_details(groupe_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information about a generic group for the drawer.

    Args:
        groupe_id: The generic group ID

    Returns:
        Dictionary containing:
        - groupe_id: The group ID
        - princeps: The reference product (type_generique=0) or None
        - equivalents: List of generic equivalents
        - stats: Statistics (nb_labos, nb_references)

    Raises:
        HTTPException 404: If group not found
    """
    # Query the bdpm_equivalences table
    equivalents = db.execute(
        text("""
            SELECT cip13, denomination, type_generique, pfht, conditionnement
            FROM bdpm_equivalences
            WHERE groupe_generique_id = :groupe_id
            ORDER BY type_generique ASC, conditionnement ASC, denomination ASC
        """),
        {"groupe_id": groupe_id}
    ).fetchall()

    if not equivalents:
        raise HTTPException(404, "Groupe non trouve")

    # Find the princeps and separate generics
    princeps = None
    generiques = []
    for eq in equivalents:
        item = {
            "cip13": eq.cip13,
            "denomination": eq.denomination,
            "pfht": float(eq.pfht) if eq.pfht else None,
            "type_generique": eq.type_generique,
            "labo": extract_labo_from_denomination(eq.denomination),
            "conditionnement": eq.conditionnement
        }
        if eq.type_generique == 0:
            princeps = item
        else:
            generiques.append(item)

    # Calculate stats
    labos = set(g['labo'] for g in generiques if g['labo'])

    return {
        "groupe_id": groupe_id,
        "princeps": princeps,
        "equivalents": generiques,
        "stats": {
            "nb_labos": len(labos),
            "nb_references": len(generiques) + (1 if princeps else 0)
        }
    }


@router.get("/{groupe_id}/membres")
async def get_groupe_membres(groupe_id: int, db: Session = Depends(get_db)):
    """
    Get all members of a generic group.

    Args:
        groupe_id: The generic group ID

    Returns:
        List of group members with their details
    """
    membres = db.execute(
        text("""
            SELECT cip13, denomination, type_generique, pfht, match_origin, conditionnement
            FROM bdpm_equivalences
            WHERE groupe_generique_id = :groupe_id
            ORDER BY type_generique ASC, conditionnement ASC, denomination ASC
        """),
        {"groupe_id": groupe_id}
    ).fetchall()

    return [
        {
            "cip13": m.cip13,
            "denomination": m.denomination,
            "type_generique": m.type_generique,
            "pfht": float(m.pfht) if m.pfht else None,
            "match_origin": m.match_origin,
            "labo": extract_labo_from_denomination(m.denomination),
            "conditionnement": m.conditionnement
        }
        for m in membres
    ]
