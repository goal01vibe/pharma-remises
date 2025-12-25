# PHASE 1 : Migrations et Index Database

## Objectif
Creer toutes les tables et index necessaires pour le systeme de matching optimise.

## Pre-requis
- PostgreSQL running sur port 5433
- DB de test : `pharma_remises_test`
- Extensions : `pg_trgm`, `fuzzystrmatch`

---

## 1.1 Activer les extensions PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
```

---

## 1.2 Migration : molecule_signature (colonne calculee)

**Fichier** : `backend/alembic/versions/008_add_molecule_signature.py`

```sql
-- Ajouter colonne calculee pour signature moleculaire
-- Extrait "AMLODIPINE 5 mg" depuis libelle_groupe "AMLODIPINE 5 mg - AMLOR 5 mg, comprime"
ALTER TABLE bdpm_equivalences
ADD COLUMN molecule_signature TEXT GENERATED ALWAYS AS (
    UPPER(TRIM(split_part(libelle_groupe, ' - ', 1)))
) STORED;

-- Ajouter colonne labo extrait depuis denomination
ALTER TABLE bdpm_equivalences
ADD COLUMN labo_extracted VARCHAR(50);

-- Index trigram pour recherche fuzzy rapide sur signature
CREATE INDEX idx_bdpm_signature_trgm ON bdpm_equivalences
    USING gin (molecule_signature gin_trgm_ops);

-- Index sur labo extrait pour stats groupees
CREATE INDEX idx_bdpm_labo ON bdpm_equivalences(labo_extracted);
```

---

## 1.3 Migration : enrichir matching_memory

**Fichier** : `backend/alembic/versions/009_enrich_matching_memory.py`

```sql
-- Enrichir matching_memory avec les colonnes manquantes pour le cache complet
ALTER TABLE matching_memory
ADD COLUMN IF NOT EXISTS matched_cip13 VARCHAR(13),
ADD COLUMN IF NOT EXISTS matched_denomination TEXT,
ADD COLUMN IF NOT EXISTS pfht DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS matched_at TIMESTAMP DEFAULT NOW();

-- Index supplementaires pour lookups rapides
CREATE INDEX IF NOT EXISTS idx_matching_matched_cip ON matching_memory(matched_cip13);
CREATE INDEX IF NOT EXISTS idx_matching_type ON matching_memory(match_origin);
CREATE INDEX IF NOT EXISTS idx_matching_score ON matching_memory(match_score DESC);
```

---

## 1.4 Migration : bdpm_prix_historique

**Fichier** : `backend/alembic/versions/010_create_bdpm_prix_historique.py`

```sql
-- Historique des changements de prix BDPM
CREATE TABLE bdpm_prix_historique (
    id SERIAL PRIMARY KEY,
    cip13 VARCHAR(13) NOT NULL,
    pfht_ancien DECIMAL(10,4),
    pfht_nouveau DECIMAL(10,4),
    variation_pct DECIMAL(5,2),
    date_changement TIMESTAMP DEFAULT NOW(),
    source_import VARCHAR(50)
);

-- Index pour requetes rapides
CREATE INDEX idx_prix_hist_cip ON bdpm_prix_historique(cip13);
CREATE INDEX idx_prix_hist_date ON bdpm_prix_historique(date_changement DESC);
```

---

## 1.5 Migration : pending_validations

**Fichier** : `backend/alembic/versions/011_create_pending_validations.py`

```sql
-- Validations en attente
CREATE TABLE pending_validations (
    id SERIAL PRIMARY KEY,
    validation_type VARCHAR(30) NOT NULL,
    source_cip13 VARCHAR(13),
    source_designation TEXT,
    proposed_cip13 VARCHAR(13),
    proposed_designation TEXT,
    proposed_pfht DECIMAL(10,4),
    proposed_groupe_id INT,
    match_score FLOAT,
    auto_source VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    auto_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP
);

CREATE INDEX idx_pending_status ON pending_validations(status);
CREATE INDEX idx_pending_type ON pending_validations(validation_type);
CREATE INDEX idx_pending_created ON pending_validations(created_at);
CREATE INDEX idx_pending_auto ON pending_validations(auto_validated);
```

---

## 1.6 Migration : audit_logs

**Fichier** : `backend/alembic/versions/012_create_audit_logs.py`

```sql
-- Table centrale des logs d'audit
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_id UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    user_id INT,
    user_email VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    description TEXT,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT
);

