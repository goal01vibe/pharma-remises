"""Pharmaceutical text preprocessing for fuzzy matching.

This module provides functions to normalize pharmaceutical product names
before fuzzy matching, improving accuracy by removing noise (lab names,
abbreviations, packaging info).
"""
import re
from typing import Set, Optional

# Known lab names to remove from text for matching
LABOS_CONNUS: Set[str] = {
    'viatris', 'zentiva', 'biogaran', 'sandoz', 'teva', 'mylan', 'arrow',
    'eg', 'cristers', 'accord', 'ranbaxy', 'zydus', 'sun', 'almus', 'bgr',
    'ratiopharm', 'actavis', 'winthrop', 'pfizer', 'sanofi', 'bayer',
}

# Forms to normalize (abbreviation -> full form)
FORMES_MAPPING = {
    'cpr': 'comprime', 'cp': 'comprime', 'comp': 'comprime',
    'gel': 'gelule', 'caps': 'capsule', 'sol': 'solution',
    'susp': 'suspension', 'inj': 'injectable', 'cr': 'creme',
    'pom': 'pommade', 'suppo': 'suppositoire', 'pdre': 'poudre',
}


def preprocess_pharma(text: str) -> str:
    """
    Normalize pharmaceutical names before fuzzy matching.

    Improves matching precision by removing noise:
    - Lab names (BIOGARAN, SANDOZ, etc.)
    - Abbreviations are expanded (CPR -> COMPRIME)
    - Dosages normalized (40 mg -> 40MG)
    - Packaging removed (B/30, BTE 30)

    Args:
        text: The pharmaceutical product name to normalize

    Returns:
        Normalized uppercase string

    Examples:
        >>> preprocess_pharma('AMLODIPINE BIOGARAN 5MG CPR B/30')
        'AMLODIPINE 5MG COMPRIME'
        >>> preprocess_pharma('METFORMINE SANDOZ 1000 MG BTE 30')
        'METFORMINE 1000MG'
    """
    if not text:
        return ""

    result = text.upper()

    # 1. Remove lab names
    for labo in LABOS_CONNUS:
        result = re.sub(rf'\b{labo.upper()}\b', '', result)

    # 2. Normalize forms (CPR -> COMPRIME)
    for abbr, full in FORMES_MAPPING.items():
        result = re.sub(rf'\b{abbr.upper()}\b', full.upper(), result)

    # 3. Normalize dosages (40 mg -> 40MG, remove spaces)
    result = re.sub(r'(\d+)\s*(MG|G|ML|MCG|UI)', r'\1\2', result)

    # 4. Remove packaging info (B/30, BTE 30, etc.)
    result = re.sub(r'\bB/?(\d+)\b', '', result)
    result = re.sub(r'\b(BTE|BOITE|PLQ)\s*\d+\b', '', result)

    # 5. Clean up multiple spaces
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def extract_labo_from_denomination(denomination: str) -> Optional[str]:
    """
    Extract lab name from BDPM denomination.

    Args:
        denomination: The product denomination from BDPM

    Returns:
        Lab name if found, None otherwise

    Examples:
        >>> extract_labo_from_denomination('AMLODIPINE BIOGARAN 5 mg')
        'BIOGARAN'
        >>> extract_labo_from_denomination('DOLIPRANE 1000 mg')
        None
    """
    if not denomination:
        return None

    LABO_PATTERNS = {
        'BIOGARAN': r'\bBIOGARAN\b|\bBGR\b',
        'SANDOZ': r'\bSANDOZ\b',
        'ARROW': r'\bARROW\b',
        'ZENTIVA': r'\bZENTIVA\b',
        'VIATRIS': r'\bVIATRIS\b|\bMYLAN\b',
        'EG': r'\bEG\b',
        'TEVA': r'\bTEVA\b',
        'CRISTERS': r'\bCRISTERS\b',
        'ZYDUS': r'\bZYDUS\b',
        'ACCORD': r'\bACCORD\b',
    }

    for labo, pattern in LABO_PATTERNS.items():
        if re.search(pattern, denomination, re.IGNORECASE):
            return labo
    return None
