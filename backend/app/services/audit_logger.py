"""Audit logging service for tracking all system changes.

This module provides comprehensive audit logging with support for:
- User tracking (email, IP, user agent)
- Before/after values for changes
- JSONB metadata for flexible additional context
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Request
from typing import Optional, Dict, Any
import json


class AuditLogger:
    """
    Audit logging service.

    Records all significant events with full context for compliance
    and debugging purposes.

    Usage:
        logger = AuditLogger(db)
        logger.log(
            action='update_price',
            resource_type='bdpm_equivalence',
            resource_id='3400930000001',
            old_values={'pfht': 10.0},
            new_values={'pfht': 12.0}
        )
    """

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        description: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> None:
        """
        Record an audit event.

        Args:
            action: The action performed (e.g., 'create', 'update', 'delete')
            resource_type: Type of resource (e.g., 'bdpm_equivalence', 'vente')
            resource_id: Identifier of the affected resource
            description: Human-readable description of the event
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            metadata: Additional context as JSONB
            request: FastAPI request object for extracting user info
            status: Event status ('success', 'error', 'warning')
            error_message: Error details if status is 'error'
        """
        # Extract info from request if available
        user_email = None
        ip_address = None
        user_agent = None

        if request:
            user_email = getattr(request.state, 'user_email', None)
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get('user-agent')

        self.db.execute(
            text("""
                INSERT INTO audit_logs (
                    user_email, ip_address, user_agent,
                    action, resource_type, resource_id,
                    description, old_values, new_values, metadata,
                    status, error_message
                ) VALUES (
                    :user_email, :ip_address::inet, :user_agent,
                    :action, :resource_type, :resource_id,
                    :description, :old_values::jsonb, :new_values::jsonb, :metadata::jsonb,
                    :status, :error_message
                )
            """),
            {
                "user_email": user_email,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "description": description,
                "old_values": json.dumps(old_values) if old_values else None,
                "new_values": json.dumps(new_values) if new_values else None,
                "metadata": json.dumps(metadata) if metadata else None,
                "status": status,
                "error_message": error_message
            }
        )
        self.db.commit()

    def log_batch(
        self,
        action: str,
        resource_type: str,
        items: list[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> None:
        """
        Log a batch operation as a single audit entry.

        Args:
            action: The batch action (e.g., 'batch_update', 'bulk_import')
            resource_type: Type of resources affected
            items: List of affected items with their changes
            metadata: Additional context
            request: FastAPI request object
        """
        batch_metadata = metadata or {}
        batch_metadata['item_count'] = len(items)
        batch_metadata['items'] = items[:10]  # Only store first 10 for space

        self.log(
            action=action,
            resource_type=resource_type,
            description=f"Batch operation on {len(items)} items",
            metadata=batch_metadata,
            request=request
        )