-- Index pour requetes frequentes
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_user ON audit_logs(user_email);
CREATE INDEX idx_audit_status ON audit_logs(status);
CREATE INDEX idx_audit_metadata ON audit_logs USING gin(metadata);
```

---

## 1.7 Migration : bdpm_blacklist

**Fichier** : `backend/alembic/versions/013_create_bdpm_blacklist.py`

```sql
-- Blacklist BDPM (produits supprimes definitivement)
CREATE TABLE bdpm_blacklist (
    id SERIAL PRIMARY KEY,
    cip13 VARCHAR(13) UNIQUE NOT NULL,
    denomination TEXT,
    raison_suppression VARCHAR(50),
    supprime_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_blacklist_cip ON bdpm_blacklist(cip13);
```

---

## 1.8 Migration : integrated_at sur bdpm_equivalence

**Fichier** : `backend/alembic/versions/014_add_integrated_at.py`

```sql
-- Colonne pour identifier les nouvelles entrees
ALTER TABLE bdpm_equivalence
ADD COLUMN IF NOT EXISTS integrated_at TIMESTAMP DEFAULT NOW();

-- Index pour tri par date d'integration
CREATE INDEX idx_bdpm_integrated ON bdpm_equivalence(integrated_at DESC);
```

---

## Tests a effectuer

### Test 1 : Appliquer les migrations

```bash
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/pharma_remises_test alembic upgrade head
```

### Test 2 : Verifier les extensions

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "SELECT * FROM pg_extension WHERE extname IN ('pg_trgm', 'fuzzystrmatch');"
# Doit retourner 2 lignes
```

### Test 3 : Verifier les nouvelles tables

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('bdpm_prix_historique', 'pending_validations', 'audit_logs', 'bdpm_blacklist')
ORDER BY table_name;"
# Doit retourner 4 tables
```

### Test 4 : Verifier les colonnes ajoutees a bdpm_equivalences

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'bdpm_equivalences'
AND column_name IN ('molecule_signature', 'labo_extracted', 'integrated_at');"
# Doit retourner 3 colonnes
```

### Test 5 : Verifier les colonnes ajoutees a matching_memory

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'matching_memory'
AND column_name IN ('matched_cip13', 'matched_denomination', 'pfht', 'matched_at');"
# Doit retourner 4 colonnes
```

### Test 6 : Verifier les index crees

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%'
ORDER BY indexname;"
# Doit retourner tous les index idx_*
```

### Test 7 : Verifier que l'index trigram fonctionne

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
SELECT 'AMLODIPINE' % 'AMLODIPIN' AS trigram_test;"
# Doit retourner true (t)
```

### Test 8 : Verifier la structure de pending_validations

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
INSERT INTO pending_validations (validation_type, source_cip13, match_score, status)
VALUES ('fuzzy_match', '3400930000001', 85.5, 'pending') RETURNING id;"
# Doit retourner un ID

docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
DELETE FROM pending_validations WHERE source_cip13 = '3400930000001';"
```

### Test 9 : Verifier la structure de audit_logs

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
INSERT INTO audit_logs (action, resource_type, description, metadata)
VALUES ('test', 'migration', 'Test Phase 1', '{\"test\": true}'::jsonb) RETURNING id, event_id;"
# Doit retourner un ID et un UUID

docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
DELETE FROM audit_logs WHERE action = 'test';"
```

### Test 10 : Verifier bdpm_blacklist contrainte unique

```bash
docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
INSERT INTO bdpm_blacklist (cip13, denomination, raison_suppression)
VALUES ('3400930000001', 'TEST PRODUIT', 'test');"

docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
INSERT INTO bdpm_blacklist (cip13, denomination, raison_suppression)
VALUES ('3400930000001', 'TEST PRODUIT 2', 'test');" 2>&1 | grep -q "duplicate key" && echo "UNIQUE constraint OK"

docker exec -it pharma-remises-db-1 psql -U postgres -d pharma_remises_test -c "
DELETE FROM bdpm_blacklist WHERE cip13 = '3400930000001';"
```

---

## Script de test automatise

**Fichier** : `backend/tests/test_phase1_migrations.py`

```python
"""Tests Phase 1 - Migrations Database"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

class TestPhase1Migrations:
    """Verification complete des migrations Phase 1."""

    def test_extensions_installed(self, db: Session):
        """Verifie que pg_trgm et fuzzystrmatch sont installes."""
        result = db.execute(text(
            "SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'fuzzystrmatch')"
        )).fetchall()
        extensions = [r[0] for r in result]
        assert 'pg_trgm' in extensions, "Extension pg_trgm manquante"
        assert 'fuzzystrmatch' in extensions, "Extension fuzzystrmatch manquante"

    def test_table_bdpm_prix_historique_exists(self, db: Session):
        """Verifie que la table bdpm_prix_historique existe avec les bonnes colonnes."""
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'bdpm_prix_historique'
        """)).fetchall()
        columns = [r[0] for r in result]
        assert 'cip13' in columns
        assert 'pfht_ancien' in columns
        assert 'pfht_nouveau' in columns
        assert 'variation_pct' in columns
        assert 'date_changement' in columns

    def test_table_pending_validations_exists(self, db: Session):
        """Verifie que la table pending_validations existe."""
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'pending_validations'
        """)).fetchall()
        columns = [r[0] for r in result]
        assert 'validation_type' in columns
        assert 'source_cip13' in columns
        assert 'match_score' in columns
        assert 'auto_validated' in columns
        assert 'status' in columns

    def test_table_audit_logs_exists(self, db: Session):
        """Verifie que la table audit_logs existe avec JSONB."""
        result = db.execute(text("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'audit_logs'
        """)).fetchall()
        columns = {r[0]: r[1] for r in result}
        assert 'event_id' in columns
        assert 'action' in columns
        assert 'metadata' in columns
        assert columns.get('metadata') == 'jsonb'

    def test_table_bdpm_blacklist_exists(self, db: Session):
        """Verifie que la table bdpm_blacklist existe avec contrainte unique."""
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'bdpm_blacklist'
        """)).fetchall()
        columns = [r[0] for r in result]
        assert 'cip13' in columns
        assert 'raison_suppression' in columns

    def test_bdpm_equivalences_new_columns(self, db: Session):
        """Verifie les nouvelles colonnes sur bdpm_equivalences."""
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'bdpm_equivalences'
            AND column_name IN ('molecule_signature', 'labo_extracted', 'integrated_at')
        """)).fetchall()
        columns = [r[0] for r in result]
        assert len(columns) >= 2, f"Colonnes manquantes, trouvees: {columns}"

    def test_matching_memory_enriched(self, db: Session):
        """Verifie les colonnes enrichies sur matching_memory."""
        result = db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'matching_memory'
            AND column_name IN ('matched_cip13', 'matched_denomination', 'pfht', 'matched_at')
        """)).fetchall()
        columns = [r[0] for r in result]
        assert 'matched_cip13' in columns
        assert 'pfht' in columns

    def test_indexes_created(self, db: Session):
        """Verifie que les index critiques existent."""
        result = db.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public'
        """)).fetchall()
        indexes = [r[0] for r in result]
        # Verifier quelques index critiques
        critical_indexes = [
            'idx_pending_status',
            'idx_audit_created',
            'idx_blacklist_cip'
        ]
        for idx in critical_indexes:
            assert idx in indexes, f"Index {idx} manquant"

    def test_trigram_similarity_works(self, db: Session):
        """Verifie que la similarite trigram fonctionne."""
        result = db.execute(text(
            "SELECT similarity('AMLODIPINE', 'AMLODIPIN') > 0.3 AS similar"
        )).fetchone()
        assert result[0] is True, "Trigram similarity ne fonctionne pas"

    def test_soundex_works(self, db: Session):
        """Verifie que soundex fonctionne."""
        result = db.execute(text(
            "SELECT soundex('AMLODIPINE') = soundex('AMLODIPIN') AS same_sound"
        )).fetchone()
        assert result[0] is True, "Soundex ne fonctionne pas"

    def test_insert_and_delete_pending_validation(self, db: Session):
        """Test CRUD sur pending_validations."""
        # Insert
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, source_cip13, match_score)
            VALUES ('test', '9999999999999', 99.0)
        """))
        db.commit()

        # Verify
        result = db.execute(text(
            "SELECT COUNT(*) FROM pending_validations WHERE source_cip13 = '9999999999999'"
        )).fetchone()
        assert result[0] == 1

        # Cleanup
        db.execute(text("DELETE FROM pending_validations WHERE source_cip13 = '9999999999999'"))
        db.commit()

    def test_insert_and_delete_audit_log(self, db: Session):
        """Test CRUD sur audit_logs avec JSONB."""
        # Insert avec JSONB
        db.execute(text("""
            INSERT INTO audit_logs (action, resource_type, metadata)
            VALUES ('test_phase1', 'migration', '{"phase": 1, "test": true}'::jsonb)
        """))
        db.commit()

        # Verify JSONB query
        result = db.execute(text("""
            SELECT metadata->>'phase' FROM audit_logs
            WHERE action = 'test_phase1'
        """)).fetchone()
        assert result[0] == '1'

        # Cleanup
        db.execute(text("DELETE FROM audit_logs WHERE action = 'test_phase1'"))
        db.commit()
```

---

## Criteres de validation Phase 1

- [ ] Extensions pg_trgm et fuzzystrmatch actives
- [ ] Table `bdpm_prix_historique` creee avec 6 colonnes
- [ ] Table `pending_validations` creee avec 13 colonnes
- [ ] Table `audit_logs` creee avec JSONB
- [ ] Table `bdpm_blacklist` creee avec contrainte UNIQUE
- [ ] Colonne `molecule_signature` (GENERATED) sur bdpm_equivalences
- [ ] Colonne `labo_extracted` sur bdpm_equivalences
- [ ] Colonnes enrichies dans `matching_memory` (4 colonnes)
- [ ] Tous les index idx_* crees (minimum 15)
- [ ] Trigram similarity fonctionne
- [ ] Soundex fonctionne
- [ ] CRUD fonctionne sur toutes les nouvelles tables
- [ ] `alembic upgrade head` passe sans erreur
- [ ] `pytest backend/tests/test_phase1_migrations.py` passe

---

## Apres cette phase

Executer `/compact` puis passer a Phase 2 : `docs/architecture/PHASE2_SERVICES.md`
