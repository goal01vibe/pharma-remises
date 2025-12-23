"""Auto-validation rules for matching results.

This module defines thresholds and rules for automatically validating
certain types of matches without requiring manual review.
"""
from typing import Dict, Any

# Auto-validation configuration by match type
AUTO_VALIDATION_THRESHOLDS = {
    'fuzzy_match': {
        'score_min': 95.0,
        'same_groupe': True,
        'same_dosage': True,
    },
    'prix_groupe': {
        'auto_validate': True,
    },
    'nouveau_produit': {
        'auto_validate': False,
    },
    'cip_exact': {
        'auto_validate': True,
    },
    'groupe_generique': {
        'auto_validate': True,
    },
}


def should_auto_validate(match_type: str, score: float, context: Dict[str, Any]) -> bool:
    """
    Determine if a match should be auto-validated based on thresholds.

    Args:
        match_type: Type of match ('fuzzy_match', 'cip_exact', etc.)
        score: Match score (0-100)
        context: Additional context for validation rules

    Returns:
        True if the match should be auto-validated, False otherwise

    Examples:
        >>> should_auto_validate('cip_exact', 100.0, {})
        True
        >>> should_auto_validate('fuzzy_match', 96.0, {})
        True
        >>> should_auto_validate('fuzzy_match', 80.0, {})
        False
        >>> should_auto_validate('nouveau_produit', 100.0, {})
        False
    """
    config = AUTO_VALIDATION_THRESHOLDS.get(match_type, {})

    # Types always auto-validated
    if config.get('auto_validate') is True:
        return True

    # Types never auto-validated
    if config.get('auto_validate') is False:
        return False

    # Fuzzy match: multi-criteria verification
    if match_type == 'fuzzy_match':
        if score < config.get('score_min', 95.0):
            return False
        if config.get('same_groupe') and context.get('source_groupe') != context.get('target_groupe'):
            return False
        if config.get('same_dosage') and context.get('source_dosage') != context.get('target_dosage'):
            return False
        return True

    return False


def get_validation_threshold(match_type: str) -> float:
    """
    Get the minimum score threshold for a match type.

    Args:
        match_type: Type of match

    Returns:
        Minimum score required for auto-validation
    """
    config = AUTO_VALIDATION_THRESHOLDS.get(match_type, {})
    return config.get('score_min', 95.0)


def get_validation_config(match_type: str) -> Dict[str, Any]:
    """
    Get the full validation configuration for a match type.

    Args:
        match_type: Type of match

    Returns:
        Configuration dictionary
    """
    return AUTO_VALIDATION_THRESHOLDS.get(match_type, {})
