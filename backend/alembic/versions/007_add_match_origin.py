"""Add match_origin column to bdpm_equivalences

Revision ID: 007
Revises: 006
Create Date: 2025-12-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add match_origin column to track how the groupe_generique was assigned
    # Values: 'bdpm' (from BDPM import), 'fuzzy' (user validated fuzzy match)
    op.add_column('bdpm_equivalences', sa.Column('match_origin', sa.String(50), nullable=True))

    # Set default value for existing records to 'bdpm' if they have a groupe_generique_id
    op.execute("""
        UPDATE bdpm_equivalences
        SET match_origin = 'bdpm'
        WHERE groupe_generique_id IS NOT NULL AND match_origin IS NULL
    """)


def downgrade() -> None:
    op.drop_column('bdpm_equivalences', 'match_origin')
