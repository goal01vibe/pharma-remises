# PHASE 3 : Endpoints API

## Objectif
Implementer les nouveaux endpoints API avec pagination cursor-based.

## Pre-requis
- Phase 1 terminee (tables existent)
- Phase 2 terminee (services disponibles)

---

## 3.1 Pagination cursor-based (helper)

**Fichier** : `backend/app/api/pagination.py`

```python
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel
import base64
import json

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None
    total_count: int

def encode_cursor(data: dict) -> str:
    """Encode un dictionnaire en cursor base64."""
    return base64.b64encode(json.dumps(data).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    """Decode un cursor base64 en dictionnaire."""
    try:
        return json.loads(base64.b64decode(cursor.encode()).decode())
    except:
        return {}

def paginate_query(query, cursor: Optional[str], limit: int, id_field: str = 'id'):
    """
    Applique la pagination cursor-based a une query SQLAlchemy.

    Returns: (items, next_cursor)
    """
    if cursor:
        cursor_data = decode_cursor(cursor)
        last_id = cursor_data.get('last_id')
        if last_id:
            query = query.filter(getattr(query.column_descriptions[0]['entity'], id_field) > last_id)

    items = query.limit(limit + 1).all()

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        last_item = items[-1]
        next_cursor = encode_cursor({'last_id': getattr(last_item, id_field)})

    return items, next_cursor
```

---

## 3.2 Endpoint : Groupe details (pour drawer)

**Fichier** : `backend/app/api/groupe.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db
from ..services.pharma_preprocessing import extract_labo_from_denomination

router = APIRouter(prefix="/api/groupe", tags=["groupe"])

@router.get("/{groupe_id}/details")
async def get_groupe_details(groupe_id: int, db: Session = Depends(get_db)):
    """
    Retourne les details d'un groupe generique pour le drawer.
    """
    # Query sur la table directement (ou vue materialisee si existe)
    equivalents = db.execute(
        text("""
            SELECT cip13, denomination, type_generique, pfht
            FROM bdpm_equivalences
            WHERE groupe_generique_id = :groupe_id
            ORDER BY type_generique ASC, denomination ASC
        """),
        {"groupe_id": groupe_id}
    ).fetchall()

    if not equivalents:
        raise HTTPException(404, "Groupe non trouve")

    # Trouver le princeps
    princeps = None
    generiques = []
    for eq in equivalents:
        item = {
            "cip13": eq.cip13,
            "denomination": eq.denomination,
            "pfht": float(eq.pfht) if eq.pfht else None,
            "type_generique": eq.type_generique,
            "labo": extract_labo_from_denomination(eq.denomination)
        }
        if eq.type_generique == 0:
            princeps = item
        else:
            generiques.append(item)

    # Stats
    labos = set(g['labo'] for g in generiques if g['labo'])

    return {
        "groupe_id": groupe_id,
        "princeps": princeps,
        "equivalents": generiques,
        "stats": {
            "nb_labos": len(labos),
            "nb_references": len(generiques) + (1 if princeps else 0)
        }
    }
```

---

## 3.3 Endpoints : Validations

