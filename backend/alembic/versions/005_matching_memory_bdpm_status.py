"""Add matching_memory and bdpm_file_status tables

Revision ID: 005
Revises: 004
Create Date: 2024-12-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table matching_memory - Memoire de matching persistante
    op.create_table(
        'matching_memory',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('groupe_equivalence_id', sa.Integer(), nullable=False, index=True),
        sa.Column('cip13', sa.String(13), nullable=False, unique=True, index=True),
        sa.Column('designation', sa.String(500), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('groupe_generique_id', sa.Integer(), nullable=True, index=True),
        sa.Column('match_origin', sa.String(100), nullable=True),
        sa.Column('match_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('validated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Table bdpm_file_status - Statut des fichiers BDPM
    op.create_table(
        'bdpm_file_status',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('filename', sa.String(100), nullable=False, unique=True),
        sa.Column('file_url', sa.String(500), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('last_checked', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_downloaded', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_integrated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_count', sa.Integer(), nullable=True),
        sa.Column('new_records', sa.Integer(), server_default='0'),
        sa.Column('removed_records', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Ajouter colonne absent_bdpm a bdpm_equivalences
    op.add_column('bdpm_equivalences', sa.Column('absent_bdpm', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('bdpm_equivalences', 'absent_bdpm')
    op.drop_table('bdpm_file_status')
    op.drop_table('matching_memory')
