"""Create bdpm_prix_historique table for price change tracking

Revision ID: 010
Revises: 009
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create bdpm_prix_historique table
    op.create_table(
        'bdpm_prix_historique',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cip13', sa.String(13), nullable=False),
        sa.Column('pfht_ancien', sa.Numeric(10, 4), nullable=True),
        sa.Column('pfht_nouveau', sa.Numeric(10, 4), nullable=True),
        sa.Column('variation_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('date_changement', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('source_import', sa.String(50), nullable=True)
    )

    # Create indexes for fast queries
    op.execute("""
        CREATE INDEX idx_prix_hist_cip
        ON bdpm_prix_historique(cip13);
    """)

    op.execute("""
        CREATE INDEX idx_prix_hist_date
        ON bdpm_prix_historique(date_changement DESC);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_prix_hist_date;")
    op.execute("DROP INDEX IF EXISTS idx_prix_hist_cip;")
    op.drop_table('bdpm_prix_historique')
