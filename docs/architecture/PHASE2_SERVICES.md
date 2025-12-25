# PHASE 2 : Services Backend

## Objectif
Implementer les services metier : MatchingService, AuditLogger, et fonctions de preprocessing.

## Pre-requis
- Phase 1 terminee (migrations appliquees)
- Tables `matching_memory`, `audit_logs`, `pending_validations` existent

---

## 2.1 Preprocessing pharmaceutique

**Fichier** : `backend/app/services/pharma_preprocessing.py`

```python
import re
from typing import Set

# Labos a supprimer du texte pour matching
LABOS_CONNUS: Set[str] = {
    'viatris', 'zentiva', 'biogaran', 'sandoz', 'teva', 'mylan', 'arrow',
    'eg', 'cristers', 'accord', 'ranbaxy', 'zydus', 'sun', 'almus', 'bgr',
    'ratiopharm', 'actavis', 'winthrop', 'pfizer', 'sanofi', 'bayer',
}

# Formes a normaliser
FORMES_MAPPING = {
    'cpr': 'comprime', 'cp': 'comprime', 'comp': 'comprime',
    'gel': 'gelule', 'caps': 'capsule', 'sol': 'solution',
    'susp': 'suspension', 'inj': 'injectable', 'cr': 'creme',
    'pom': 'pommade', 'suppo': 'suppositoire', 'pdre': 'poudre',
}

def preprocess_pharma(text: str) -> str:
    """
    Normalise les noms pharma avant matching fuzzy.
    Ameliore la precision en supprimant le bruit (labos, abreviations).
    """
    if not text:
        return ""

    result = text.upper()

    # 1. Supprimer les noms de labos
    for labo in LABOS_CONNUS:
        result = re.sub(rf'\b{labo.upper()}\b', '', result)

    # 2. Normaliser les formes (CPR -> COMPRIME)
    for abbr, full in FORMES_MAPPING.items():
        result = re.sub(rf'\b{abbr.upper()}\b', full.upper(), result)

    # 3. Normaliser dosages (40 mg -> 40MG, supprimer espaces)
    result = re.sub(r'(\d+)\s*(MG|G|ML|MCG|UI)', r'\1\2', result)

    # 4. Supprimer conditionnement (B/30, BTE 30, etc.)
    result = re.sub(r'\bB/?(\d+)\b', '', result)
    result = re.sub(r'\b(BTE|BOITE|PLQ)\s*\d+\b', '', result)

    # 5. Nettoyer espaces multiples
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def extract_labo_from_denomination(denomination: str) -> str | None:
    """Extrait le nom du labo depuis la denomination BDPM."""
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
```

---

## 2.2 Batch Matching avec RapidFuzz

**Fichier** : `backend/app/services/batch_matching.py`

```python
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
    Match une fois, stocke pour toujours.
    Utilise cdist pour matching matriciel ultra-rapide.

    Performance: ~10,000 ventes vs ~50,000 BDPM en < 5 secondes
    """
    # Preprocessing pharma avant matching
    vente_names = [preprocess_pharma(v['designation']) for v in ventes]
    bdpm_names = [preprocess_pharma(b['denomination']) for b in bdpm]

    # Calcul matriciel (utilise tous les CPU)
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
                'source_designation': vente['designation'],
                'matched_cip13': bdpm[best_idx]['cip13'],
                'matched_designation': bdpm[best_idx]['denomination'],
                'match_score': best_score,
                'match_type': 'fuzzy',
                'pfht': bdpm[best_idx].get('pfht')
            })
        else:
            results.append({
                'source_cip13': vente.get('cip13'),
                'source_designation': vente['designation'],
                'matched_cip13': None,
                'match_score': best_score,
                'match_type': 'no_match',
                'pfht': None
            })

    return results
```

---

## 2.3 MatchingService avec cache

