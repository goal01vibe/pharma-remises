# PHASE 4 : Vues Materialisees

## Objectif
Creer les vues materialisees pour performance instantanee sur les requetes frequentes.

## Pre-requis
- Phase 1 terminee (tables existent)
- Phase 2 terminee (services disponibles)
- Phase 3 terminee (endpoints API fonctionnels)

---

## 4.1 Vue materialisee : Clusters d'equivalences

Cette vue pre-calcule tous les generiques equivalents par groupe BDPM.
Resultat instantane (<5ms) au lieu de recalculer a chaque requete.

**Migration** : `backend/alembic/versions/015_create_mv_clusters_equivalences.py`

```python
"""Create mv_clusters_equivalences materialized view

Revision ID: 015
"""
from alembic import op

def upgrade():
    op.execute("""
        -- Vue materialisee des clusters d'equivalences par groupe generique
        CREATE MATERIALIZED VIEW mv_clusters_equivalences AS
        SELECT
            groupe_generique_id,
            -- Princeps du groupe (CIP + nom)
            MAX(CASE WHEN type_generique = 0 THEN cip13 END) as princeps_cip13,
            MAX(CASE WHEN type_generique = 0 THEN denomination END) as princeps_ref,
            -- Tous les noms du groupe concatenes
            string_agg(DISTINCT denomination, ' | ' ORDER BY denomination) as equivalences,
            -- Tous les CIP du groupe
            string_agg(DISTINCT cip13, ', ' ORDER BY cip13) as cips,
            -- Nombre de laboratoires differents (utilise labo_extracted, fiable)
            count(DISTINCT labo_extracted) FILTER (WHERE labo_extracted IS NOT NULL) as nb_labos,
            -- Liste des labos du groupe
            string_agg(DISTINCT labo_extracted, ', ' ORDER BY labo_extracted)
                FILTER (WHERE labo_extracted IS NOT NULL) as labos_liste,
            -- Prix PFHT (tous identiques dans un groupe, on prend le max non-null)
            MAX(pfht) as pfht_groupe,
            -- Nombre total de references dans le groupe
            count(*) as nb_references,
            -- Date derniere MAJ du groupe
            MAX(created_at) as derniere_maj
        FROM bdpm_equivalences
        WHERE groupe_generique_id IS NOT NULL
        GROUP BY groupe_generique_id;

        -- Index pour recherche rapide par groupe
        CREATE UNIQUE INDEX idx_mv_clusters_groupe ON mv_clusters_equivalences(groupe_generique_id);
    """)

def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_clusters_equivalences")
```

---

## 4.2 Vue materialisee : Stats matching

Pour dashboard - rafraichie periodiquement.

**Migration** : `backend/alembic/versions/016_create_mv_matching_stats.py`

```python
"""Create mv_matching_stats materialized view

Revision ID: 016
"""
from alembic import op

def upgrade():
    op.execute("""
        -- Vue materialisee pour dashboard (rafraichie periodiquement)
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

        -- Index unique pour refresh concurrent
        CREATE UNIQUE INDEX idx_mv_matching_stats_type ON mv_matching_stats(match_type);
    """)

def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_matching_stats")
```

---

## 4.3 Index supplementaires pour performance

**Migration** : `backend/alembic/versions/017_add_performance_indexes.py`

```python
"""Add performance indexes

Revision ID: 017
"""
from alembic import op

def upgrade():
    # Index GIN sur denomination pour recherche fuzzy rapide
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_denomination_trgm
            ON bdpm_equivalences USING gin (denomination gin_trgm_ops);
    """)

    # Index GIN sur princeps_denomination
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bdpm_princeps_trgm
            ON bdpm_equivalences USING gin (princeps_denomination gin_trgm_ops);
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_bdpm_denomination_trgm")
    op.execute("DROP INDEX IF EXISTS idx_bdpm_princeps_trgm")
```

---

## 4.4 Fonction SQL de matching hybride

**Migration** : `backend/alembic/versions/018_create_find_best_match_function.py`

```python
"""Create find_best_match SQL function

Revision ID: 018
"""
from alembic import op

def upgrade():
    op.execute("""
        -- Fonction : Soundex (pre-filtre rapide) + Trigram (precision)
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
                -- Pre-filtre Soundex (elimine 95% des candidats)
                soundex(split_part(b.denomination, ' ', 1)) = soundex(split_part(search_term, ' ', 1))
                -- Filtre trigram
                AND b.denomination % search_term
            ORDER BY similarity(b.denomination, search_term) DESC
            LIMIT 5;
        END;
        $$ LANGUAGE plpgsql;
    """)

def downgrade():
    op.execute("DROP FUNCTION IF EXISTS find_best_match(TEXT)")
```

