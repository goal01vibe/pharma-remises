"""Materialized views management service.

This module provides utilities for managing and refreshing materialized
views used for performance optimization.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MaterializedViewService:
    """
    Service for managing materialized views.

    Materialized views provide instant query results (<5ms) for frequently
    accessed data that would otherwise require expensive JOINs and aggregations.

    Usage:
        service = MaterializedViewService(db)
        service.refresh_all()  # Refresh all views
    """

    def __init__(self, db: Session):
        self.db = db

    def refresh_clusters(self) -> dict:
        """
        Refresh the mv_clusters_equivalences view.

        Should be called after each BDPM import.

        Returns:
            Dictionary with status and elapsed time
        """
        start = datetime.now()
        try:
            self.db.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_clusters_equivalences"
            ))
            self.db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"mv_clusters_equivalences refreshed in {elapsed:.2f}s")
            return {"status": "success", "elapsed_seconds": elapsed}
        except Exception as e:
            logger.error(f"Error refreshing mv_clusters_equivalences: {e}")
            # Try non-concurrent refresh as fallback
            try:
                self.db.execute(text(
                    "REFRESH MATERIALIZED VIEW mv_clusters_equivalences"
                ))
                self.db.commit()
                elapsed = (datetime.now() - start).total_seconds()
                logger.info(f"mv_clusters_equivalences refreshed (non-concurrent) in {elapsed:.2f}s")
                return {"status": "success", "elapsed_seconds": elapsed, "mode": "non-concurrent"}
            except Exception as e2:
                logger.error(f"Error refreshing mv_clusters_equivalences (non-concurrent): {e2}")
                return {"status": "error", "message": str(e2)}

    def refresh_matching_stats(self) -> dict:
        """
        Refresh the mv_matching_stats view.

        Should be called periodically (e.g., every hour).

        Returns:
            Dictionary with status and elapsed time
        """
        start = datetime.now()
        try:
            self.db.execute(text(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_matching_stats"
            ))
            self.db.commit()
            elapsed = (datetime.now() - start).total_seconds()
            logger.info(f"mv_matching_stats refreshed in {elapsed:.2f}s")
            return {"status": "success", "elapsed_seconds": elapsed}
        except Exception as e:
            logger.error(f"Error refreshing mv_matching_stats: {e}")
            # Try non-concurrent refresh as fallback
            try:
                self.db.execute(text(
                    "REFRESH MATERIALIZED VIEW mv_matching_stats"
                ))
                self.db.commit()
                elapsed = (datetime.now() - start).total_seconds()
                logger.info(f"mv_matching_stats refreshed (non-concurrent) in {elapsed:.2f}s")
                return {"status": "success", "elapsed_seconds": elapsed, "mode": "non-concurrent"}
            except Exception as e2:
                logger.error(f"Error refreshing mv_matching_stats (non-concurrent): {e2}")
                return {"status": "error", "message": str(e2)}

    def refresh_all(self) -> dict:
        """
        Refresh all materialized views.

        Returns:
            Dictionary with results for each view
        """
        results = {}
        results["clusters"] = self.refresh_clusters()
        results["matching_stats"] = self.refresh_matching_stats()
        return results

    def get_stats(self) -> list:
        """
        Get statistics about materialized views.

        Returns:
            List of dictionaries with view names and sizes
        """
        try:
            result = self.db.execute(text("""
                SELECT
                    schemaname,
                    matviewname,
                    pg_size_pretty(pg_relation_size(schemaname || '.' || matviewname)) as size
                FROM pg_matviews
                WHERE schemaname = 'public'
            """)).fetchall()

            return [{"name": r.matviewname, "size": r.size} for r in result]
        except Exception as e:
            logger.error(f"Error getting materialized view stats: {e}")
            return []

    def get_cluster_by_groupe(self, groupe_id: int) -> dict:
        """
        Get pre-computed cluster data for a specific group.

        This is much faster than querying bdpm_equivalences directly.

        Args:
            groupe_id: The generic group ID

        Returns:
            Cluster data or None if not found
        """
        try:
            result = self.db.execute(text("""
                SELECT * FROM mv_clusters_equivalences
                WHERE groupe_generique_id = :groupe_id
            """), {"groupe_id": groupe_id}).fetchone()

            if result:
                return dict(result._mapping)
            return None
        except Exception as e:
            logger.error(f"Error getting cluster for groupe {groupe_id}: {e}")
            return None

    def check_views_exist(self) -> dict:
        """
        Check if all expected materialized views exist.

        Returns:
            Dictionary with view names and existence status
        """
        expected_views = ['mv_clusters_equivalences', 'mv_matching_stats']
        results = {}

        try:
            for view in expected_views:
                result = self.db.execute(text("""
                    SELECT COUNT(*) FROM pg_matviews
                    WHERE matviewname = :view_name
                """), {"view_name": view}).scalar()
                results[view] = result > 0
        except Exception as e:
            logger.error(f"Error checking materialized views: {e}")
            for view in expected_views:
                results[view] = False

        return results
