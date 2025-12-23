"""Create bdpm_blacklist table for permanently removed products

Revision ID: 013
Revises: 012
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create bdpm_blacklist table
    op.create_table(
        'bdpm_blacklist',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cip13', sa.String(13), nullable=False, unique=True),
        sa.Column('denomination', sa.Text(), nullable=True),
        sa.Column('raison_suppression', sa.String(50), nullable=True),
        sa.Column('supprime_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True)
    )

    # Create index on cip13 for fast lookups
    op.execute("""
        CREATE INDEX idx_blacklist_cip
        ON bdpm_blacklist(cip13);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_blacklist_cip;")
    op.drop_table('bdpm_blacklist')