**Fichier** : `backend/app/api/validations.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..core.database import get_db
from ..services.audit_logger import AuditLogger
from .pagination import paginate_query, PaginatedResponse, encode_cursor, decode_cursor

router = APIRouter(prefix="/api/validations", tags=["validations"])

class ValidationItem(BaseModel):
    id: int
    validation_type: str
    source_cip13: Optional[str]
    source_designation: Optional[str]
    proposed_cip13: Optional[str]
    proposed_designation: Optional[str]
    proposed_pfht: Optional[float]
    match_score: Optional[float]
    status: str
    auto_validated: bool
    created_at: datetime

class ValidateRequest(BaseModel):
    ids: List[int]
    action: str  # 'validate' ou 'reject'

@router.get("/pending")
async def get_pending_validations(
    validation_type: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Liste les validations en attente avec pagination."""
    query = """
        SELECT id, validation_type, source_cip13, source_designation,
               proposed_cip13, proposed_designation, proposed_pfht,
               match_score, status, auto_validated, created_at
        FROM pending_validations
        WHERE status = 'pending'
    """
    params = {}

    if validation_type:
        query += " AND validation_type = :validation_type"
        params["validation_type"] = validation_type

    if cursor:
        cursor_data = decode_cursor(cursor)
        if cursor_data.get('last_id'):
            query += " AND id > :last_id"
            params["last_id"] = cursor_data['last_id']

    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit + 1

    results = db.execute(text(query), params).fetchall()

    items = results[:limit]
    next_cursor = None
    if len(results) > limit:
        next_cursor = encode_cursor({'last_id': items[-1].id})

    # Count total
    count_query = "SELECT COUNT(*) FROM pending_validations WHERE status = 'pending'"
    if validation_type:
        count_query += f" AND validation_type = '{validation_type}'"
    total = db.execute(text(count_query)).scalar()

    return {
        "items": [dict(row._mapping) for row in items],
        "next_cursor": next_cursor,
        "total_count": total
    }

@router.get("/stats")
async def get_validation_stats(db: Session = Depends(get_db)):
    """Stats des validations par type."""
    result = db.execute(text("""
        SELECT
            validation_type,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'validated') as validated,
            COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
            COUNT(*) FILTER (WHERE auto_validated = true) as auto_validated
        FROM pending_validations
        GROUP BY validation_type
    """)).fetchall()

    return {row.validation_type: {
        "pending": row.pending,
        "validated": row.validated,
        "rejected": row.rejected,
        "auto_validated": row.auto_validated
    } for row in result}

@router.post("/bulk-action")
async def bulk_validate(
    request_data: ValidateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Valide ou rejette plusieurs validations en masse."""
    audit = AuditLogger(db)

    if request_data.action == 'validate':
        new_status = 'validated'
    elif request_data.action == 'reject':
        new_status = 'rejected'
    else:
        raise HTTPException(400, "Action invalide")

    db.execute(
        text("""
            UPDATE pending_validations
            SET status = :status, validated_at = NOW()
            WHERE id = ANY(:ids)
        """),
        {"status": new_status, "ids": request_data.ids}
    )
    db.commit()

    audit.log(
        action=request_data.action,
        resource_type="validation",
        description=f"{len(request_data.ids)} validations {new_status}",
        metadata={"ids": request_data.ids},
        request=request
    )

    return {"updated": len(request_data.ids), "status": new_status}

@router.get("/count-pending")
async def count_pending(db: Session = Depends(get_db)):
    """Compte le nombre de validations en attente (pour badge header)."""
    count = db.execute(
        text("SELECT COUNT(*) FROM pending_validations WHERE status = 'pending'")
    ).scalar()
    return {"count": count}
```

---

## 3.4 Endpoint : Prix variations stats

**Fichier** : `backend/app/api/prix.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/prix", tags=["prix"])

@router.get("/variations/stats")
async def get_price_variation_stats(db: Session = Depends(get_db)):
    """
    Retourne les stats de variation de prix du dernier mois.
    Utilise pour le bandeau d'alerte dans le header.
    """
    result = db.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE variation_pct > 10) as hausses,
            COUNT(*) FILTER (WHERE variation_pct < -10) as baisses,
            MAX(ABS(variation_pct)) as variation_max
        FROM bdpm_prix_historique
        WHERE date_changement > NOW() - INTERVAL '30 days'
          AND ABS(variation_pct) > 10
    """)).fetchone()

    return {
        "total": result.total or 0,
        "hausses": result.hausses or 0,
        "baisses": result.baisses or 0,
        "variation_max": float(result.variation_max) if result.variation_max else 0
    }

@router.get("/historique/{cip13}")
async def get_price_history(cip13: str, db: Session = Depends(get_db)):
    """Historique des prix pour un CIP."""
    results = db.execute(text("""
        SELECT date_changement, pfht_ancien, pfht_nouveau, variation_pct, source_import
        FROM bdpm_prix_historique
        WHERE cip13 = :cip13
        ORDER BY date_changement DESC
        LIMIT 20
    """), {"cip13": cip13}).fetchall()

    return [dict(row._mapping) for row in results]
```

---

## 3.5 Enregistrer les routers dans main.py

**Modifier** : `backend/main.py`

```python
# Ajouter les imports
from app.api.groupe import router as groupe_router
from app.api.validations import router as validations_router
from app.api.prix import router as prix_router

# Ajouter les routers
app.include_router(groupe_router)
app.include_router(validations_router)
app.include_router(prix_router)
```

---

## Tests a effectuer

### Demarrer le serveur

```bash
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/pharma_remises_test uvicorn main:app --reload --port 8001
```

### Tests manuels avec curl

```bash
# Test pagination helper
curl -s http://localhost:8001/api/validations/pending?limit=5 | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'next_cursor' in d else 'FAIL')"

# Test groupe details (remplacer 1234 par un vrai groupe_id)
curl -s http://localhost:8001/api/groupe/1/details | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'groupe_id' in d else 'FAIL: '+str(d))"

# Test validations pending
curl -s http://localhost:8001/api/validations/pending | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'items' in d and 'total_count' in d else 'FAIL')"

# Test validations stats
curl -s http://localhost:8001/api/validations/stats | python -c "import sys,json; d=json.load(sys.stdin); print('OK - types:', list(d.keys()))"

# Test count-pending
curl -s http://localhost:8001/api/validations/count-pending | python -c "import sys,json; d=json.load(sys.stdin); print('OK count=' + str(d.get('count')))"

# Test prix variations stats
curl -s http://localhost:8001/api/prix/variations/stats | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'total' in d else 'FAIL')"

# Test prix historique
curl -s http://localhost:8001/api/prix/historique/3400930000001 | python -c "import sys,json; d=json.load(sys.stdin); print('OK - entries:', len(d))"
```

