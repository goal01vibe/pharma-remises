"""Add performance indexes for fuzzy search

Revision ID: 017
Revises: 016
Create Date: 2025-12-23
"""
from alembic import op

# revision identifiers
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on denomination for fast fuzzy search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_denomination_trgm
        ON bdpm_equivalences USING gin (denomination gin_trgm_ops);
    """)

    # GIN index on princeps_denomination
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_princeps_trgm
        ON bdpm_equivalences USING gin (princeps_denomination gin_trgm_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bdpm_denomination_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_bdpm_princeps_trgm;")
