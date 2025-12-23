"""Add integrated_at column to bdpm_equivalences

Revision ID: 014
Revises: 013
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add integrated_at column to identify new entries
    op.add_column('bdpm_equivalences',
                  sa.Column('integrated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True))

    # Create index for sorting by integration date
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_integrated
        ON bdpm_equivalences(integrated_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bdpm_integrated;")
    op.drop_column('bdpm_equivalences', 'integrated_at')
