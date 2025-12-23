"""Create mv_clusters_equivalences materialized view

Revision ID: 015
Revises: 014
Create Date: 2025-12-23
"""
from alembic import op

# revision identifiers
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Materialized view of equivalence clusters by generic group
    op.execute("""
        CREATE MATERIALIZED VIEW mv_clusters_equivalences AS
        SELECT
            groupe_generique_id,
            -- Princeps of the group (CIP + name)
            MAX(CASE WHEN type_generique = 0 THEN cip13 END) as princeps_cip13,
            MAX(CASE WHEN type_generique = 0 THEN denomination END) as princeps_ref,
            -- All names in the group concatenated
            string_agg(DISTINCT denomination, ' | ' ORDER BY denomination) as equivalences,
            -- All CIPs in the group
            string_agg(DISTINCT cip13, ', ' ORDER BY cip13) as cips,
            -- Number of different labs (using labo_extracted, reliable)
            count(DISTINCT labo_extracted) FILTER (WHERE labo_extracted IS NOT NULL) as nb_labos,
            -- List of labs in the group
            string_agg(DISTINCT labo_extracted, ', ' ORDER BY labo_extracted)
                FILTER (WHERE labo_extracted IS NOT NULL) as labos_liste,
            -- PFHT price (all identical in a group, take max non-null)
            MAX(pfht) as pfht_groupe,
            -- Total number of references in the group
            count(*) as nb_references,
            -- Last update date of the group
            MAX(created_at) as derniere_maj
        FROM bdpm_equivalences
        WHERE groupe_generique_id IS NOT NULL
        GROUP BY groupe_generique_id;
    """)

    # Index for fast lookup by group
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_clusters_groupe
        ON mv_clusters_equivalences(groupe_generique_id);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_clusters_equivalences")
