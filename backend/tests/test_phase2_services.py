"""Tests Phase 2 - Services Backend"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import text


# Tests Preprocessing
class TestPharmaPreprocessing:
    """Tests pour pharma_preprocessing.py"""

    def test_preprocess_removes_labo_names(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        result = preprocess_pharma('AMLODIPINE BIOGARAN 5MG')
        assert 'BIOGARAN' not in result
        assert 'AMLODIPINE' in result
        assert '5MG' in result

    def test_preprocess_normalizes_forms(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        result = preprocess_pharma('MEDICAMENT CPR 10MG')
        assert 'COMPRIME' in result
        assert 'CPR' not in result

    def test_preprocess_normalizes_dosage_spaces(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        result = preprocess_pharma('MEDICAMENT 10 MG')
        assert '10MG' in result
        assert '10 MG' not in result

    def test_preprocess_removes_packaging(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        result = preprocess_pharma('MEDICAMENT 10MG B/30')
        assert 'B/30' not in result
        assert 'B/' not in result

    def test_preprocess_removes_bte(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        result = preprocess_pharma('MEDICAMENT 10MG BTE 30')
        assert 'BTE' not in result

    def test_preprocess_handles_empty_string(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        assert preprocess_pharma('') == ''
        assert preprocess_pharma(None) == ''

    def test_preprocess_multiple_labos(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        # Should remove all known labos
        result = preprocess_pharma('AMLODIPINE SANDOZ TEVA 5MG')
        assert 'SANDOZ' not in result
        assert 'TEVA' not in result

    def test_extract_labo_biogaran(self):
        from app.services.pharma_preprocessing import extract_labo_from_denomination
        assert extract_labo_from_denomination('AMLODIPINE BIOGARAN 5MG') == 'BIOGARAN'

    def test_extract_labo_sandoz(self):
        from app.services.pharma_preprocessing import extract_labo_from_denomination
        assert extract_labo_from_denomination('METFORMINE SANDOZ 1000MG') == 'SANDOZ'

    def test_extract_labo_none(self):
        from app.services.pharma_preprocessing import extract_labo_from_denomination
        assert extract_labo_from_denomination('DOLIPRANE 1000MG') is None

    def test_extract_labo_bgr_alias(self):
        from app.services.pharma_preprocessing import extract_labo_from_denomination
        assert extract_labo_from_denomination('MEDICAMENT BGR 10MG') == 'BIOGARAN'

    def test_extract_labo_mylan_viatris(self):
        from app.services.pharma_preprocessing import extract_labo_from_denomination
        assert extract_labo_from_denomination('MEDICAMENT MYLAN 10MG') == 'VIATRIS'


# Tests Batch Matching
class TestBatchMatching:
    """Tests pour batch_matching.py"""

    def test_batch_match_exact_match(self):
        from app.services.batch_matching import batch_match_products
        ventes = [{'designation': 'AMLODIPINE 5MG COMPRIME'}]
        bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE 5MG COMPRIME', 'pfht': 2.5}]
        results = batch_match_products(ventes, bdpm)
        assert len(results) == 1
        assert results[0]['match_score'] >= 95
        assert results[0]['matched_cip13'] == '123'

    def test_batch_match_fuzzy_match(self):
        from app.services.batch_matching import batch_match_products
        ventes = [{'designation': 'AMLODIPINE 5MG'}]
        bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE EG 5MG CPR', 'pfht': 2.5}]
        results = batch_match_products(ventes, bdpm)
        assert len(results) == 1
        assert results[0]['match_score'] >= 70

    def test_batch_match_no_match(self):
        from app.services.batch_matching import batch_match_products
        ventes = [{'designation': 'PRODUIT TOTALEMENT DIFFERENT XYZ'}]
        bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE 5MG', 'pfht': 2.5}]
        results = batch_match_products(ventes, bdpm, score_threshold=70.0)
        assert len(results) == 1
        assert results[0]['matched_cip13'] is None
        assert results[0]['match_type'] == 'no_match'

    def test_batch_match_multiple_ventes(self):
        from app.services.batch_matching import batch_match_products
        ventes = [
            {'designation': 'AMLODIPINE 5MG'},
            {'designation': 'METFORMINE 1000MG'}
        ]
        bdpm = [
            {'cip13': '123', 'denomination': 'AMLODIPINE 5MG CPR', 'pfht': 2.5},
            {'cip13': '456', 'denomination': 'METFORMINE 1000MG CPR', 'pfht': 3.0}
        ]
        results = batch_match_products(ventes, bdpm)
        assert len(results) == 2
        assert results[0]['matched_cip13'] == '123'
        assert results[1]['matched_cip13'] == '456'

    def test_batch_match_returns_pfht(self):
        from app.services.batch_matching import batch_match_products
        ventes = [{'designation': 'AMLODIPINE 5MG'}]
        bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE 5MG', 'pfht': 2.5}]
        results = batch_match_products(ventes, bdpm)
        assert results[0]['pfht'] == 2.5

    def test_batch_match_threshold(self):
        from app.services.batch_matching import batch_match_products
        ventes = [{'designation': 'AMLO'}]
        bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE 5MG', 'pfht': 2.5}]
        # With threshold 90, should not match
        results = batch_match_products(ventes, bdpm, score_threshold=90.0)
        assert results[0]['matched_cip13'] is None

    def test_batch_match_empty_input(self):
        from app.services.batch_matching import batch_match_products
        results = batch_match_products([], [])
        assert results == []


# Tests Auto-Validation
class TestAutoValidation:
    """Tests pour auto_validation.py"""

    def test_fuzzy_match_high_score_auto_validates(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('fuzzy_match', 96.0, {})
        assert result is True

    def test_fuzzy_match_low_score_requires_manual(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('fuzzy_match', 80.0, {})
        assert result is False

    def test_cip_exact_always_auto_validates(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('cip_exact', 100.0, {})
        assert result is True

    def test_nouveau_produit_never_auto_validates(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('nouveau_produit', 100.0, {})
        assert result is False

    def test_groupe_generique_auto_validates(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('groupe_generique', 100.0, {})
        assert result is True

    def test_unknown_type_returns_false(self):
        from app.services.auto_validation import should_auto_validate
        result = should_auto_validate('unknown_type', 100.0, {})
        assert result is False

    def test_get_validation_threshold(self):
        from app.services.auto_validation import get_validation_threshold
        threshold = get_validation_threshold('fuzzy_match')
        assert threshold == 95.0

    def test_get_validation_config(self):
        from app.services.auto_validation import get_validation_config
        config = get_validation_config('fuzzy_match')
        assert 'score_min' in config
        assert config['score_min'] == 95.0


# Tests Audit Logger
class TestAuditLogger:
    """Tests pour audit_logger.py"""

    def test_audit_log_creates_entry(self, db):
        from app.services.audit_logger import AuditLogger
        logger = AuditLogger(db)
        logger.log(
            action='test_action',
            resource_type='test_resource',
            description='Test description'
        )
        # Verify entry exists
        result = db.execute(text(
            "SELECT * FROM audit_logs WHERE action = 'test_action'"
        )).fetchone()
        assert result is not None
        # Cleanup
        db.execute(text("DELETE FROM audit_logs WHERE action = 'test_action'"))
        db.commit()

    def test_audit_log_with_metadata(self, db):
        from app.services.audit_logger import AuditLogger
        logger = AuditLogger(db)
        logger.log(
            action='test_metadata',
            resource_type='test',
            metadata={'key': 'value', 'count': 42}
        )
        result = db.execute(text(
            "SELECT metadata FROM audit_logs WHERE action = 'test_metadata'"
        )).fetchone()
        assert result is not None
        metadata = result[0]
        assert metadata['key'] == 'value'
        assert metadata['count'] == 42
        # Cleanup
        db.execute(text("DELETE FROM audit_logs WHERE action = 'test_metadata'"))
        db.commit()

    def test_audit_log_with_old_new_values(self, db):
        from app.services.audit_logger import AuditLogger
        logger = AuditLogger(db)
        logger.log(
            action='update',
            resource_type='product',
            resource_id='12345',
            old_values={'price': 10.0},
            new_values={'price': 12.0}
        )
        result = db.execute(text(
            "SELECT old_values, new_values FROM audit_logs WHERE action = 'update' AND resource_id = '12345'"
        )).fetchone()
        assert result[0]['price'] == 10.0
        assert result[1]['price'] == 12.0
        # Cleanup
        db.execute(text("DELETE FROM audit_logs WHERE resource_id = '12345'"))
        db.commit()


# Tests MatchingService
class TestMatchingService:
    """Tests pour matching_service.py"""

    def test_matching_service_cache_hit(self, db):
        from app.services.matching_service import MatchingService
        # Pre-populate cache
        db.execute(text("""
            INSERT INTO matching_memory (groupe_equivalence_id, cip13, designation, matched_cip13, match_score, validated)
            VALUES (99999, '9999999999999', 'TEST CACHE', '8888888888888', 95.0, true)
        """))
        db.commit()

        service = MatchingService(db)
        result = service.get_or_compute_match('9999999999999', 'TEST CACHE')

        assert result['matched_cip13'] == '8888888888888'
        assert result['match_score'] == 95.0

        # Cleanup
        db.execute(text("DELETE FROM matching_memory WHERE cip13 = '9999999999999'"))
        db.commit()

    def test_matching_service_batch_process(self, db):
        from app.services.matching_service import MatchingService
        service = MatchingService(db)

        ventes = [
            {'code_cip_achete': '1111111111111', 'designation': 'TEST 1'},
            {'code_cip_achete': '2222222222222', 'designation': 'TEST 2'}
        ]
        result = service.batch_process_ventes(ventes)

        assert 'total' in result
        assert 'from_cache' in result
        assert 'computed' in result
        assert result['total'] == 2

    def test_matching_service_invalidate_cache(self, db):
        from app.services.matching_service import MatchingService
        # Pre-populate cache
        db.execute(text("""
            INSERT INTO matching_memory (groupe_equivalence_id, cip13, designation, matched_cip13, match_score, validated)
            VALUES (99998, '8888888888888', 'TEST INVALIDATE', '7777777777777', 95.0, true)
        """))
        db.commit()

        service = MatchingService(db)
        assert '8888888888888' in service._cache

        service.invalidate_cache('8888888888888')
        assert '8888888888888' not in service._cache

        # Cleanup
        db.execute(text("DELETE FROM matching_memory WHERE cip13 = '8888888888888'"))
        db.commit()
