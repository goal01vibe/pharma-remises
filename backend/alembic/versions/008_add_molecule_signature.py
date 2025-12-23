"""Add molecule_signature and labo_extracted columns to bdpm_equivalences

Revision ID: 008
Revises: 007
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostgreSQL extensions for fuzzy matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")

    # Add molecule_signature as a generated column
    # Extracts "AMLODIPINE 5 mg" from libelle_groupe "AMLODIPINE 5 mg - AMLOR 5 mg, comprime"
    op.execute("""
        ALTER TABLE bdpm_equivalences
        ADD COLUMN IF NOT EXISTS molecule_signature TEXT GENERATED ALWAYS AS (
            UPPER(TRIM(split_part(libelle_groupe, ' - ', 1)))
        ) STORED;
    """)

    # Add labo_extracted column for lab statistics
    op.add_column('bdpm_equivalences',
                  sa.Column('labo_extracted', sa.String(50), nullable=True))

    # Create trigram index for fast fuzzy search on signature
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_signature_trgm
        ON bdpm_equivalences USING gin (molecule_signature gin_trgm_ops);
    """)

    # Create index on labo_extracted for grouped stats
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_labo
        ON bdpm_equivalences(labo_extracted);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bdpm_labo;")
    op.execute("DROP INDEX IF EXISTS idx_bdpm_signature_trgm;")
    op.drop_column('bdpm_equivalences', 'labo_extracted')
    op.execute("ALTER TABLE bdpm_equivalences DROP COLUMN IF EXISTS molecule_signature;")
    # Note: We don't drop extensions as they might be used by other parts
