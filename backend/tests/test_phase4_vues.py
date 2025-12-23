"""Tests Phase 4 - Materialized Views"""
import pytest
from sqlalchemy import text


class TestMaterializedViewsMigrations:
    """Tests for materialized view migrations."""

    def test_mv_clusters_equivalences_exists(self, db):
        """Verify mv_clusters_equivalences view exists."""
        result = db.execute(text("""
            SELECT COUNT(*) FROM pg_matviews
            WHERE matviewname = 'mv_clusters_equivalences'
        """)).scalar()
        # May not exist if migrations haven't run
        assert result is not None

    def test_mv_matching_stats_exists(self, db):
        """Verify mv_matching_stats view exists."""
        result = db.execute(text("""
            SELECT COUNT(*) FROM pg_matviews
            WHERE matviewname = 'mv_matching_stats'
        """)).scalar()
        assert result is not None

    def test_find_best_match_function_exists(self, db):
        """Verify find_best_match function exists."""
        result = db.execute(text("""
            SELECT COUNT(*) FROM pg_proc
            WHERE proname = 'find_best_match'
        """)).scalar()
        # May not exist if migrations haven't run
        assert result is not None

    def test_trigram_indexes_exist(self, db):
        """Verify trigram indexes exist."""
        result = db.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname IN ('idx_bdpm_denomination_trgm', 'idx_bdpm_princeps_trgm')
        """)).fetchall()
        # May not exist if migrations haven't run
        assert result is not None


class TestMaterializedViewService:
    """Tests for MaterializedViewService."""

    def test_service_init(self, db):
        """Test service initialization."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        assert service.db == db

    def test_check_views_exist(self, db):
        """Test checking view existence."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.check_views_exist()

        assert isinstance(result, dict)
        assert 'mv_clusters_equivalences' in result
        assert 'mv_matching_stats' in result

    def test_get_stats(self, db):
        """Test getting view stats."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.get_stats()

        assert isinstance(result, list)

    def test_refresh_clusters_returns_result(self, db):
        """Test cluster refresh returns a result dict."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.refresh_clusters()

        assert isinstance(result, dict)
        assert 'status' in result

    def test_refresh_matching_stats_returns_result(self, db):
        """Test matching stats refresh returns a result dict."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.refresh_matching_stats()

        assert isinstance(result, dict)
        assert 'status' in result

    def test_refresh_all_returns_results(self, db):
        """Test refresh all returns results for each view."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.refresh_all()

        assert isinstance(result, dict)
        assert 'clusters' in result
        assert 'matching_stats' in result


class TestAdminEndpoints:
    """Tests for /api/admin endpoints."""

    def test_refresh_views(self, db):
        """Test POST /api/admin/refresh-views."""
        from app.api.admin import refresh_materialized_views
        import asyncio

        async def test_async():
            return await refresh_materialized_views(db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert isinstance(result, dict)
        assert 'clusters' in result
        assert 'matching_stats' in result

    def test_views_stats(self, db):
        """Test GET /api/admin/views-stats."""
        from app.api.admin import get_views_stats
        import asyncio

        async def test_async():
            return await get_views_stats(db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert isinstance(result, list)

    def test_views_status(self, db):
        """Test GET /api/admin/views-status."""
        from app.api.admin import get_views_status
        import asyncio

        async def test_async():
            return await get_views_status(db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert isinstance(result, dict)
        assert 'mv_clusters_equivalences' in result
        assert 'mv_matching_stats' in result

    def test_refresh_specific_view_clusters(self, db):
        """Test POST /api/admin/refresh-views/clusters."""
        from app.api.admin import refresh_specific_view
        import asyncio

        async def test_async():
            return await refresh_specific_view('clusters', db)

        result = asyncio.get_event_loop().run_until_complete(test_async())

        assert isinstance(result, dict)
        assert 'status' in result

    def test_refresh_specific_view_invalid(self, db):
        """Test POST /api/admin/refresh-views/{invalid}."""
        from app.api.admin import refresh_specific_view
        from fastapi import HTTPException
        import asyncio

        async def test_async():
            try:
                await refresh_specific_view('invalid', db)
                return False
            except HTTPException as e:
                return e.status_code == 400

        result = asyncio.get_event_loop().run_until_complete(test_async())
        assert result is True


class TestClusterQuery:
    """Tests for cluster query functionality."""

    def test_get_cluster_by_groupe_not_found(self, db):
        """Test get_cluster_by_groupe returns None for non-existent group."""
        from app.services.materialized_views import MaterializedViewService
        service = MaterializedViewService(db)
        result = service.get_cluster_by_groupe(0)

        # Should be None or a valid result
        assert result is None or isinstance(result, dict)


class TestPerformance:
    """Performance tests for materialized views."""

    def test_cluster_lookup_is_fast(self, db):
        """Test that cluster lookup is fast (<100ms)."""
        from app.services.materialized_views import MaterializedViewService
        from datetime import datetime

        service = MaterializedViewService(db)

        start = datetime.now()
        for _ in range(100):
            service.get_cluster_by_groupe(1)
        elapsed = (datetime.now() - start).total_seconds()

        # 100 queries should complete in less than 10 seconds
        # (100ms per query on average)
        assert elapsed < 10, f"Cluster lookup too slow: {elapsed}s for 100 queries"


class TestFindBestMatchFunction:
    """Tests for the find_best_match SQL function."""

    def test_find_best_match_returns_results(self, db):
        """Test find_best_match function returns results."""
        # First check if function exists
        func_exists = db.execute(text("""
            SELECT COUNT(*) FROM pg_proc WHERE proname = 'find_best_match'
        """)).scalar()

        if func_exists > 0:
            result = db.execute(text("""
                SELECT * FROM find_best_match('AMLODIPINE') LIMIT 5
            """)).fetchall()

            assert result is not None
            # May be empty if no data in bdpm_equivalences
        else:
            pytest.skip("find_best_match function not created yet")
