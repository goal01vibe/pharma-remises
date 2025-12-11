"""Add VenteMatching table for intelligent matching results

Revision ID: 003
Revises: 002
Create Date: 2024-12-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table de mapping ventes -> produits catalogue par labo
    op.create_table(
        'vente_matching',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vente_id', sa.Integer(), nullable=False),
        sa.Column('labo_id', sa.Integer(), nullable=False),
        sa.Column('produit_id', sa.Integer(), nullable=True),
        sa.Column('match_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('match_type', sa.String(30), nullable=True),
        sa.Column('matched_on', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['vente_id'], ['mes_ventes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['labo_id'], ['laboratoires.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['produit_id'], ['catalogue_produits.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('vente_id', 'labo_id', name='uq_vente_labo')
    )

    # Index pour recherches rapides
    op.create_index('ix_vente_matching_vente_id', 'vente_matching', ['vente_id'])
    op.create_index('ix_vente_matching_labo_id', 'vente_matching', ['labo_id'])
    op.create_index('ix_vente_matching_produit_id', 'vente_matching', ['produit_id'])


def downgrade() -> None:
    op.drop_index('ix_vente_matching_produit_id', 'vente_matching')
    op.drop_index('ix_vente_matching_labo_id', 'vente_matching')
    op.drop_index('ix_vente_matching_vente_id', 'vente_matching')
    op.drop_table('vente_matching')
