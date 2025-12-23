"""Tests Phase 3 - Endpoints API"""
import pytest
from sqlalchemy import text
import base64
import json


class TestPaginationHelper:
    """Tests pour pagination.py"""

    def test_encode_decode_cursor(self):
        from app.api.pagination import encode_cursor, decode_cursor
        data = {'last_id': 42, 'page': 1}
        cursor = encode_cursor(data)
        decoded = decode_cursor(cursor)
        assert decoded == data

    def test_decode_invalid_cursor(self):
        from app.api.pagination import decode_cursor
        result = decode_cursor('invalid_base64')
        assert result == {}

    def test_encode_cursor_is_base64(self):
        from app.api.pagination import encode_cursor
        cursor = encode_cursor({'last_id': 1})
        # Should be valid base64
        try:
            base64.b64decode(cursor)
            assert True
        except Exception:
            assert False, "Cursor is not valid base64"

    def test_decode_empty_cursor(self):
        from app.api.pagination import decode_cursor
        result = decode_cursor('')
        assert result == {}

    def test_encode_complex_data(self):
        from app.api.pagination import encode_cursor, decode_cursor
        data = {'last_id': 12345, 'filters': {'type': 'fuzzy'}, 'active': True}
        cursor = encode_cursor(data)
        decoded = decode_cursor(cursor)
        assert decoded == data


class TestGroupeEndpoints:
    """Tests pour /api/groupe endpoints"""

    def test_groupe_details_returns_structure(self, db):
        # First insert a test groupe
        db.execute(text("""
            INSERT INTO bdpm_equivalences (cip13, denomination, groupe_generique_id, type_generique, pfht)
            VALUES
            ('9999999999901', 'PRINCEPS TEST', 99999, 0, 10.0),
            ('9999999999902', 'GENERIQUE TEST 1', 99999, 1, 10.0),
            ('9999999999903', 'GENERIQUE TEST 2', 99999, 1, 10.0)
            ON CONFLICT (cip13) DO NOTHING
        """))
        db.commit()

        # Import and test the endpoint function directly
        from app.api.groupe import get_groupe_details
        import asyncio

        async def test_async():
            result = await get_groupe_details(99999, db)
            return result

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'groupe_id' in result
        assert 'princeps' in result
        assert 'equivalents' in result
        assert 'stats' in result
        assert result['stats']['nb_references'] >= 1

        # Cleanup
        db.execute(text("DELETE FROM bdpm_equivalences WHERE groupe_generique_id = 99999"))
        db.commit()

    def test_groupe_details_not_found(self, db):
        from app.api.groupe import get_groupe_details
        from fastapi import HTTPException
        import asyncio

        async def test_async():
            try:
                await get_groupe_details(0, db)
                return False
            except HTTPException as e:
                return e.status_code == 404

        result = asyncio.get_event_loop().run_until_complete(test_async())
        assert result is True