---

## Script de test automatise

**Fichier** : `backend/tests/test_phase3_endpoints.py`

```python
"""Tests Phase 3 - Endpoints API"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
import base64
import json

# Importer l'app
from main import app

client = TestClient(app)


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
        except:
            assert False, "Cursor is not valid base64"


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
        """))
        db.commit()

        response = client.get("/api/groupe/99999/details")
        assert response.status_code == 200
        data = response.json()

        assert 'groupe_id' in data
        assert 'princeps' in data
        assert 'equivalents' in data
        assert 'stats' in data
        assert data['stats']['nb_references'] >= 1

        # Cleanup
        db.execute(text("DELETE FROM bdpm_equivalences WHERE groupe_generique_id = 99999"))
        db.commit()

    def test_groupe_details_not_found(self):
        response = client.get("/api/groupe/0/details")
        assert response.status_code == 404

    def test_groupe_details_returns_princeps(self, db):
        db.execute(text("""
            INSERT INTO bdpm_equivalences (cip13, denomination, groupe_generique_id, type_generique, pfht)
            VALUES ('9999999999901', 'PRINCEPS REF', 88888, 0, 15.0)
        """))
        db.commit()

        response = client.get("/api/groupe/88888/details")
        data = response.json()

        assert data['princeps'] is not None
        assert data['princeps']['type_generique'] == 0

        db.execute(text("DELETE FROM bdpm_equivalences WHERE groupe_generique_id = 88888"))
        db.commit()


class TestValidationsEndpoints:
    """Tests pour /api/validations endpoints"""

    def test_pending_returns_paginated(self, db):
        # Insert test validations
        for i in range(15):
            db.execute(text("""
                INSERT INTO pending_validations (validation_type, source_cip13, status)
                VALUES ('test', :cip, 'pending')
            """), {'cip': f'999999999{i:04d}'})
        db.commit()

        response = client.get("/api/validations/pending?limit=10")
        assert response.status_code == 200
        data = response.json()

        assert 'items' in data
        assert 'next_cursor' in data
        assert 'total_count' in data
        assert len(data['items']) <= 10
        assert data['total_count'] >= 15

        # Test with cursor
        if data['next_cursor']:
            response2 = client.get(f"/api/validations/pending?limit=10&cursor={data['next_cursor']}")
            assert response2.status_code == 200
            data2 = response2.json()
            assert len(data2['items']) > 0

        # Cleanup
        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test'"))
        db.commit()

    def test_pending_filter_by_type(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('fuzzy_match', 'pending'), ('cip_exact', 'pending')
        """))
        db.commit()

        response = client.get("/api/validations/pending?validation_type=fuzzy_match")
        data = response.json()

        for item in data['items']:
            assert item['validation_type'] == 'fuzzy_match'

        db.execute(text("DELETE FROM pending_validations WHERE validation_type IN ('fuzzy_match', 'cip_exact')"))
        db.commit()

    def test_stats_returns_by_type(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status, auto_validated)
            VALUES
            ('fuzzy_match', 'pending', false),
            ('fuzzy_match', 'validated', false),
            ('cip_exact', 'pending', true)
        """))
        db.commit()

        response = client.get("/api/validations/stats")
        assert response.status_code == 200
        data = response.json()

        assert 'fuzzy_match' in data or 'cip_exact' in data

        db.execute(text("DELETE FROM pending_validations WHERE validation_type IN ('fuzzy_match', 'cip_exact')"))
        db.commit()

    def test_count_pending(self, db):
        db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('test_count', 'pending'), ('test_count', 'pending')
        """))
        db.commit()

        response = client.get("/api/validations/count-pending")
        assert response.status_code == 200
        data = response.json()

        assert 'count' in data
        assert data['count'] >= 2

        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test_count'"))
        db.commit()

    def test_bulk_action_validate(self, db):
        # Insert test data
        result = db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('test_bulk', 'pending')
            RETURNING id
        """))
        db.commit()
        test_id = result.fetchone()[0]

        response = client.post("/api/validations/bulk-action", json={
            "ids": [test_id],
            "action": "validate"
        })
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'validated'
        assert data['updated'] == 1

        # Verify status changed
        result = db.execute(text(
            "SELECT status FROM pending_validations WHERE id = :id"
        ), {'id': test_id}).fetchone()
        assert result[0] == 'validated'

        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test_bulk'"))
        db.commit()

    def test_bulk_action_reject(self, db):
        result = db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('test_reject', 'pending')
            RETURNING id
        """))
        db.commit()
        test_id = result.fetchone()[0]

        response = client.post("/api/validations/bulk-action", json={
            "ids": [test_id],
            "action": "reject"
        })
        assert response.status_code == 200
        assert response.json()['status'] == 'rejected'

        db.execute(text("DELETE FROM pending_validations WHERE validation_type = 'test_reject'"))
        db.commit()

    def test_bulk_action_invalid(self):
        response = client.post("/api/validations/bulk-action", json={
            "ids": [1],
            "action": "invalid_action"
        })
        assert response.status_code == 400


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

        response = client.get("/api/prix/variations/stats")
        assert response.status_code == 200
        data = response.json()

        assert 'total' in data
        assert 'hausses' in data
        assert 'baisses' in data
        assert 'variation_max' in data

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

        response = client.get("/api/prix/historique/9999999999999")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 2

        db.execute(text("DELETE FROM bdpm_prix_historique WHERE cip13 = '9999999999999'"))
        db.commit()

    def test_historique_empty(self):
        response = client.get("/api/prix/historique/0000000000000")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestAuditLogging:
    """Tests que les actions sont loguees"""

    def test_bulk_action_creates_audit_log(self, db):
        # Insert test validation
        result = db.execute(text("""
            INSERT INTO pending_validations (validation_type, status)
            VALUES ('audit_test', 'pending')
            RETURNING id
        """))
        db.commit()
        test_id = result.fetchone()[0]

        # Perform action
        client.post("/api/validations/bulk-action", json={
            "ids": [test_id],
            "action": "validate"
        })

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


class TestRoutersRegistered:
    """Tests que tous les routers sont enregistres"""

    def test_groupe_router_registered(self):
        response = client.get("/api/groupe/1/details")
        # Should not be 404 "Not Found" for the route itself
        assert response.status_code != 404 or 'non trouve' in response.text.lower()

    def test_validations_router_registered(self):
        response = client.get("/api/validations/pending")
        assert response.status_code in [200, 500]  # 500 if DB issue, but route exists

    def test_prix_router_registered(self):
        response = client.get("/api/prix/variations/stats")
        assert response.status_code in [200, 500]
```

