"""Create pending_validations table for fuzzy match validation queue

Revision ID: 011
Revises: 010
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pending_validations table
    op.create_table(
        'pending_validations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('validation_type', sa.String(30), nullable=False),
        sa.Column('source_cip13', sa.String(13), nullable=True),
        sa.Column('source_designation', sa.Text(), nullable=True),
        sa.Column('proposed_cip13', sa.String(13), nullable=True),
        sa.Column('proposed_designation', sa.Text(), nullable=True),
        sa.Column('proposed_pfht', sa.Numeric(10, 4), nullable=True),
        sa.Column('proposed_groupe_id', sa.Integer(), nullable=True),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('auto_source', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=True),
        sa.Column('auto_validated', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('validated_at', sa.DateTime(), nullable=True)
    )

    # Create indexes for fast queries
    op.execute("""
        CREATE INDEX idx_pending_status
        ON pending_validations(status);
    """)

    op.execute("""
        CREATE INDEX idx_pending_type
        ON pending_validations(validation_type);
    """)

    op.execute("""
        CREATE INDEX idx_pending_created
        ON pending_validations(created_at);
    """)

    op.execute("""
        CREATE INDEX idx_pending_auto
        ON pending_validations(auto_validated);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pending_auto;")
    op.execute("DROP INDEX IF EXISTS idx_pending_created;")
    op.execute("DROP INDEX IF EXISTS idx_pending_type;")
    op.execute("DROP INDEX IF EXISTS idx_pending_status;")
    op.drop_table('pending_validations')
