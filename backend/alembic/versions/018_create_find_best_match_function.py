"""Create find_best_match SQL function

Revision ID: 018
Revises: 017
Create Date: 2025-12-23
"""
from alembic import op

# revision identifiers
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hybrid matching function: Soundex (fast pre-filter) + Trigram (precision)
    op.execute("""
        CREATE OR REPLACE FUNCTION find_best_match(search_term TEXT)
        RETURNS TABLE(cip13 VARCHAR, denomination TEXT, score FLOAT) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                b.cip13,
                b.denomination,
                similarity(b.denomination, search_term)::FLOAT AS score
            FROM bdpm_equivalences b
            WHERE
                -- Soundex pre-filter (eliminates 95% of candidates)
                soundex(split_part(b.denomination, ' ', 1)) = soundex(split_part(search_term, ' ', 1))
                -- Trigram filter
                AND b.denomination % search_term
            ORDER BY similarity(b.denomination, search_term) DESC
            LIMIT 5;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS find_best_match(TEXT)")
