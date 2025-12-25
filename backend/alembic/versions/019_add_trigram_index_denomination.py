"""Add GIN trigram index on denomination for fast fuzzy search

Revision ID: 019
Revises: 018
Create Date: 2025-12-24

This index dramatically improves performance of similarity searches
using pg_trgm (trigram matching) on the denomination column.
"""
from alembic import op

# revision identifiers
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create GIN trigram index on bdpm_equivalences.denomination
    # This enables fast LIKE, ILIKE, and similarity() operations
    # Note: Not using CONCURRENTLY as it cannot run inside a transaction
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_equivalences_denomination_trgm
        ON bdpm_equivalences
        USING gin (denomination gin_trgm_ops)
    """)

    # Also add trigram index on matching_memory.designation for ventes matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_matching_memory_designation_trgm
        ON matching_memory
        USING gin (designation gin_trgm_ops)
    """)

    # Add trigram index on catalogue_produits.nom_commercial for catalogue matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_catalogue_produits_nom_commercial_trgm
        ON catalogue_produits
        USING gin (nom_commercial gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_catalogue_produits_nom_commercial_trgm")
    op.execute("DROP INDEX IF EXISTS idx_matching_memory_designation_trgm")
    op.execute("DROP INDEX IF EXISTS idx_bdpm_equivalences_denomination_trgm")