---

## Commande pour executer tous les tests Phase 3

```bash
cd backend
# Demarrer le serveur en background
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/pharma_remises_test uvicorn main:app --port 8001 &

# Attendre que le serveur demarre
sleep 3

# Executer les tests
pytest tests/test_phase3_endpoints.py -v --tb=short

# Arreter le serveur
pkill -f "uvicorn main:app"
```

---

## Criteres de validation Phase 3

- [ ] `pagination.py` helper cree
  - [ ] encode_cursor() retourne base64 valide
  - [ ] decode_cursor() parse correctement
  - [ ] decode_cursor() gere les erreurs
- [ ] `/api/groupe/{id}/details`
  - [ ] Retourne 200 avec structure complete
  - [ ] Retourne 404 si groupe inexistant
  - [ ] Inclut princeps et equivalents
  - [ ] Inclut stats (nb_labos, nb_references)
- [ ] `/api/validations/pending`
  - [ ] Retourne items + next_cursor + total_count
  - [ ] Pagination fonctionne avec cursor
  - [ ] Filtre par validation_type fonctionne
- [ ] `/api/validations/stats`
  - [ ] Retourne stats par type
  - [ ] Inclut pending, validated, rejected, auto_validated
- [ ] `/api/validations/bulk-action`
  - [ ] Action 'validate' fonctionne
  - [ ] Action 'reject' fonctionne
  - [ ] Action invalide retourne 400
  - [ ] Cree un audit log
- [ ] `/api/validations/count-pending`
  - [ ] Retourne {count: N}
- [ ] `/api/prix/variations/stats`
  - [ ] Retourne total, hausses, baisses, variation_max
- [ ] `/api/prix/historique/{cip13}`
  - [ ] Retourne liste d'historique
  - [ ] Retourne [] si pas d'historique
- [ ] Routers enregistres dans main.py
  - [ ] groupe_router
  - [ ] validations_router
  - [ ] prix_router
- [ ] `pytest tests/test_phase3_endpoints.py` passe

---

## Apres cette phase

Executer `/compact` puis passer a Phase 4 : `docs/architecture/PHASE4_VUES.md`
