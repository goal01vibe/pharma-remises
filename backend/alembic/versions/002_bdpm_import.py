"""Add BDPM columns for generic groups import

Revision ID: 002
Revises: 001
Create Date: 2024-12-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter colonnes BDPM à catalogue_produits
    op.add_column('catalogue_produits', sa.Column('source', sa.String(20), server_default='bdpm', nullable=True))
    op.add_column('catalogue_produits', sa.Column('groupe_generique_id', sa.Integer(), nullable=True))
    op.add_column('catalogue_produits', sa.Column('libelle_groupe', sa.String(300), nullable=True))
    op.add_column('catalogue_produits', sa.Column('conditionnement', sa.Integer(), nullable=True))
    op.add_column('catalogue_produits', sa.Column('type_generique', sa.String(20), nullable=True))
    op.add_column('catalogue_produits', sa.Column('prix_fabricant', sa.Numeric(10, 2), nullable=True))
    op.add_column('catalogue_produits', sa.Column('code_cis', sa.String(20), nullable=True))

    # Index pour recherche par groupe générique
    op.create_index('ix_catalogue_produits_groupe_generique', 'catalogue_produits', ['groupe_generique_id'])
    op.create_index('ix_catalogue_produits_source', 'catalogue_produits', ['source'])

    # Table des groupes génériques (référentiel)
    op.create_table(
        'groupes_generiques',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('libelle', sa.String(300), nullable=True),
        sa.Column('molecule', sa.String(200), nullable=True),
        sa.Column('dosage', sa.String(100), nullable=True),
        sa.Column('nb_produits', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Marquer les produits existants comme 'manuel'
    op.execute("UPDATE catalogue_produits SET source = 'manuel' WHERE source IS NULL OR source = 'bdpm'")


def downgrade() -> None:
    op.drop_table('groupes_generiques')
    op.drop_index('ix_catalogue_produits_source', 'catalogue_produits')
    op.drop_index('ix_catalogue_produits_groupe_generique', 'catalogue_produits')
    op.drop_column('catalogue_produits', 'code_cis')
    op.drop_column('catalogue_produits', 'prix_fabricant')
    op.drop_column('catalogue_produits', 'type_generique')
    op.drop_column('catalogue_produits', 'conditionnement')
    op.drop_column('catalogue_produits', 'libelle_groupe')
    op.drop_column('catalogue_produits', 'groupe_generique_id')
    op.drop_column('catalogue_produits', 'source')
