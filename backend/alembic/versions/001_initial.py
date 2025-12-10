"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Laboratoires
    op.create_table(
        'laboratoires',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(100), nullable=False),
        sa.Column('remise_negociee', sa.Numeric(5, 2), nullable=True),
        sa.Column('remise_ligne_defaut', sa.Numeric(5, 2), nullable=True),
        sa.Column('actif', sa.Boolean(), default=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nom')
    )
    op.create_index('ix_laboratoires_id', 'laboratoires', ['id'])

    # Presentations
    op.create_table(
        'presentations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_interne', sa.String(50), nullable=False),
        sa.Column('molecule', sa.String(200), nullable=False),
        sa.Column('dosage', sa.String(50), nullable=True),
        sa.Column('forme', sa.String(50), nullable=True),
        sa.Column('conditionnement', sa.Integer(), nullable=True),
        sa.Column('type_conditionnement', sa.String(20), nullable=True),
        sa.Column('classe_therapeutique', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_interne')
    )
    op.create_index('ix_presentations_id', 'presentations', ['id'])
    op.create_index('ix_presentations_code_interne', 'presentations', ['code_interne'])
    op.create_index('ix_presentations_molecule', 'presentations', ['molecule'])

    # Imports
    op.create_table(
        'imports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type_import', sa.String(50), nullable=False),
        sa.Column('nom_fichier', sa.String(200), nullable=True),
        sa.Column('laboratoire_id', sa.Integer(), nullable=True),
        sa.Column('nb_lignes_importees', sa.Integer(), nullable=True),
        sa.Column('nb_lignes_erreur', sa.Integer(), nullable=True),
        sa.Column('statut', sa.String(20), default='en_cours'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['laboratoire_id'], ['laboratoires.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_imports_id', 'imports', ['id'])

    # Catalogue Produits
    op.create_table(
        'catalogue_produits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('laboratoire_id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=True),
        sa.Column('code_cip', sa.String(20), nullable=True),
        sa.Column('code_acl', sa.String(20), nullable=True),
        sa.Column('nom_commercial', sa.String(200), nullable=True),
        sa.Column('prix_ht', sa.Numeric(10, 2), nullable=True),
        sa.Column('remise_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('remontee_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('actif', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['laboratoire_id'], ['laboratoires.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('laboratoire_id', 'code_cip', name='uq_labo_cip')
    )
    op.create_index('ix_catalogue_produits_id', 'catalogue_produits', ['id'])
    op.create_index('ix_catalogue_produits_code_cip', 'catalogue_produits', ['code_cip'])

    # Regles Remontee
    op.create_table(
        'regles_remontee',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('laboratoire_id', sa.Integer(), nullable=False),
        sa.Column('nom_regle', sa.String(100), nullable=False),
        sa.Column('type_regle', sa.String(20), nullable=False),
        sa.Column('remontee_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['laboratoire_id'], ['laboratoires.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_regles_remontee_id', 'regles_remontee', ['id'])

    # Regles Remontee Produits
    op.create_table(
        'regles_remontee_produits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('regle_id', sa.Integer(), nullable=False),
        sa.Column('produit_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['regle_id'], ['regles_remontee.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['produit_id'], ['catalogue_produits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('regle_id', 'produit_id', name='uq_regle_produit')
    )
    op.create_index('ix_regles_remontee_produits_id', 'regles_remontee_produits', ['id'])

    # Mes Ventes
    op.create_table(
        'mes_ventes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('import_id', sa.Integer(), nullable=True),
        sa.Column('presentation_id', sa.Integer(), nullable=True),
        sa.Column('code_cip_achete', sa.String(20), nullable=True),
        sa.Column('labo_actuel', sa.String(100), nullable=True),
        sa.Column('designation', sa.String(200), nullable=True),
        sa.Column('quantite_annuelle', sa.Integer(), nullable=True),
        sa.Column('prix_achat_unitaire', sa.Numeric(10, 2), nullable=True),
        sa.Column('montant_annuel', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['import_id'], ['imports.id']),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mes_ventes_id', 'mes_ventes', ['id'])

    # Correspondances Manuelles
    op.create_table(
        'correspondances_manuelles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=False),
        sa.Column('produit_id', sa.Integer(), nullable=False),
        sa.Column('cree_par', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.ForeignKeyConstraint(['produit_id'], ['catalogue_produits.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('presentation_id', 'produit_id', name='uq_presentation_produit')
    )
    op.create_index('ix_correspondances_manuelles_id', 'correspondances_manuelles', ['id'])

    # Scenarios
    op.create_table(
        'scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('laboratoire_id', sa.Integer(), nullable=False),
        sa.Column('remise_simulee', sa.Numeric(5, 2), nullable=True),
        sa.Column('import_ventes_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['laboratoire_id'], ['laboratoires.id']),
        sa.ForeignKeyConstraint(['import_ventes_id'], ['imports.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scenarios_id', 'scenarios', ['id'])

    # Resultats Simulation
    op.create_table(
        'resultats_simulation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('presentation_id', sa.Integer(), nullable=True),
        sa.Column('quantite', sa.Integer(), nullable=True),
        sa.Column('montant_ht', sa.Numeric(12, 2), nullable=True),
        sa.Column('disponible', sa.Boolean(), default=False),
        sa.Column('produit_id', sa.Integer(), nullable=True),
        sa.Column('remise_ligne', sa.Numeric(5, 2), nullable=True),
        sa.Column('montant_remise_ligne', sa.Numeric(12, 2), nullable=True),
        sa.Column('statut_remontee', sa.String(20), nullable=True),
        sa.Column('remontee_cible', sa.Numeric(5, 2), nullable=True),
        sa.Column('montant_remontee', sa.Numeric(12, 2), nullable=True),
        sa.Column('remise_totale', sa.Numeric(5, 2), nullable=True),
        sa.Column('montant_total_remise', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['presentation_id'], ['presentations.id']),
        sa.ForeignKeyConstraint(['produit_id'], ['catalogue_produits.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resultats_simulation_id', 'resultats_simulation', ['id'])

    # Parametres
    op.create_table(
        'parametres',
        sa.Column('cle', sa.String(50), nullable=False),
        sa.Column('valeur', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('cle')
    )

    # Insert default parametres
    op.execute("""
        INSERT INTO parametres (cle, valeur, description) VALUES
        ('seuil_grand_conditionnement', '60', 'Seuil pour classifier en grand conditionnement'),
        ('equivalence_petit', '28,30', 'Conditionnements equivalents petits'),
        ('equivalence_grand', '84,90,100', 'Conditionnements equivalents grands'),
        ('openai_model_default', 'gpt-4o-mini', 'Modele OpenAI par defaut'),
        ('openai_model_fallback', 'gpt-4o', 'Modele OpenAI de secours')
    """)


def downgrade() -> None:
    op.drop_table('parametres')
    op.drop_table('resultats_simulation')
    op.drop_table('scenarios')
    op.drop_table('correspondances_manuelles')
    op.drop_table('mes_ventes')
    op.drop_table('regles_remontee_produits')
    op.drop_table('regles_remontee')
    op.drop_table('catalogue_produits')
    op.drop_table('imports')
    op.drop_table('presentations')
    op.drop_table('laboratoires')