**Fichier** : `backend/app/services/matching_service.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from .batch_matching import batch_match_products
from ..models.models import MatchingMemory, BdpmEquivalence

class MatchingService:
    """
    Service de matching avec cache.
    Ne recalcule que les nouveaux CIP.
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Charger le cache depuis matching_memory"""
        matches = self.db.query(MatchingMemory).filter(
            MatchingMemory.validated == True
        ).all()
        self._cache = {m.cip13: {
            'matched_cip13': m.matched_cip13,
            'matched_denomination': m.matched_denomination,
            'match_score': m.match_score,
            'match_origin': m.match_origin,
            'pfht': float(m.pfht) if m.pfht else None,
            'groupe_generique_id': m.groupe_generique_id
        } for m in matches}

    def get_or_compute_match(self, cip13: str, designation: str) -> Dict:
        """
        Retourne le match cache ou le calcule si nouveau.
        """
        # Cache hit = instantane
        if cip13 in self._cache:
            return self._cache[cip13]

        # Cache miss = calculer et stocker
        match = self._compute_single_match(designation)
        if match['matched_cip13']:
            self._store_match(cip13, designation, match)
        return match

    def _compute_single_match(self, designation: str) -> Dict:
        """Calcule le match pour une designation."""
        bdpm_refs = self.db.query(BdpmEquivalence).filter(
            BdpmEquivalence.pfht.isnot(None)
        ).all()

        bdpm_list = [{'cip13': b.cip13, 'denomination': b.denomination, 'pfht': b.pfht}
                     for b in bdpm_refs]

        results = batch_match_products(
            [{'designation': designation}],
            bdpm_list,
            score_threshold=70.0
        )
        return results[0] if results else {'matched_cip13': None, 'match_score': 0}

    def _store_match(self, cip13: str, designation: str, match: Dict):
        """Stocke un nouveau match dans matching_memory."""
        memory = MatchingMemory(
            cip13=cip13,
            designation=designation,
            matched_cip13=match.get('matched_cip13'),
            matched_denomination=match.get('matched_designation'),
            match_score=match.get('match_score'),
            match_origin=match.get('match_type'),
            pfht=match.get('pfht'),
            validated=False  # Require validation
        )
        self.db.add(memory)
        self.db.commit()

    def batch_process_ventes(self, ventes: List[Dict]) -> Dict:
        """
        Traite un lot de ventes.
        Separe les cache hits des calculs necessaires.
        """
        cached = []
        to_compute = []

        for v in ventes:
            cip = v.get('code_cip_achete')
            if cip in self._cache:
                result = self._cache[cip].copy()
                result['source_cip13'] = cip
                result['source_designation'] = v.get('designation')
                cached.append(result)
            else:
                to_compute.append(v)

        # Batch compute seulement les nouveaux
        computed = []
        if to_compute:
            bdpm_refs = self.db.query(BdpmEquivalence).filter(
                BdpmEquivalence.pfht.isnot(None)
            ).all()
            bdpm_list = [{'cip13': b.cip13, 'denomination': b.denomination, 'pfht': b.pfht}
                         for b in bdpm_refs]

            vente_list = [{'cip13': v.get('code_cip_achete'), 'designation': v.get('designation')}
                          for v in to_compute]

            new_matches = batch_match_products(vente_list, bdpm_list)

            for match in new_matches:
                if match['source_cip13']:
                    self._store_match(
                        match['source_cip13'],
                        match['source_designation'],
                        match
                    )
                computed.append(match)

        return {
            'total': len(ventes),
            'from_cache': len(cached),
            'computed': len(computed),
            'results': cached + computed
        }
```

---

## 2.4 AuditLogger

