"""Add denomination column to bdpm_equivalences

Revision ID: 006
Revises: 005
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add denomination column (full drug name from CIS_bdpm.txt)
    op.add_column('bdpm_equivalences', sa.Column('denomination', sa.String(500), nullable=True))

    # Add princeps_denomination column (name of the princeps for this generic group)
    op.add_column('bdpm_equivalences', sa.Column('princeps_denomination', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('bdpm_equivalences', 'princeps_denomination')
    op.drop_column('bdpm_equivalences', 'denomination')
