# Architecture Future - Pharma-Remises

Ce document liste les fonctionnalites a implementer dans les prochaines versions.

---

## 1. SYSTEME DE VALIDATION OBLIGATOIRE (Fuzzy Matching)

### 1.1 Concept

Quand le systeme ne trouve pas un CIP exact lors du rapprochement, il propose un rattachement base sur la similarite du nom (fuzzy matching). Ces propositions doivent etre validees manuellement.

**Exemple :**
```
Vente : "AMOXICILLINE 500MG BIOGARAN" (CIP inconnu)
    | fuzzy match (score 85%)
    v
Proposition : Rattacher au groupe generique "AMOXICILLINE 500 mg"
    |
    v
En attente de validation par l'utilisateur
```

### 1.2 Table existante

La table `pending_validations` existe deja :

```sql
CREATE TABLE pending_validations (
    id SERIAL PRIMARY KEY,
    validation_type VARCHAR(30) NOT NULL,  -- 'fuzzy_match', 'prix_groupe', 'nouveau_produit'
    source_cip13 VARCHAR(13),
    source_designation TEXT,
    proposed_cip13 VARCHAR(13),
    proposed_designation TEXT,
    proposed_pfht DECIMAL(10,4),
    proposed_groupe_id INT,
    match_score FLOAT,
    auto_source VARCHAR(50),               -- 'rapidfuzz', 'groupe_generique', 'bdpm_import'
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'validated', 'rejected', 'auto_validated'
    auto_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP
);
```

### 1.3 Middleware de blocage (existe deja)

Le middleware `PendingValidationsMiddleware` bloque les simulations si des validations sont en attente.

### 1.4 A implementer : Interface Frontend

**Page /validations avec onglets :**
```
+------------------------------------------------------------------+
| VALIDATIONS EN ATTENTE                                           |
+------------------------------------------------------------------+
| [Fuzzy: 12]  [Prix Auto: 3]  [Nouveaux: 5]  |  TOTAL: 20        |
+------------------------------------------------------------------+

| SEL | PRODUIT VENDU           | PROPOSITION            | SCORE   |
+-----+-------------------------+------------------------+---------+
| [x] | AMLODIPINE BIOGARAN 5MG | AMLODIPINE EG 5MG     | 95%     |
| [x] | METFORMINE SANDOZ 850MG | METFORMINE MYLAN 850MG| 88%     |
| [ ] | PRODUIT DOUTEUX XYZ     | AUTRE PRODUIT ABC     | 71%     |
+-----+-------------------------+------------------------+---------+
| [VALIDER SELECTIONNES]        [REJETER NON SELECTIONNES]         |
+------------------------------------------------------------------+
```

**Actions :**
- Valider = Deplace vers `matching_memory`, utilisable immediatement
- Rejeter = Status 'rejected', option d'ajouter a la blacklist

### 1.5 Seuils d'auto-validation

```python
AUTO_VALIDATION_THRESHOLDS = {
    'fuzzy_match': {'score_min': 95.0, 'same_groupe': True},
    'prix_groupe': {'auto_validate': True},
    'cip_exact': {'auto_validate': True},
    'groupe_generique': {'auto_validate': True},
    'nouveau_produit': {'auto_validate': False},  # Toujours manuel
}
```

### 1.6 Checklist

- [ ] Creer page `/validations` avec onglets
- [ ] Endpoint `GET /api/validations/pending`
- [ ] Endpoint `POST /api/validations/{id}/validate`
- [ ] Endpoint `POST /api/validations/{id}/reject`
- [ ] Indicateur dans le Header (badge rouge si validations en attente)
- [ ] Modal de blocage quand action bloquee

---

## 2. ALERTES VARIATIONS PRIX BDPM

### 2.1 Concept

Afficher une alerte quand des prix BDPM ont varie de plus de 10% lors du dernier import.

### 2.2 Table existante

La table `bdpm_prix_historique` existe deja et stocke l'historique des changements.

### 2.3 A implementer : Bandeau d'alerte

```tsx
<Alert variant="warning">
  <AlertTriangle className="h-4 w-4" />
  <strong>12 prix</strong> ont varie de plus de 10% ce mois :
  <span className="text-red-600">8 hausses</span>
  <span className="text-green-600">4 baisses</span>
  <Button>Voir details</Button>
</Alert>
```

### 2.4 Checklist

- [ ] Endpoint `GET /api/repertoire/prix-variations/stats`
- [ ] Composant `PriceAlertBanner.tsx`
- [ ] Integrer dans page Repertoire
- [ ] Modal historique prix au clic sur un produit

---

## 3. ~~EXTENSION LABOS CIBLES~~ (TERMINE)

### Resultat

**14 labos supportes** (ajoutes le 2024-12-24) :

| Phase | Labos | Nb produits |
|-------|-------|-------------|
| Initial | BIOGARAN, SANDOZ, ARROW, ZENTIVA, VIATRIS | - |
| Phase 1 | EG, TEVA, CRISTERS, ZYDUS, ACCORD | - |
| Phase 2 | EVOLUGEN, KRKA, ALMUS, SUN | ~500 |

Fichier modifie : `backend/app/services/bdpm_import.py` (LAB_PATTERNS)

---

## 4. TESTS AUTOMATISES PERFORMANCE

### 4.1 Objectifs

- Matching batch 1000 ventes < 100ms
- Lookup cache < 10ms
- Vue materialisee < 5ms

### 4.2 A implementer

```python
# tests/performance/test_matching_performance.py
def test_batch_matching_under_100ms(sample_ventes, sample_bdpm):
    start = time.perf_counter()
    results = batch_match_products(sample_ventes, sample_bdpm)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 100, f"Trop lent: {elapsed:.2f}ms"
```

### 4.3 Checklist

- [ ] Creer dossier `tests/performance/`
- [ ] Tests matching batch
- [ ] Tests lookup cache
- [ ] Tests vues materialisees
- [ ] Integration CI/CD

---

## 5. EXPORT PDF/EXCEL AVANCE

### 5.1 Concept

Generer des rapports PDF professionnels avec graphiques pour les simulations.

### 5.2 Contenu du rapport

- Resume executif (KPIs)
- Graphique repartition par labo
- Tableau detaille des produits
- Comparaison avec simulation precedente

### 5.3 Technologies

- WeasyPrint ou ReportLab pour PDF
- openpyxl pour Excel avec mise en forme

---

**Derniere mise a jour** : 2024-12-24