**Fichier** : `backend/app/services/audit_logger.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Request
from typing import Optional, Dict
import json

class AuditLogger:
    """Service de logging d'audit."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        description: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        request: Optional[Request] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """
        Enregistre un evenement d'audit.
        """
        # Extraire infos de la requete si disponible
        user_email = None
        ip_address = None
        user_agent = None

        if request:
            user_email = getattr(request.state, 'user_email', None)
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get('user-agent')

        self.db.execute(
            text("""
                INSERT INTO audit_logs (
                    user_email, ip_address, user_agent,
                    action, resource_type, resource_id,
                    description, old_values, new_values, metadata,
                    status, error_message
                ) VALUES (
                    :user_email, :ip_address, :user_agent,
                    :action, :resource_type, :resource_id,
                    :description, :old_values, :new_values, :metadata,
                    :status, :error_message
                )
            """),
            {
                "user_email": user_email,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "description": description,
                "old_values": json.dumps(old_values) if old_values else None,
                "new_values": json.dumps(new_values) if new_values else None,
                "metadata": json.dumps(metadata) if metadata else None,
                "status": status,
                "error_message": error_message
            }
        )
        self.db.commit()
```

---

## 2.5 Auto-validation thresholds

**Fichier** : `backend/app/services/auto_validation.py`

```python
from typing import Dict

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

def should_auto_validate(match_type: str, score: float, context: dict) -> bool:
    """
    Determine si un match doit etre auto-valide selon les seuils.
    """
    config = AUTO_VALIDATION_THRESHOLDS.get(match_type, {})

    # Types toujours auto-valides
    if config.get('auto_validate') is True:
        return True

    # Types jamais auto-valides
    if config.get('auto_validate') is False:
        return False

    # Fuzzy match : verification multi-criteres
    if match_type == 'fuzzy_match':
        if score < config.get('score_min', 95.0):
            return False
        if config.get('same_groupe') and context.get('source_groupe') != context.get('target_groupe'):
            return False
        if config.get('same_dosage') and context.get('source_dosage') != context.get('target_dosage'):
            return False
        return True

    return False
```

---

## Tests a effectuer

### Tests manuels rapides

```bash
cd backend

# Test preprocessing
python -c "
from app.services.pharma_preprocessing import preprocess_pharma, extract_labo_from_denomination
print('Test 1:', preprocess_pharma('AMLODIPINE BIOGARAN 5MG CPR B/30'))
# Attendu: 'AMLODIPINE 5MG COMPRIME'
print('Test 2:', preprocess_pharma('METFORMINE SANDOZ 1000 MG BTE 30'))
# Attendu: 'METFORMINE 1000MG'
print('Test 3:', extract_labo_from_denomination('AMLODIPINE BIOGARAN 5 mg'))
# Attendu: 'BIOGARAN'
print('Test 4:', extract_labo_from_denomination('DOLIPRANE 1000 mg'))
# Attendu: None
"

# Test batch matching
python -c "
from app.services.batch_matching import batch_match_products
ventes = [
    {'designation': 'AMLODIPINE 5MG'},
    {'designation': 'METFORMINE 1000MG'},
    {'designation': 'PRODUIT INCONNU XYZ'}
]
bdpm = [
    {'cip13': '3400930000001', 'denomination': 'AMLODIPINE EG 5MG CPR', 'pfht': 2.5},
    {'cip13': '3400930000002', 'denomination': 'METFORMINE SANDOZ 1000MG', 'pfht': 3.0}
]
results = batch_match_products(ventes, bdpm)
for r in results:
    print(f\"{r['source_designation']} -> {r['matched_cip13']} (score: {r['match_score']:.1f})\")
"

# Test auto-validation
python -c "
from app.services.auto_validation import should_auto_validate
print('Score 96 fuzzy:', should_auto_validate('fuzzy_match', 96.0, {}))  # True
print('Score 80 fuzzy:', should_auto_validate('fuzzy_match', 80.0, {}))  # False
print('CIP exact:', should_auto_validate('cip_exact', 100.0, {}))  # True
print('Nouveau produit:', should_auto_validate('nouveau_produit', 100.0, {}))  # False
"
```

---

## Script de test automatise

