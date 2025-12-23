"""Batch matching service using RapidFuzz for high-performance fuzzy matching.

This module provides vectorized batch matching using cdist for ultra-fast
matching of pharmaceutical product names.

Performance: ~10,000 sales vs ~50,000 BDPM products in < 5 seconds
"""
from rapidfuzz import process, fuzz
import numpy as np
from typing import List, Dict
from .pharma_preprocessing import preprocess_pharma


def batch_match_products(
    ventes: List[Dict],
    bdpm: List[Dict],
    score_threshold: float = 70.0
) -> List[Dict]:
    """
    Match products once, store forever.

    Uses cdist for ultra-fast matrix-based matching utilizing all CPU cores.

    Args:
        ventes: List of sales records with 'designation' key
        bdpm: List of BDPM records with 'cip13', 'denomination', 'pfht' keys
        score_threshold: Minimum score (0-100) to consider a match valid

    Returns:
        List of match results with source and matched info

    Example:
        >>> ventes = [{'designation': 'AMLODIPINE 5MG'}]
        >>> bdpm = [{'cip13': '123', 'denomination': 'AMLODIPINE 5MG CPR', 'pfht': 2.5}]
        >>> results = batch_match_products(ventes, bdpm)
        >>> results[0]['matched_cip13']
        '123'
    """
    if not ventes or not bdpm:
        return []

    # Pharmaceutical preprocessing before matching
    vente_names = [preprocess_pharma(v.get('designation', '')) for v in ventes]
    bdpm_names = [preprocess_pharma(b.get('denomination', '')) for b in bdpm]

    # Matrix computation (uses all CPUs with workers=-1)
    scores = process.cdist(
        vente_names,
        bdpm_names,
        scorer=fuzz.token_set_ratio,
        workers=-1
    )

    results = []
    for i, vente in enumerate(ventes):
        best_idx = int(np.argmax(scores[i]))
        best_score = float(scores[i][best_idx])

        if best_score >= score_threshold:
            results.append({
                'source_cip13': vente.get('cip13'),
                'source_designation': vente.get('designation', ''),
                'matched_cip13': bdpm[best_idx].get('cip13'),
                'matched_designation': bdpm[best_idx].get('denomination'),
                'match_score': best_score,
                'match_type': 'fuzzy',
                'pfht': bdpm[best_idx].get('pfht')
            })
        else:
            results.append({
                'source_cip13': vente.get('cip13'),
                'source_designation': vente.get('designation', ''),
                'matched_cip13': None,
                'matched_designation': None,
                'match_score': best_score,
                'match_type': 'no_match',
                'pfht': None
            })

    return results
