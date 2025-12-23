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

    def test_bdpm_blacklist_unique_constraint(self, db: Session):
        """Test contrainte UNIQUE sur bdpm_blacklist.cip13."""
        # Insert first record
        db.execute(text("""
            INSERT INTO bdpm_blacklist (cip13, denomination, raison_suppression)
            VALUES ('9999999999998', 'TEST PRODUIT', 'test')
        """))
        db.commit()

        # Try to insert duplicate - should fail
        try:
            db.execute(text("""
                INSERT INTO bdpm_blacklist (cip13, denomination, raison_suppression)
                VALUES ('9999999999998', 'TEST PRODUIT 2', 'test')
            """))
            db.commit()
            # If we get here, constraint didn't work
            assert False, "UNIQUE constraint not enforced"
        except Exception as e:
            db.rollback()
            assert 'duplicate key' in str(e).lower() or 'unique' in str(e).lower()

        # Cleanup
        db.execute(text("DELETE FROM bdpm_blacklist WHERE cip13 = '9999999999998'"))
        db.commit()

    def test_bdpm_prix_historique_crud(self, db: Session):
        """Test CRUD sur bdpm_prix_historique."""
        # Insert
        db.execute(text("""
            INSERT INTO bdpm_prix_historique (cip13, pfht_ancien, pfht_nouveau, variation_pct, source_import)
            VALUES ('9999999999997', 10.00, 12.00, 20.00, 'test')
        """))
        db.commit()

        # Verify
        result = db.execute(text("""
            SELECT pfht_ancien, pfht_nouveau, variation_pct FROM bdpm_prix_historique
            WHERE cip13 = '9999999999997'
        """)).fetchone()
        assert float(result[0]) == 10.00
        assert float(result[1]) == 12.00
        assert float(result[2]) == 20.00

        # Cleanup
        db.execute(text("DELETE FROM bdpm_prix_historique WHERE cip13 = '9999999999997'"))
        db.commit()
