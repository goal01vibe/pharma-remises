"""Create mv_matching_stats materialized view

Revision ID: 016
Revises: 015
Create Date: 2025-12-23
"""
from alembic import op

# revision identifiers
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Materialized view for dashboard (refreshed periodically)
    op.execute("""
        CREATE MATERIALIZED VIEW mv_matching_stats AS
        SELECT
            match_origin as match_type,
            COUNT(*) as total,
            AVG(match_score) as score_moyen,
            MIN(matched_at) as premier_match,
            MAX(matched_at) as dernier_match
        FROM matching_memory
        WHERE validated = true
        GROUP BY match_origin;
    """)

    # Unique index for concurrent refresh
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_matching_stats_type
        ON mv_matching_stats(match_type);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_matching_stats")
