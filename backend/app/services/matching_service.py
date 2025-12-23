"""Matching service with persistent cache.

This service manages product matching with a cache layer that stores
validated matches. Only new CIPs are computed, making repeat matching
near-instantaneous.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from .batch_matching import batch_match_products
from ..models.models import MatchingMemory, BdpmEquivalence


class MatchingService:
    """
    Matching service with cache.

    Only recomputes for new CIPs - validated matches are cached permanently.

    Usage:
        service = MatchingService(db)
        match = service.get_or_compute_match('3400930000001', 'AMLODIPINE 5MG')
        # Returns cached match or computes new one
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Load cache from matching_memory table."""
        matches = self.db.query(MatchingMemory).filter(
            MatchingMemory.validated == True
        ).all()

        self._cache = {}
        for m in matches:
            self._cache[m.cip13] = {
                'matched_cip13': m.matched_cip13,
                'matched_denomination': m.matched_denomination,
                'match_score': float(m.match_score) if m.match_score else None,
                'match_origin': m.match_origin,
                'pfht': float(m.pfht) if m.pfht else None,
                'groupe_generique_id': m.groupe_generique_id
            }

    def get_or_compute_match(self, cip13: str, designation: str) -> Dict:
        """
        Return cached match or compute if new.

        Args:
            cip13: The CIP13 code of the product
            designation: The product designation for fuzzy matching

        Returns:
            Match result dictionary with matched_cip13, match_score, etc.
        """
        # Cache hit = instant
        if cip13 in self._cache:
            return self._cache[cip13]

        # Cache miss = compute and store
        match = self._compute_single_match(designation)
        if match.get('matched_cip13'):
            self._store_match(cip13, designation, match)
        return match

    def _compute_single_match(self, designation: str) -> Dict:
        """Compute match for a single designation."""
        bdpm_refs = self.db.query(BdpmEquivalence).filter(
            BdpmEquivalence.pfht.isnot(None)
        ).all()

        if not bdpm_refs:
            return {'matched_cip13': None, 'match_score': 0, 'match_type': 'no_bdpm'}

        bdpm_list = [
            {'cip13': b.cip13, 'denomination': b.denomination, 'pfht': b.pfht}
            for b in bdpm_refs
        ]

        results = batch_match_products(
            [{'designation': designation}],
            bdpm_list,
            score_threshold=70.0
        )
        return results[0] if results else {'matched_cip13': None, 'match_score': 0}

    def _store_match(self, cip13: str, designation: str, match: Dict):
        """Store a new match in matching_memory."""
        # Check if already exists
        existing = self.db.query(MatchingMemory).filter(
            MatchingMemory.cip13 == cip13
        ).first()

        if existing:
            # Update existing
            existing.matched_cip13 = match.get('matched_cip13')
            existing.matched_denomination = match.get('matched_designation')
            existing.match_score = match.get('match_score')
            existing.match_origin = match.get('match_type')
            existing.pfht = match.get('pfht')
            existing.validated = False
        else:
            # Create new
            # Generate a unique groupe_equivalence_id
            max_groupe = self.db.execute(
                text("SELECT COALESCE(MAX(groupe_equivalence_id), 0) + 1 FROM matching_memory")
            ).scalar()

            memory = MatchingMemory(
                groupe_equivalence_id=max_groupe,
                cip13=cip13,
                designation=designation,
                matched_cip13=match.get('matched_cip13'),
                matched_denomination=match.get('matched_designation'),
                match_score=match.get('match_score'),
                match_origin=match.get('match_type'),
                pfht=match.get('pfht'),
                validated=False  # Requires validation
            )
            self.db.add(memory)

        self.db.commit()

    def batch_process_ventes(self, ventes: List[Dict]) -> Dict:
        """
        Process a batch of sales.

        Separates cache hits from required computations for optimal performance.

        Args:
            ventes: List of sales with 'code_cip_achete' and 'designation'

        Returns:
            Dictionary with 'total', 'from_cache', 'computed', 'results'
        """
        cached = []
        to_compute = []

        for v in ventes:
            cip = v.get('code_cip_achete')
            if cip and cip in self._cache:
                result = self._cache[cip].copy()
                result['source_cip13'] = cip
                result['source_designation'] = v.get('designation')
                cached.append(result)
            else:
                to_compute.append(v)

        # Batch compute only new ones
        computed = []
        if to_compute:
            bdpm_refs = self.db.query(BdpmEquivalence).filter(
                BdpmEquivalence.pfht.isnot(None)
            ).all()

            if bdpm_refs:
                bdpm_list = [
                    {'cip13': b.cip13, 'denomination': b.denomination, 'pfht': b.pfht}
                    for b in bdpm_refs
                ]

                vente_list = [
                    {'cip13': v.get('code_cip_achete'), 'designation': v.get('designation')}
                    for v in to_compute
                ]

                new_matches = batch_match_products(vente_list, bdpm_list)

                for match in new_matches:
                    source_cip = match.get('source_cip13')
                    if source_cip:
                        self._store_match(
                            source_cip,
                            match.get('source_designation', ''),
                            match
                        )
                    computed.append(match)

        return {
            'total': len(ventes),
            'from_cache': len(cached),
            'computed': len(computed),
            'results': cached + computed
        }

    def invalidate_cache(self, cip13: Optional[str] = None):
        """
        Invalidate cache entries.

        Args:
            cip13: Specific CIP to invalidate, or None to clear all
        """
        if cip13:
            self._cache.pop(cip13, None)
        else:
            self._cache.clear()
            self._load_cache()