---

## 4.5 Service de refresh des vues

**Fichier** : `backend/app/services/materialized_views.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MaterializedViewService:
    """Service de gestion des vues materialisees."""

    def __init__(self, db: Session):
        self.db = db

    def refresh_clusters(self) -> dict:
        """
        Rafraichit la vue mv_clusters_equivalences.
        Appeler apres chaque import BDPM.
        """
        start = datetime.now()
        try:
            self.db.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_clusters_equivalences"
            ))
            self.db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"mv_clusters_equivalences rafraichie en {elapsed:.2f}s")
            return {"status": "success", "elapsed_seconds": elapsed}
        except Exception as e:
            logger.error(f"Erreur refresh mv_clusters_equivalences: {e}")
            return {"status": "error", "message": str(e)}

    def refresh_matching_stats(self) -> dict:
        """
        Rafraichit la vue mv_matching_stats.
        Appeler periodiquement (toutes les heures).
        """
        start = datetime.now()
        try:
            self.db.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_matching_stats"
            ))
            self.db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"mv_matching_stats rafraichie en {elapsed:.2f}s")
            return {"status": "success", "elapsed_seconds": elapsed}
        except Exception as e:
            logger.error(f"Erreur refresh mv_matching_stats: {e}")
            return {"status": "error", "message": str(e)}

    def refresh_all(self) -> dict:
        """Rafraichit toutes les vues materialisees."""
        results = {}
        results["clusters"] = self.refresh_clusters()
        results["matching_stats"] = self.refresh_matching_stats()
        return results

    def get_stats(self) -> dict:
        """Retourne des stats sur les vues materialisees."""
        result = self.db.execute(text("""
            SELECT
                schemaname,
                matviewname,
                pg_size_pretty(pg_relation_size(matviewname::text)) as size
            FROM pg_matviews
            WHERE schemaname = 'public'
        """)).fetchall()

        return [{"name": r.matviewname, "size": r.size} for r in result]
```

---

## 4.6 Endpoint pour refresh manuel

**Ajouter dans** : `backend/app/api/admin.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..services.materialized_views import MaterializedViewService

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/refresh-views")
async def refresh_materialized_views(db: Session = Depends(get_db)):
    """
    Rafraichit toutes les vues materialisees.
    A utiliser apres un import BDPM ou manuellement.
    """
    service = MaterializedViewService(db)
    results = service.refresh_all()
    return results

@router.get("/views-stats")
async def get_views_stats(db: Session = Depends(get_db)):
    """Retourne des stats sur les vues materialisees."""
    service = MaterializedViewService(db)
    return service.get_stats()
```

**Ajouter dans main.py** :
```python
from app.api.admin import router as admin_router
app.include_router(admin_router)
```

---

## 4.7 Integration avec import BDPM

**Modifier** : `backend/app/api/repertoire.py` (endpoint sync-bdpm)

Ajouter a la fin de la fonction sync_bdpm :

```python
# Rafraichir les vues materialisees apres import
from ..services.materialized_views import MaterializedViewService
mv_service = MaterializedViewService(db)
mv_service.refresh_clusters()
```

---

## Tests a effectuer

```bash
# Appliquer les migrations
cd backend
alembic upgrade head

# Verifier les vues
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "\dm+"

# Tester performance lookup
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
EXPLAIN ANALYZE
SELECT * FROM mv_clusters_equivalences WHERE groupe_generique_id = 1234;
"

# Tester refresh
curl -X POST http://localhost:8001/api/admin/refresh-views

# Tester stats
curl http://localhost:8001/api/admin/views-stats
```

---

## Criteres de validation Phase 4

- [ ] Migration 015 : `mv_clusters_equivalences` creee
- [ ] Migration 016 : `mv_matching_stats` creee
- [ ] Migration 017 : Index GIN crees
- [ ] Migration 018 : Fonction `find_best_match` creee
- [ ] Service `MaterializedViewService` fonctionne
- [ ] Endpoint `/api/admin/refresh-views` retourne 200
- [ ] Endpoint `/api/admin/views-stats` retourne liste
- [ ] Performance lookup < 5ms
- [ ] Refresh integre dans sync-bdpm
- [ ] `alembic upgrade head` passe sans erreur

---

## Apres cette phase

Merger feature/backend dans dev. Executer `/compact` puis passer a Phase 5 : `docs/architecture/PHASE5_FRONTEND.md`
