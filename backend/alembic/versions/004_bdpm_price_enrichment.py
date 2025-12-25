"""Add BDPM price fields to mes_ventes

Revision ID: 004
Revises: 003
Create Date: 2024-12-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter colonnes BDPM a mes_ventes
    op.add_column('mes_ventes', sa.Column('prix_bdpm', sa.Numeric(10, 2), nullable=True))
    op.add_column('mes_ventes', sa.Column('has_bdpm_price', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('mes_ventes', sa.Column('groupe_generique_id', sa.Integer(), nullable=True))

    # Index pour matching rapide par groupe generique
    op.create_index('ix_mes_ventes_groupe_generique_id', 'mes_ventes', ['groupe_generique_id'])
    op.create_index('ix_mes_ventes_has_bdpm_price', 'mes_ventes', ['has_bdpm_price'])


def downgrade() -> None:
    op.drop_index('ix_mes_ventes_has_bdpm_price', 'mes_ventes')
    op.drop_index('ix_mes_ventes_groupe_generique_id', 'mes_ventes')
    op.drop_column('mes_ventes', 'groupe_generique_id')
    op.drop_column('mes_ventes', 'has_bdpm_price')
    op.drop_column('mes_ventes', 'prix_bdpm')