**Fichier** : `backend/tests/test_phase2_services.py`

```python
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
        assert '30' not in result or 'BTE 30' not in result

    def test_preprocess_handles_empty_string(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        assert preprocess_pharma('') == ''
        assert preprocess_pharma(None) == ''

    def test_preprocess_multiple_labos(self):
        from app.services.pharma_preprocessing import preprocess_pharma
        # Doit supprimer tous les labos connus
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
        # Avec threshold 90, ne devrait pas matcher
        results = batch_match_products(ventes, bdpm, score_threshold=90.0)
        assert results[0]['matched_cip13'] is None


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
        import json
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
            INSERT INTO matching_memory (cip13, designation, matched_cip13, match_score, validated)
            VALUES ('9999999999999', 'TEST CACHE', '8888888888888', 95.0, true)
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


# Tests de performance
class TestPerformance:
    """Tests de performance pour les services."""

    def test_preprocessing_performance(self, benchmark):
        from app.services.pharma_preprocessing import preprocess_pharma
        # Doit traiter 1000 items en moins de 1 seconde
        items = ['AMLODIPINE BIOGARAN 5MG CPR B/30'] * 1000

        def process_all():
            return [preprocess_pharma(item) for item in items]

        result = benchmark(process_all)
        assert len(result) == 1000

    def test_batch_matching_performance(self, benchmark):
        from app.services.batch_matching import batch_match_products
        # Setup
        ventes = [{'designation': f'MEDICAMENT {i} MG'} for i in range(100)]
        bdpm = [{'cip13': str(i), 'denomination': f'MEDICAMENT {i} MG CPR', 'pfht': float(i)} for i in range(500)]

        result = benchmark(batch_match_products, ventes, bdpm)
        assert len(result) == 100
```

---

## Fichier conftest.py pour les tests

**Fichier** : `backend/tests/conftest.py`

```python
"""Configuration pytest pour les tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL_TEST = os.getenv(
    'DATABASE_URL_TEST',
    'postgresql://postgres:postgres@localhost:5433/pharma_remises_test'
)

@pytest.fixture(scope='session')
def engine():
    return create_engine(DATABASE_URL_TEST)

@pytest.fixture(scope='function')
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

---

## Commande pour executer tous les tests Phase 2

```bash
cd backend
pytest tests/test_phase2_services.py -v --tb=short
```

---

## Criteres de validation Phase 2

- [ ] `pharma_preprocessing.py` cree
  - [ ] preprocess_pharma() supprime les labos
  - [ ] preprocess_pharma() normalise les formes (CPR -> COMPRIME)
  - [ ] preprocess_pharma() normalise les dosages (10 MG -> 10MG)
  - [ ] preprocess_pharma() supprime le conditionnement (B/30)
  - [ ] extract_labo_from_denomination() detecte les labos
- [ ] `batch_matching.py` cree
  - [ ] Match exact fonctionne (score > 95)
  - [ ] Match fuzzy fonctionne (score > 70)
  - [ ] No match retourne matched_cip13 = None
  - [ ] Performance: 100 ventes vs 500 BDPM < 2s
- [ ] `matching_service.py` cree
  - [ ] Cache hit instantane
  - [ ] Cache miss calcule et stocke
  - [ ] batch_process_ventes() fonctionne
- [ ] `audit_logger.py` cree
  - [ ] log() cree une entree dans audit_logs
  - [ ] Metadata JSONB fonctionne
  - [ ] old_values/new_values stockes
- [ ] `auto_validation.py` cree
  - [ ] fuzzy_match score >= 95 -> auto-valide
  - [ ] cip_exact -> auto-valide
  - [ ] nouveau_produit -> jamais auto-valide
- [ ] `pytest tests/test_phase2_services.py` passe (tous les tests)

---

## Apres cette phase

Executer `/compact` puis passer a Phase 3 : `docs/architecture/PHASE3_ENDPOINTS.md`
