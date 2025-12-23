"""Cursor-based pagination helper for API endpoints.

This module provides utilities for implementing efficient cursor-based
pagination, which is more performant than offset-based pagination for
large datasets.
"""
from typing import TypeVar, Generic, List, Optional, Any
from pydantic import BaseModel
import base64
import json

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""
    items: List[Any]
    next_cursor: Optional[str] = None
    total_count: int


def encode_cursor(data: dict) -> str:
    """
    Encode a dictionary as a base64 cursor string.

    Args:
        data: Dictionary containing cursor data (e.g., {'last_id': 42})

    Returns:
        Base64-encoded cursor string
    """
    return base64.b64encode(json.dumps(data).encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """
    Decode a base64 cursor string to a dictionary.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        Dictionary containing cursor data, or empty dict if invalid
    """
    try:
        return json.loads(base64.b64decode(cursor.encode()).decode())
    except Exception:
        return {}


def paginate_query(query, cursor: Optional[str], limit: int, id_field: str = 'id'):
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        cursor: Optional cursor string from previous page
        limit: Maximum number of items to return
        id_field: Name of the ID field for cursor positioning

    Returns:
        Tuple of (items, next_cursor)
    """
    if cursor:
        cursor_data = decode_cursor(cursor)
        last_id = cursor_data.get('last_id')
        if last_id:
            # Get the entity from query
            entity = query.column_descriptions[0]['entity']
            query = query.filter(getattr(entity, id_field) > last_id)

    items = query.limit(limit + 1).all()

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        last_item = items[-1]
        next_cursor = encode_cursor({'last_id': getattr(last_item, id_field)})

    return items, next_cursor
