"""Admin endpoints for system management.

This module provides endpoints for administrative tasks such as
refreshing materialized views and monitoring system status.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..services.materialized_views import MaterializedViewService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh-views")
async def refresh_materialized_views(db: Session = Depends(get_db)):
    """
    Refresh all materialized views.

    Use after a BDPM import or manually when needed.

    Returns:
        Dictionary with refresh results for each view
    """
    service = MaterializedViewService(db)
    results = service.refresh_all()
    return results


@router.post("/refresh-views/{view_name}")
async def refresh_specific_view(view_name: str, db: Session = Depends(get_db)):
    """
    Refresh a specific materialized view.

    Args:
        view_name: 'clusters' or 'matching_stats'

    Returns:
        Refresh result for the specified view
    """
    service = MaterializedViewService(db)

    if view_name == 'clusters':
        return service.refresh_clusters()
    elif view_name == 'matching_stats':
        return service.refresh_matching_stats()
    else:
        raise HTTPException(400, f"Unknown view: {view_name}. Use 'clusters' or 'matching_stats'")


@router.get("/views-stats")
async def get_views_stats(db: Session = Depends(get_db)):
    """
    Get statistics about materialized views.

    Returns:
        List of views with their sizes
    """
    service = MaterializedViewService(db)
    return service.get_stats()


@router.get("/views-status")
async def get_views_status(db: Session = Depends(get_db)):
    """
    Check if all expected materialized views exist.

    Returns:
        Dictionary with view names and existence status
    """
    service = MaterializedViewService(db)
    return service.check_views_exist()


@router.get("/cluster/{groupe_id}")
async def get_cluster_data(groupe_id: int, db: Session = Depends(get_db)):
    """
    Get pre-computed cluster data for a specific group.

    This endpoint is faster than /api/groupe/{id}/details as it
    uses the materialized view.

    Args:
        groupe_id: The generic group ID

    Returns:
        Cluster data from materialized view
    """
    service = MaterializedViewService(db)
    result = service.get_cluster_by_groupe(groupe_id)

    if not result:
        raise HTTPException(404, f"Cluster not found for groupe_id: {groupe_id}")

    return result