class TestValidationsEndpoints:
    """Tests pour /api/validations endpoints"""

    def test_pending_returns_paginated(self, db):
        # Insert test validations
        for i in range(5):
            db.execute(text("""
                INSERT INTO pending_validations (validation_type, source_cip13, status)
                VALUES ('test', :cip, 'pending')
            """), {'cip': f'999999999{i:04d}'})
        db.commit()

        from app.api.validations import get_pending_validations
        import asyncio

        async def test_async():
            return await get_pending_validations(limit=10, db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'items' in result
        assert 'next_cursor' in result
        assert 'total_count' in result
        assert result['total_count'] >= 5

        # Cleanup
        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test'"))
        db.commit()

    def test_pending_filter_by_type(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('test_fuzzy', 'pending'), ('test_exact', 'pending')
        """))
        db.commit()

        from app.api.validations import get_pending_validations
        import asyncio

        async def test_async():
            return await get_pending_validations(validation_type='test_fuzzy', db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        for item in result['items']:
            assert item['validation_type'] == 'test_fuzzy'

        db.execute(text("DELETE FROM pending_validations WHERE validation_type IN ('test_fuzzy', 'test_exact')"))
        db.commit()

    def test_stats_returns_by_type(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status, auto_validated)
            VALUES
            ('test_stats_fuzzy', 'pending', false),
            ('test_stats_fuzzy', 'validated', false),
            ('test_stats_exact', 'pending', true)
        """))
        db.commit()

        from app.api.validations import get_validation_stats
        import asyncio

        async def test_async():
            return await get_validation_stats(db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'test_stats_fuzzy' in result or 'test_stats_exact' in result

        db.execute(text("DELETE FROM pending_validations WHERE validation_type IN ('test_stats_fuzzy', 'test_stats_exact')"))
        db.commit()

    def test_count_pending(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('test_count', 'pending'), ('test_count', 'pending')
        """))
        db.commit()

        from app.api.validations import count_pending
        import asyncio

        async def test_async():
            return await count_pending(db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'count' in result
        assert result['count'] >= 2

        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test_count'"))
        db.commit()


class TestPrixEndpoints:
    """Tests pour /api/prix endpoints"""

    def test_variations_stats(self, db):
        # Insert test data
        db.execute(text("""
            INSERT INTO bdpm_prix_historique (cip13, pfht_ancien, pfht_nouveau, variation_pct, date_changement)
            VALUES
            ('9999999999901', 10.0, 15.0, 50.0, NOW()),
            ('9999999999902', 20.0, 15.0, -25.0, NOW())
        """))
        db.commit()

        from app.api.prix import get_price_variation_stats
        import asyncio

        async def test_async():
            return await get_price_variation_stats(db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'total' in result
        assert 'hausses' in result
        assert 'baisses' in result
        assert 'variation_max' in result

        db.execute(text("DELETE FROM bdpm_prix_historique WHERE cip13 LIKE '999999999990%'"))
        db.commit()

    def test_historique_cip(self, db):
        db.execute(text("""
            INSERT INTO bdpm_prix_historique (cip13, pfht_ancien, pfht_nouveau, variation_pct)
            VALUES
            ('9999999999999', 10.0, 12.0, 20.0),
            ('9999999999999', 12.0, 11.0, -8.33)
        """))
        db.commit()

        from app.api.prix import get_price_history
        import asyncio

        async def test_async():
            return await get_price_history('9999999999999', db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert isinstance(result, list)
        assert len(result) >= 2

        db.execute(text("DELETE FROM bdpm_prix_historique WHERE cip13 = '9999999999999'"))
        db.commit()

    def test_historique_empty(self, db):
        from app.api.prix import get_price_history
        import asyncio

        async def test_async():
            return await get_price_history('0000000000000', db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())
        assert result == []

    def test_alert_count(self, db):
        db.execute(text("""
            INSERT INTO bdpm_prix_historique (cip13, pfht_ancien, pfht_nouveau, variation_pct, date_changement)
            VALUES ('9999999999998', 10.0, 15.0, 50.0, NOW())
        """))
        db.commit()

        from app.api.prix import get_alert_count
        import asyncio

        async def test_async():
            return await get_alert_count(db=db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert 'count' in result
        assert result['count'] >= 1

        db.execute(text("DELETE FROM bdpm_prix_historique WHERE cip13 = '9999999999998'"))
        db.commit()


class TestAuditLogging:
    """Tests que les actions sont loguees"""

    def test_bulk_action_creates_audit_log(self, db):
        from unittest.mock import Mock

        # Insert test validation
        result = db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('audit_test', 'pending')
            RETURNING id
        """))
        db.commit()
        test_id = result.fetchone()[0]

        # Create a mock request
        mock_request = Mock()
        mock_request.state = Mock()
        mock_request.state.user_email = None
        mock_request.client = None
        mock_request.headers = {}

        from app.api.validations import bulk_validate, ValidateRequest
        import asyncio

        async def test_async():
            req = ValidateRequest(ids=[test_id], action='validate')
            return await bulk_validate(req, mock_request, db)

        asyncio.get_event_loop().run_until_complete(test_async())

        # Check audit log
        result = db.execute(text("""
            SELECT * FROM audit_logs
            WHERE action = 'validate'
            AND resource_type = 'validation'
            ORDER BY created_at DESC
            LIMIT 1
        """)).fetchone()

        assert result is not None

        # Cleanup
        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'audit_test'"))
        db.execute(text("DELETE FROM audit_logs WHERE resource_type = 'validation'"))
        db.commit()
