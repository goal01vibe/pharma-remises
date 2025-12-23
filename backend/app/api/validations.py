"""Validations endpoints for managing pending match validations.

This module provides endpoints for viewing and managing pending validations
that require user review (e.g., fuzzy matches below auto-validation threshold).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..db.database import get_db
from ..services.audit_logger import AuditLogger
from .pagination import encode_cursor, decode_cursor

router = APIRouter(prefix="/api/validations", tags=["validations"])


class ValidationItem(BaseModel):
    """Model for a validation item."""
    id: int
    validation_type: str
    source_cip13: Optional[str]
    source_designation: Optional[str]
    proposed_cip13: Optional[str]
    proposed_designation: Optional[str]
    proposed_pfht: Optional[float]
    match_score: Optional[float]
    status: str
    auto_validated: bool
    created_at: datetime


class ValidateRequest(BaseModel):
    """Request model for bulk validation actions."""
    ids: List[int]
    action: str  # 'validate' or 'reject'


@router.get("/pending")
async def get_pending_validations(
    validation_type: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List pending validations with cursor-based pagination.

    Args:
        validation_type: Optional filter by validation type
        cursor: Pagination cursor from previous request
        limit: Maximum items per page (default 50)

    Returns:
        Paginated list of pending validations
    """
    query = """
        SELECT id, validation_type, source_cip13, source_designation,
               proposed_cip13, proposed_designation, proposed_pfht,
               match_score, status, auto_validated, created_at
        FROM pending_validations
        WHERE status = 'pending'
    """
    params = {}

    if validation_type:
        query += " AND validation_type = :validation_type"
        params["validation_type"] = validation_type

    if cursor:
        cursor_data = decode_cursor(cursor)
        if cursor_data.get('last_id'):
            query += " AND id > :last_id"
            params["last_id"] = cursor_data['last_id']

    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit + 1

    results = db.execute(text(query), params).fetchall()

    items = results[:limit]
    next_cursor = None
    if len(results) > limit:
        next_cursor = encode_cursor({'last_id': items[-1].id})

    # Count total
    count_query = "SELECT COUNT(*) FROM pending_validations WHERE status = 'pending'"
    if validation_type:
        count_query += f" AND validation_type = '{validation_type}'"
    total = db.execute(text(count_query)).scalar()

    return {
        "items": [dict(row._mapping) for row in items],
        "next_cursor": next_cursor,
        "total_count": total
    }


@router.get("/stats")
async def get_validation_stats(db: Session = Depends(get_db)):
    """
    Get validation statistics grouped by type.

    Returns:
        Dictionary with stats for each validation type:
        - pending: Count of pending validations
        - validated: Count of validated items
        - rejected: Count of rejected items
        - auto_validated: Count of auto-validated items
    """
    result = db.execute(text("""
        SELECT
            validation_type,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'validated') as validated,
            COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
            COUNT(*) FILTER (WHERE auto_validated = true) as auto_validated
        FROM pending_validations
        GROUP BY validation_type
    """)).fetchall()

    return {row.validation_type: {
        "pending": row.pending,
        "validated": row.validated,
        "rejected": row.rejected,
        "auto_validated": row.auto_validated
    } for row in result}


@router.post("/bulk-action")
async def bulk_validate(
    request_data: ValidateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Validate or reject multiple validations in bulk.

    Args:
        request_data: Contains list of IDs and action ('validate' or 'reject')

    Returns:
        Count of updated items and new status

    Raises:
        HTTPException 400: If action is invalid
    """
    audit = AuditLogger(db)

    if request_data.action == 'validate':
        new_status = 'validated'
    elif request_data.action == 'reject':
        new_status = 'rejected'
    else:
        raise HTTPException(400, "Action invalide. Utilisez 'validate' ou 'reject'")

    db.execute(
        text("""
            UPDATE pending_validations
            SET status = :status, validated_at = NOW()
            WHERE id = ANY(:ids)
        """),
        {"status": new_status, "ids": request_data.ids}
    )
    db.commit()

    audit.log(
        action=request_data.action,
        resource_type="validation",
        description=f"{len(request_data.ids)} validations {new_status}",
        metadata={"ids": request_data.ids},
        request=request
    )

    return {"updated": len(request_data.ids), "status": new_status}


@router.get("/count-pending")
async def count_pending(db: Session = Depends(get_db)):
    """
    Count the number of pending validations.

    Used for the badge in the header.

    Returns:
        Dictionary with count of pending validations
    """
    count = db.execute(
        text("SELECT COUNT(*) FROM pending_validations WHERE status = 'pending'")
    ).scalar()
    return {"count": count}


@router.get("/{validation_id}")
async def get_validation_detail(validation_id: int, db: Session = Depends(get_db)):
    """
    Get details of a specific validation.

    Args:
        validation_id: The validation ID

    Returns:
        Full validation details

    Raises:
        HTTPException 404: If validation not found
    """
    result = db.execute(
        text("""
            SELECT id, validation_type, source_cip13, source_designation,
                   proposed_cip13, proposed_designation, proposed_pfht,
                   proposed_groupe_id, match_score, auto_source,
                   status, auto_validated, created_at, validated_at
            FROM pending_validations
            WHERE id = :id
        """),
        {"id": validation_id}
    ).fetchone()

    if not result:
        raise HTTPException(404, "Validation non trouvee")

    return dict(result._mapping)
