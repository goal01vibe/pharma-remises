"""Prix (price) endpoints for price variations and history.

This module provides endpoints for tracking price changes and
displaying price variation alerts.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from ..db.database import get_db

router = APIRouter(prefix="/api/prix", tags=["prix"])


@router.get("/variations/stats")
async def get_price_variation_stats(db: Session = Depends(get_db)):
    """
    Get price variation statistics for the last 30 days.

    Used for the alert banner in the header showing significant
    price changes.

    Returns:
        Dictionary with:
        - total: Total number of significant variations
        - hausses: Number of price increases > 10%
        - baisses: Number of price decreases > 10%
        - variation_max: Maximum absolute variation percentage
    """
    result = db.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE variation_pct > 10) as hausses,
            COUNT(*) FILTER (WHERE variation_pct < -10) as baisses,
            MAX(ABS(variation_pct)) as variation_max
        FROM bdpm_prix_historique
        WHERE date_changement > NOW() - INTERVAL '30 days'
          AND ABS(variation_pct) > 10
    """)).fetchone()

    return {
        "total": result.total or 0,
        "hausses": result.hausses or 0,
        "baisses": result.baisses or 0,
        "variation_max": float(result.variation_max) if result.variation_max else 0
    }


@router.get("/historique/{cip13}")
async def get_price_history(cip13: str, db: Session = Depends(get_db)):
    """
    Get price history for a specific CIP13.

    Args:
        cip13: The CIP13 code

    Returns:
        List of price change records, most recent first
    """
    results = db.execute(text("""
        SELECT date_changement, pfht_ancien, pfht_nouveau, variation_pct, source_import
        FROM bdpm_prix_historique
        WHERE cip13 = :cip13
        ORDER BY date_changement DESC
        LIMIT 20
    """), {"cip13": cip13}).fetchall()

    return [dict(row._mapping) for row in results]


@router.get("/variations/recent")
async def get_recent_variations(
    min_variation: Optional[float] = 10.0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get recent significant price variations.

    Args:
        min_variation: Minimum absolute variation percentage (default 10%)
        limit: Maximum number of results

    Returns:
        List of recent price variations with product details
    """
    results = db.execute(text("""
        SELECT
            h.cip13,
            h.pfht_ancien,
            h.pfht_nouveau,
            h.variation_pct,
            h.date_changement,
            h.source_import,
            b.denomination,
            b.groupe_generique_id
        FROM bdpm_prix_historique h
        LEFT JOIN bdpm_equivalences b ON h.cip13 = b.cip13
        WHERE h.date_changement > NOW() - INTERVAL '30 days'
          AND ABS(h.variation_pct) >= :min_variation
        ORDER BY h.date_changement DESC
        LIMIT :limit
    """), {"min_variation": min_variation, "limit": limit}).fetchall()

    return [dict(row._mapping) for row in results]


@router.get("/alerte-count")
async def get_alert_count(db: Session = Depends(get_db)):
    """
    Count significant price variations for alert badge.

    Returns:
        Count of significant price changes in the last 30 days
    """
    count = db.execute(text("""
        SELECT COUNT(*)
        FROM bdpm_prix_historique
        WHERE date_changement > NOW() - INTERVAL '30 days'
          AND ABS(variation_pct) > 10
    """)).scalar()

    return {"count": count or 0}
