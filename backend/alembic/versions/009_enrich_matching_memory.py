"""Enrich matching_memory with additional columns for complete cache

Revision ID: 009
Revises: 008
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add matched_cip13 column
    op.add_column('matching_memory',
                  sa.Column('matched_cip13', sa.String(13), nullable=True))

    # Add matched_denomination column
    op.add_column('matching_memory',
                  sa.Column('matched_denomination', sa.Text(), nullable=True))

    # Add pfht column for price caching
    op.add_column('matching_memory',
                  sa.Column('pfht', sa.Numeric(10, 4), nullable=True))

    # Add matched_at timestamp
    op.add_column('matching_memory',
                  sa.Column('matched_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True))

    # Create indexes for fast lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_matching_matched_cip
        ON matching_memory(matched_cip13);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_matching_type
        ON matching_memory(match_origin);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_matching_score
        ON matching_memory(match_score DESC);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_matching_score;")
    op.execute("DROP INDEX IF EXISTS idx_matching_type;")
    op.execute("DROP INDEX IF EXISTS idx_matching_matched_cip;")
    op.drop_column('matching_memory', 'matched_at')
    op.drop_column('matching_memory', 'pfht')
    op.drop_column('matching_memory', 'matched_denomination')
    op.drop_column('matching_memory', 'matched_cip13')
