# Architecture Future - Pharma-Remises

## Objectif

Optimiser le systeme de matching pour qu'il soit fait UNE SEULE FOIS et reutilise instantanement pour toutes les simulations/rapprochements ulterieurs.

---

## 1. SCHEMA DATABASE OPTIMISE

### 1.1 Signature moleculaire (colonne calculee)

**OPTIMISATION** : Plutot que creer une table separee `canonical_products`, on ajoute une colonne calculee a `bdpm_equivalences` existante. Cela evite la synchronisation et la redondance.

```sql
-- Activer les extensions necessaires
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- Ajouter colonne calculee pour signature moleculaire
-- Extrait "AMLODIPINE 5 mg" depuis libelle_groupe "AMLODIPINE 5 mg - AMLOR 5 mg, comprime"
ALTER TABLE bdpm_equivalences
ADD COLUMN molecule_signature TEXT GENERATED ALWAYS AS (
    UPPER(TRIM(split_part(libelle_groupe, ' - ', 1)))
) STORED;

-- Ajouter colonne labo extrait depuis denomination
-- Pour calculs stats fiables (evite regex fragile)
ALTER TABLE bdpm_equivalences
ADD COLUMN labo_extracted VARCHAR(50);

-- Index trigram pour recherche fuzzy rapide sur signature
CREATE INDEX idx_bdpm_signature_trgm ON bdpm_equivalences
    USING gin (molecule_signature gin_trgm_ops);

-- Index sur labo extrait pour stats groupees
CREATE INDEX idx_bdpm_labo ON bdpm_equivalences(labo_extracted);
```

**Peuplement du labo extrait (a l'import BDPM)** :
```python
# Dans bdpm_import.py - extraction labo depuis denomination
def extract_labo_from_denomination(denomination: str) -> Optional[str]:
    """Extrait le nom du labo depuis la denomination BDPM."""
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

### 1.2 Enrichissement de matching_memory (pas de nouvelle table)

**OPTIMISATION** : La table `matching_memory` existe deja (migration 005) avec une structure similaire.
Plutot que creer une nouvelle table `product_matches`, on enrichit `matching_memory` avec les colonnes manquantes.

**Structure actuelle de `matching_memory`** :
- `cip13` (UNIQUE) - deja present
- `designation` - deja present
- `groupe_generique_id` - deja present
- `match_origin` - deja present
- `match_score` - deja present
- `validated` / `validated_at` - deja present

**Colonnes a ajouter** :
```sql
-- Enrichir matching_memory avec les colonnes manquantes pour le cache complet
ALTER TABLE matching_memory
ADD COLUMN IF NOT EXISTS matched_cip13 VARCHAR(13),          -- CIP BDPM correspondant
ADD COLUMN IF NOT EXISTS matched_denomination TEXT,          -- Nom du produit matche
ADD COLUMN IF NOT EXISTS pfht DECIMAL(10,4),                 -- Prix PFHT du match
ADD COLUMN IF NOT EXISTS matched_at TIMESTAMP DEFAULT NOW(); -- Date du match

-- Index supplementaires pour lookups rapides
CREATE INDEX IF NOT EXISTS idx_matching_matched_cip ON matching_memory(matched_cip13);
CREATE INDEX IF NOT EXISTS idx_matching_type ON matching_memory(match_origin);
CREATE INDEX IF NOT EXISTS idx_matching_score ON matching_memory(match_score DESC);
```

**Avantages de cette approche** :
- Pas de nouvelle table a synchroniser
- Reutilise la logique de groupes transitifs existante
- Le champ `validated` permet de distinguer les matchs automatiques des matchs valides

### 1.3 Colonne de tracking BDPM

Ajouter a la table `bdpm_equivalence` existante :

```sql
-- Colonne pour identifier les nouvelles entrees
ALTER TABLE bdpm_equivalence
ADD COLUMN IF NOT EXISTS integrated_at TIMESTAMP DEFAULT NOW();

-- Index pour tri par date d'integration
CREATE INDEX idx_bdpm_integrated ON bdpm_equivalence(integrated_at DESC);
```

---

## 2. WORKFLOW OPTIMISE

### 2.1 Import BDPM (mensuel)

```
1. Telecharger fichier ANSM
2. Parser et comparer avec existant
3. Pour chaque NOUVELLE reference :
   - Marquer integrated_at = NOW()
   - Extraire signature moleculaire
   - Creer/MAJ dans canonical_products
4. Rafraichir les index
```

### 2.2 Import Ventes

```
1. Charger fichier CSV/Excel
2. Pour chaque ligne :
   a. Verifier si CIP existe dans product_matches
      - OUI : Lookup instantane (pas de calcul)
      - NON : Ajouter a la queue de matching
3. Pour les CIP inconnus :
   - Batch RapidFuzz avec cdist()
   - Stocker resultats dans product_matches
4. Retourner resultats (tout est pre-calcule)
```

### 2.3 Simulation / Rapprochement

```sql
-- Simple JOIN, pas de fuzzy = instantane
SELECT
    v.code_cip_achete,
    v.designation AS produit_vendu,
    pm.matched_cip13,
    b.denomination AS produit_catalogue,
    pm.match_type,
    pm.match_score,
    v.quantite_annuelle AS qte,
    pm.pfht,
    (v.quantite_annuelle * pm.pfht) AS montant_ligne
FROM mes_ventes v
JOIN product_matches pm ON v.code_cip_achete = pm.source_cip13
JOIN bdpm_equivalence b ON pm.matched_cip13 = b.cip13
WHERE v.import_id = :import_id;
```

---

## 3. OPTIMISATIONS POSTGRESQL

### 3.1 Index GIN pour recherche fuzzy

```sql
-- Index sur denomination pour recherche rapide
CREATE INDEX idx_bdpm_denomination_trgm
    ON bdpm_equivalence USING gin (denomination gin_trgm_ops);

-- Index sur princeps_denomination
CREATE INDEX idx_bdpm_princeps_trgm
    ON bdpm_equivalence USING gin (princeps_denomination gin_trgm_ops);
```

### 3.2 Fonction de matching hybride

```sql
-- Fonction : Soundex (pre-filtre rapide) + Trigram (precision)
CREATE OR REPLACE FUNCTION find_best_match(search_term TEXT)
RETURNS TABLE(cip13 VARCHAR, denomination TEXT, score FLOAT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.cip13,
        b.denomination,
        similarity(b.denomination, search_term)::FLOAT AS score
    FROM bdpm_equivalence b
    WHERE
        -- Pre-filtre Soundex (elimine 95% des candidats)
        soundex(split_part(b.denomination, ' ', 1)) = soundex(split_part(search_term, ' ', 1))
        -- Filtre trigram
        AND b.denomination % search_term
    ORDER BY similarity(b.denomination, search_term) DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
```

### 3.3 Vue materialisee pour stats matching

```sql
-- Vue materialisee pour dashboard (rafraichie periodiquement)
CREATE MATERIALIZED VIEW mv_matching_stats AS
SELECT
    match_type,
    COUNT(*) as total,
    AVG(match_score) as score_moyen,
    MIN(matched_at) as premier_match,
    MAX(matched_at) as dernier_match
FROM product_matches
GROUP BY match_type;

-- Rafraichir sans bloquer
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_matching_stats;
```

### 3.4 Vue materialisee pour clusters d'equivalences

Cette vue pre-calcule tous les generiques equivalents par groupe BDPM.
Resultat instantane au lieu de recalculer a chaque requete.

**OPTIMISATION** : Utilise la colonne `labo_extracted` (ajoutee en 1.1) au lieu d'une regex fragile sur le premier mot de denomination.

```sql
-- Vue materialisee des clusters d'equivalences par groupe generique
CREATE MATERIALIZED VIEW mv_clusters_equivalences AS
SELECT
    groupe_generique_id,
    -- Princeps du groupe (CIP + nom)
    MAX(CASE WHEN type_generique = 0 THEN cip13 END) as princeps_cip13,
    MAX(CASE WHEN type_generique = 0 THEN denomination END) as princeps_ref,
    -- Tous les noms du groupe concatenes
    string_agg(DISTINCT denomination, ' | ' ORDER BY denomination) as equivalences,
    -- Tous les CIP du groupe
    string_agg(DISTINCT cip13, ', ' ORDER BY cip13) as cips,
    -- Nombre de laboratoires differents (utilise labo_extracted, fiable)
    count(DISTINCT labo_extracted) FILTER (WHERE labo_extracted IS NOT NULL) as nb_labos,
    -- Liste des labos du groupe
    string_agg(DISTINCT labo_extracted, ', ' ORDER BY labo_extracted)
        FILTER (WHERE labo_extracted IS NOT NULL) as labos_liste,
    -- Prix PFHT (tous identiques dans un groupe, on prend le max non-null)
    MAX(pfht) as pfht_groupe,
    -- Nombre total de references dans le groupe
    count(*) as nb_references,
    -- Date derniere MAJ du groupe
    MAX(created_at) as derniere_maj
FROM bdpm_equivalences
WHERE groupe_generique_id IS NOT NULL
GROUP BY groupe_generique_id;

-- Index pour recherche rapide par groupe
CREATE UNIQUE INDEX idx_mv_clusters_groupe ON mv_clusters_equivalences(groupe_generique_id);

-- Rafraichir apres chaque import BDPM
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_clusters_equivalences;
```

**Exemple de resultat :**
```
groupe_id | equivalences                                           | cips                  | nb_labos | pfht   | nb_refs
----------|--------------------------------------------------------|-----------------------|----------|--------|--------
1234      | AMLODIPINE ARROW 5MG | AMLODIPINE BIOGARAN 5MG | ...  | 340093001, 340093002  | 8        | 2.50   | 12
5678      | DOLIPRANE 1000MG | PARACETAMOL MYLAN 1G | ...          | 340093003, 340093004  | 12       | 1.80   | 15
```

**Cas d'utilisation :**

1. **Page BDPM - Affichage equivalences** :
   ```sql
   -- Instantane (<5ms) au lieu de 500ms
   SELECT * FROM mv_clusters_equivalences WHERE groupe_generique_id = 1234;
   ```

2. **Dropdown equivalences dans Simulation** :
   ```sql
   -- Liste deroulante des generiques equivalents
   SELECT equivalences, pfht_groupe
   FROM mv_clusters_equivalences
   WHERE groupe_generique_id = (
       SELECT groupe_generique_id FROM bdpm_equivalence WHERE cip13 = '3400930000001'
   );
   ```

3. **Stats dashboard** :
   ```sql
   -- "8 labos proposent ce generique"
   SELECT nb_labos, nb_references FROM mv_clusters_equivalences WHERE groupe_generique_id = 1234;
   ```

4. **Validation fuzzy - Voir membres du groupe** :
   ```sql
   -- Afficher tous les membres quand on valide un matching fuzzy
   SELECT unnest(string_to_array(cips, ', ')) as cip, equivalences
   FROM mv_clusters_equivalences
   WHERE groupe_generique_id = :proposed_groupe_id;
   ```

**Rafraichissement :**
- Automatique apres import BDPM (dans le endpoint /api/repertoire/sync-bdpm)
- Manuel via bouton admin si besoin

---

## 4. CODE PYTHON - BATCH MATCHING

### 4.1 Preprocessing pharma avant matching

**OPTIMISATION** : Normaliser les noms pharmaceutiques AVANT le matching fuzzy ameliore significativement la precision.
Cette fonction utilise les patterns deja definis dans `intelligent_matching.py`.

```python
import re
from typing import Set

# Labos a supprimer du texte pour matching (deja dans intelligent_matching.py)
LABOS_CONNUS: Set[str] = {
    'viatris', 'zentiva', 'biogaran', 'sandoz', 'teva', 'mylan', 'arrow',
    'eg', 'cristers', 'accord', 'ranbaxy', 'zydus', 'sun', 'almus', 'bgr',
    'ratiopharm', 'actavis', 'winthrop', 'pfizer', 'sanofi', 'bayer',
}

# Formes a normaliser (deja dans intelligent_matching.py)
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

    Args:
        text: Nom du medicament brut

    Returns:
        Nom normalise pour matching
    """
    if not text:
        return ""

    result = text.upper()

    # 1. Supprimer les noms de labos
    for labo in LABOS_CONNUS:
        result = re.sub(rf'\b{labo.upper()}\b', '', result)

    # 2. Normaliser les formes (CPR → COMPRIME)
    for abbr, full in FORMES_MAPPING.items():
        result = re.sub(rf'\b{abbr.upper()}\b', full.upper(), result)

    # 3. Normaliser dosages (40 mg → 40MG, supprimer espaces)
    result = re.sub(r'(\d+)\s*(MG|G|ML|MCG|UI)', r'\1\2', result)

    # 4. Supprimer conditionnement (B/30, BTE 30, etc.)
    result = re.sub(r'\bB/?(\d+)\b', '', result)
    result = re.sub(r'\b(BTE|BOITE|PLQ)\s*\d+\b', '', result)

    # 5. Nettoyer espaces multiples
    result = re.sub(r'\s+', ' ', result).strip()

    return result
```

### 4.2 Matching matriciel avec RapidFuzz

```python
from rapidfuzz import process, fuzz
import numpy as np
from typing import List, Dict

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
    # OPTIMISATION : Preprocessing pharma avant matching
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

### 4.3 Service de matching incremental

```python
class MatchingService:
    """
    Service de matching avec cache.
    Ne recalcule que les nouveaux CIP.
    """

    def __init__(self, db_session):
        self.db = db_session
        self._cache = {}  # CIP -> match result
        self._load_cache()

    def _load_cache(self):
        """Charger le cache depuis product_matches"""
        matches = self.db.query(ProductMatch).all()
        self._cache = {m.source_cip13: m for m in matches}

    def get_or_compute_match(self, cip13: str, designation: str) -> Dict:
        """
        Retourne le match cache ou le calcule si nouveau.
        """
        # Cache hit = instantane
        if cip13 in self._cache:
            return self._cache[cip13].to_dict()

        # Cache miss = calculer et stocker
        match = self._compute_single_match(designation)
        self._store_match(cip13, designation, match)
        return match

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
                cached.append(self._cache[cip])
            else:
                to_compute.append(v)

        # Batch compute seulement les nouveaux
        if to_compute:
            new_matches = batch_match_products(to_compute, self._get_bdpm())
            for match in new_matches:
                self._store_match(match['source_cip13'],
                                  match['source_designation'],
                                  match)
                cached.append(match)

        return {
            'total': len(ventes),
            'from_cache': len(ventes) - len(to_compute),
            'computed': len(to_compute),
            'results': cached
        }
```

---

## 5. FRONTEND - INTERFACES PROPOSEES

### 5.1 Sous-menu BDPM

**Header de page :**
```
+------------------------------------------------------------------+
|  Repertoire BDPM                                                  |
|  Derniere mise a jour : 15/12/2024                               |
|  Nouvelles entrees : 47 (surlignees en vert)                     |
|                                                                   |
|  [Sync ANSM]  [Telecharger CSV]  [Telecharger Excel]            |
+------------------------------------------------------------------+
```

**Tableau avec tri par defaut : nouvelles entrees en premier**
```
+---------------+----------------------------+---------+------------+--------------+
| CIP13         | DENOMINATION               | PFHT    | GROUPE GEN | INTEGRE LE   |
+---------------+----------------------------+---------+------------+--------------+
| 3400930000001 | AMLODIPINE ARROW 5MG [NEW] | 2.50 E  | 1234       | 15/12/2024   | <- Fond vert
| 3400930000002 | METFORMINE EG 850MG [NEW]  | 3.20 E  | 2345       | 15/12/2024   | <- Fond vert
+---------------+----------------------------+---------+------------+--------------+
| 3400930000003 | DOLIPRANE 1000MG           | 1.80 E  | 5678       | 01/06/2024   |
| 3400930000004 | ASPIRINE UPSA 500MG        | 2.10 E  | 6789       | 15/03/2024   |
+---------------+----------------------------+---------+------------+--------------+
```

**Filtres disponibles :**
- Par date d'integration (nouvelles = < 12 mois)
- Par presence PFHT (avec prix / sans prix)
- Par type (generique / princeps)
- Recherche fuzzy sur denomination

### 5.2 Tableau comparatif Simulation

**Vue cote a cote pour verification facile :**
```
+------------------------------------------------------------------+-------+---------+-----------+
| PRODUIT VENDU              | PRODUIT CATALOGUE             | QTE   | PFHT    | MONTANT   |
+------------------------------------------------------------------+-------+---------+-----------+
| AMLODIPINE BIOGARAN 5MG    | AMLODIPINE EG 5MG             |       |         |           |
| CIP: 3400930000001         | CIP: 3400930000002            |  150  | 2.50 E  |  375.00 E |
|                            | Groupe: 1234 | Score: 95%     |       |         |           |
+----------------------------+-------------------------------+-------+---------+-----------+
| DOLIPRANE 1000MG CPR       | PARACETAMOL MYLAN 1G          |       |         |           |
| CIP: 3400935000005         | CIP: 3400935000006            |   85  | 1.80 E  |  153.00 E |
|                            | Groupe: 5678 | Score: 88%     |       |         |           |
+----------------------------+-------------------------------+-------+---------+-----------+
|                            |                         TOTAL |       |         |  528.00 E |
+----------------------------+-------------------------------+-------+---------+-----------+
```

**Colonnes :**
1. PRODUIT VENDU : Designation + CIP de la vente
2. PRODUIT CATALOGUE : Designation + CIP + Groupe + Score du match
3. QTE : Quantite vendue (independante)
4. PFHT : Prix unitaire du produit catalogue
5. MONTANT : QTE x PFHT (calcule)

### 5.3 Rapprochement - Suppression simplifiee

**Option A implementee : Suppression de mes_ventes uniquement**

```
+------------------------------------------------------------------+
| A SUPPRIMER (23 lignes)                          [Supprimer tout] |
+------------------------------------------------------------------+
| [ ] CIP: 340093... | PRODUIT XYZ      | Raison: princeps         |
| [ ] CIP: 340094... | PRODUIT ABC      | Raison: cip_non_trouve   |
| [ ] CIP: 340095... | PRODUIT DEF      | Raison: sans_prix        |
+------------------------------------------------------------------+
| [Supprimer selection]                                             |
+------------------------------------------------------------------+
```

**Action "Supprimer" :**
- Supprime de `mes_ventes` uniquement
- Ne touche PAS a `bdpm_equivalence`
- Log de l'action pour audit

---

## 6. GAINS DE PERFORMANCE

| Metrique              | Avant (actuel)     | Apres (optimise)   |
|-----------------------|--------------------|--------------------|
| Matching 1000 ventes  | 5-10 secondes      | < 100ms            |
| Rapprochement complet | Recalcul total     | Simple JOIN        |
| Nouvelles ventes      | Fuzzy sur tout     | Lookup + incremental |
| Memoire serveur       | Pic a chaque requete | Stable (cache DB) |
| Stockage              | 0 (pas de cache)   | ~10MB / 100k produits |

---

## 7. MIGRATION

### Phase 1 : Schema (1 jour)
1. Creer les nouvelles tables
2. Ajouter colonne `integrated_at` a `bdpm_equivalence`
3. Creer les index

### Phase 2 : Batch initial (1 jour)
1. Peupler `canonical_products` depuis BDPM existant
2. Lancer batch matching sur toutes les ventes existantes
3. Peupler `product_matches`

### Phase 3 : Backend (2-3 jours)
1. Creer `MatchingService` avec cache
2. Modifier endpoints pour utiliser le cache
3. Ajouter endpoint refresh BDPM

### Phase 4 : Frontend (2-3 jours)
1. Creer page sous-menu BDPM
2. Modifier tableau Simulation (vue cote a cote)
3. Simplifier Rapprochement (suppression mes_ventes)

---

## 8. SOURCES ET REFERENCES

- [PostgreSQL pg_trgm Documentation](https://www.postgresql.org/docs/current/pgtrgm.html)
- [PostgreSQL fuzzystrmatch](https://www.postgresql.org/docs/current/fuzzystrmatch.html)
- [RapidFuzz - Batch Processing](https://github.com/rapidfuzz/rapidfuzz)
- [pg_similarity Extension](https://github.com/eulerto/pg_similarity)
- [Fuzzy Search Best Practices](https://dennenboom.be/blog/the-hidden-superpowers-of-postgresql-fuzzy-search)
- [Crunchy Data - Fuzzy Name Matching](https://www.crunchydata.com/blog/fuzzy-name-matching-in-postgresql)

---

## 9. SYSTEME DE VALIDATION OBLIGATOIRE

### 9.1 Principe fondamental

**Aucun matching fuzzy ou prix recupere automatiquement n'est utilisable sans validation humaine.**

- Blocage de TOUTES les operations (simulation, rapprochement, comparaison) si validations en attente
- Notification persistante tant que des elements attendent validation
- Cases cochees par defaut avec possibilite de decocher

### 9.2 Tables de validation

**OPTIMISATION** : Ajout du champ `auto_validated` et de seuils d'auto-validation par type de match pour reduire la charge de validation manuelle tout en gardant le controle.

```sql
-- Validations en attente
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
    auto_validated BOOLEAN DEFAULT FALSE,  -- True si valide automatiquement (score > seuil)
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP
);

CREATE INDEX idx_pending_status ON pending_validations(status);
CREATE INDEX idx_pending_type ON pending_validations(validation_type);
CREATE INDEX idx_pending_created ON pending_validations(created_at);
CREATE INDEX idx_pending_auto ON pending_validations(auto_validated);
```

**Seuils d'auto-validation par type de match** :

```python
# Configuration des seuils d'auto-validation
AUTO_VALIDATION_THRESHOLDS = {
    # Fuzzy match : seuil eleve car moins fiable
    'fuzzy_match': {
        'score_min': 95.0,        # Score RapidFuzz minimum
        'same_groupe': True,      # Doit etre dans le meme groupe_generique
        'same_dosage': True,      # Doit avoir le meme dosage (extrait)
    },
    # Prix recupere du groupe : toujours auto-valide si meme groupe
    'prix_groupe': {
        'auto_validate': True,    # Toujours auto-valide (meme groupe = meme prix)
    },
    # Nouveau produit BDPM : jamais auto-valide
    'nouveau_produit': {
        'auto_validate': False,   # Toujours validation manuelle requise
    },
    # Match exact CIP : toujours auto-valide
    'cip_exact': {
        'auto_validate': True,    # CIP identique = 100% fiable
    },
    # Match groupe_generique_id : auto-valide si meme groupe
    'groupe_generique': {
        'auto_validate': True,    # Meme groupe = equivalents certifies ANSM
    },
}

def should_auto_validate(match_type: str, score: float, context: dict) -> bool:
    """
    Determine si un match doit etre auto-valide selon les seuils.

    Args:
        match_type: Type de match ('fuzzy_match', 'prix_groupe', etc.)
        score: Score du match (0-100)
        context: Contexte additionnel (groupe_id source/cible, dosage, etc.)

    Returns:
        True si le match peut etre auto-valide
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

**Workflow avec auto-validation** :

```
Match detecte
    |
    v
should_auto_validate() ?
    |
    +-- OUI --> INSERT pending_validations (status='auto_validated', auto_validated=True)
    |           |
    |           v
    |           Log dans audit_logs (action='auto_validation')
    |           |
    |           v
    |           Utilisable immediatement (pas de blocage)
    |
    +-- NON --> INSERT pending_validations (status='pending', auto_validated=False)
                |
                v
                Blocage jusqu'a validation manuelle
```

**Avantages** :
- Reduit drastiquement le nombre de validations manuelles
- Les cas evidents (CIP exact, meme groupe) passent automatiquement
- Les cas douteux (fuzzy < 95%) restent bloques
- Tracabilite complete via `auto_validated` flag

```sql
-- Blacklist BDPM (produits supprimes definitivement)
CREATE TABLE bdpm_blacklist (
    id SERIAL PRIMARY KEY,
    cip13 VARCHAR(13) UNIQUE NOT NULL,
    denomination TEXT,
    raison_suppression VARCHAR(50),  -- 'princeps', 'sans_prix', 'manuel', 'doublon'
    supprime_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_blacklist_cip ON bdpm_blacklist(cip13);
```

### 9.3 Middleware de blocage (Backend)

```python
# Middleware qui bloque si validations en attente
BLOCKED_PATHS = [
    "/api/simulation",
    "/api/rapprochement",
    "/api/scenarios",
    "/api/comparaison"
]

@app.middleware("http")
async def check_pending_validations(request, call_next):
    if any(request.url.path.startswith(p) for p in BLOCKED_PATHS):
        pending_count = db.query(PendingValidation).filter(
            PendingValidation.status == 'pending'
        ).count()

        if pending_count > 0:
            return JSONResponse(
                status_code=423,  # Locked
                content={
                    "error": "validations_pending",
                    "count": pending_count,
                    "message": f"{pending_count} validations en attente",
                    "redirect": "/validations"
                }
            )

    return await call_next(request)
```

### 9.4 Workflow Import BDPM avec blacklist

```
Nouveau CIP dans fichier ANSM
    |
    v
CIP dans bdpm_blacklist ?
    |
    OUI --> IGNORER (ne pas reimporter)
    |
    NON --> Ajouter a pending_validations (type: 'nouveau_produit')
            |
            v
        Produit sans PFHT ?
            |
            OUI --> Recuperer prix du groupe
                    Ajouter a pending_validations (type: 'prix_groupe')
```

### 9.5 Interface Frontend - Page /validations

**Header avec onglets cliquables :**
```
+------------------------------------------------------------------+
| VALIDATIONS EN ATTENTE                                           |
+------------------------------------------------------------------+
| [x] Ne pas reintegrer les references supprimees lors des MAJ BDPM|  <- Coche par defaut
+------------------------------------------------------------------+
| [Fuzzy: 12]  [Prix Auto: 3]  [Nouveaux: 5]  |  TOTAL: 20        |
|  ^^^^^^^^      ^^^^^^^^^^      ^^^^^^^^^                         |
|  CLIQUABLE     CLIQUABLE       CLIQUABLE                        |
|  (actif=bleu)  (inactif=gris)  (inactif=gris)                   |
+------------------------------------------------------------------+
```

**Comportement des onglets :**
- Clic sur [Fuzzy: 12] = Affiche uniquement les matchings fuzzy a valider
- Clic sur [Prix Auto: 3] = Affiche uniquement les prix recuperes du groupe
- Clic sur [Nouveaux: 5] = Affiche uniquement les nouveaux produits BDPM
- Onglet actif = fond bleu, texte blanc
- Onglets inactifs = fond gris clair, texte noir
- Badge avec compteur sur chaque onglet

**Tableau FUZZY (quand onglet Fuzzy actif) :**
```
+------------------------------------------------------------------+
| MATCHINGS FUZZY (12)                        [Tout cocher/decocher]|
+------------------------------------------------------------------+
| SEL | PRODUIT VENDU           | PROPOSITION            | SCORE   |
+-----+-------------------------+------------------------+---------+
| [x] | AMLODIPINE BIOGARAN 5MG | AMLODIPINE EG 5MG     | 95%     |
| [x] | METFORMINE SANDOZ 850MG | METFORMINE MYLAN 850MG| 88%     |
| [x] | LOSARTAN ARROW 50MG     | LOSARTAN EG 50MG      | 92%     |
| [ ] | PRODUIT DOUTEUX XYZ     | AUTRE PRODUIT ABC     | 71%     |  <- Decoche manuellement
+-----+-------------------------+------------------------+---------+
| [VALIDER 3 SELECTIONNES]        [REJETER 1 NON SELECTIONNE]     |
+------------------------------------------------------------------+
```

**Tableau PRIX AUTO (quand onglet Prix Auto actif) :**
```
+------------------------------------------------------------------+
| PRIX RECUPERES DU GROUPE (3)                [Tout cocher/decocher]|
+------------------------------------------------------------------+
| SEL | PRODUIT SANS PRIX       | PRIX PROPOSE  | SOURCE          |
+-----+-------------------------+---------------+-----------------+
| [x] | AMLODIPINE ARROW 5MG    | 2.50 EUR      | Groupe 1234     |
|     | CIP: 3400930000005      | (de EG 5MG)   |                 |
+-----+-------------------------+---------------+-----------------+
| [x] | DOLIPRANE 1000MG SACHET | 1.80 EUR      | Groupe 5678     |
|     | CIP: 3400930000006      | (de EFFERALGAN)|                |
+-----+-------------------------+---------------+-----------------+
| [VALIDER 2 SELECTIONNES]        [REJETER 0 NON SELECTIONNE]     |
+------------------------------------------------------------------+
```

**Tableau NOUVEAUX (quand onglet Nouveaux actif) :**
```
+------------------------------------------------------------------+
| NOUVEAUX PRODUITS BDPM (5)                  [Tout cocher/decocher]|
+------------------------------------------------------------------+
| SEL | CIP           | DENOMINATION              | PFHT   | GROUPE |
+-----+---------------+---------------------------+--------+--------+
| [x] | 3400930000007 | LOSARTAN BIOGARAN 50MG   | 3.20 E | 3456   |
| [x] | 3400930000008 | OMEPRAZOLE EG 20MG       | 2.80 E | 4567   |
| [x] | 3400930000009 | METFORMINE ARROW 1000MG  | 2.10 E | 2345   |
+-----+---------------+---------------------------+--------+--------+
| [VALIDER 3 SELECTIONNES]        [REJETER 0 NON SELECTIONNE]     |
+------------------------------------------------------------------+
```

### 9.6 Indicateur global (Header toutes pages)

```
+------------------------------------------------------------------+
|  PHARMA-REMISES                              [Menu] [Profil]     |
+------------------------------------------------------------------+
| [!] 12 validations en attente - Cliquez ici pour valider         |  <- Badge rouge
+------------------------------------------------------------------+
```

**Comportement :**
- Visible sur TOUTES les pages
- Cliquable : redirige vers /validations
- Clignotant si > 7 jours d'attente
- Couleur : Rouge vif si > 7 jours, Orange sinon

### 9.7 Modal de blocage

Quand l'utilisateur tente une action bloquee :

```
+------------------------------------------------------------------+
|                    [X] ACTION BLOQUEE                             |
+------------------------------------------------------------------+
|                                                                   |
|  Vous ne pouvez pas lancer de simulation tant que des            |
|  validations sont en attente.                                     |
|                                                                   |
|  - 12 matchings fuzzy a valider                                  |
|  - 3 prix recuperes automatiquement a verifier                   |
|                                                                   |
|  [Aller aux validations]              [Annuler]                  |
|                                                                   |
+------------------------------------------------------------------+
```

### 9.8 Actions de validation

**Valider [x] :**
- Deplace de pending_validations vers product_matches
- Status = 'validated'
- validated_at = NOW()

**Rejeter [ ] :**
- Status = 'rejected'
- Option : Ajouter a bdpm_blacklist si suppression definitive

**Supprimer definitivement :**
- Ajoute le CIP a bdpm_blacklist
- Ne sera JAMAIS reimporte lors des futures MAJ BDPM

### 9.9 Alerte renforcee (> 7 jours)

```
+------------------------------------------------------------------+
| [!!!] URGENT : 5 validations attendent depuis plus de 7 jours !  |  <- Rouge clignotant
+------------------------------------------------------------------+
```

- Badge rouge clignotant dans le header
- Texte en gras
- Impossible a ignorer

---

## 10. CORRECTIONS IMPORT BDPM - LABOS ET PRINCEPS

### 10.1 Probleme identifie : Labos incomplets

**Etat actuel du code (`bdpm_import.py`) :**
```python
LAB_PATTERNS = {
    'BIOGARAN': ['BIOGARAN', 'BGR'],
    'SANDOZ': ['SANDOZ'],
    'ARROW': ['ARROW'],
    'ZENTIVA': ['ZENTIVA'],
    'VIATRIS': ['VIATRIS', 'MYLAN'],
}
```

**Problemes :**
1. Seulement 5 labos cibles (manque EG, TEVA, CRISTERS, ZYDUS, ACCORD, etc.)
2. Abreviations incompletes (ex: VIAT pour VIATRIS ?)
3. Pas de fallback sur le titulaire AMM BDPM

### 10.2 Action prealable OBLIGATOIRE

**⚠️ AVANT de coder les nouveaux patterns, il faut parcourir la BDPM pour :**

1. **Lister toutes les variantes de noms pour les labos manquants :**
   - EG : Quelles abreviations existent ? (EG, E.G. ?)
   - TEVA : Variantes ? (TEVA, TEVA SANTE ?)
   - CRISTERS : Variantes ?
   - ZYDUS : Variantes ?
   - ACCORD : Variantes ?

2. **Script d'analyse a executer :**
```python
# Analyser CIS_bdpm.txt pour trouver les patterns
import re
from collections import Counter

patterns_trouves = Counter()
with open('CIS_bdpm.txt', 'r', encoding='latin-1') as f:
    for line in f:
        parts = line.split('\t')
        if len(parts) > 1:
            denom = parts[1].upper()
            # Extraire le premier mot (souvent le labo)
            premier_mot = denom.split()[0] if denom.split() else ''
            # Chercher les patterns connus
            for pattern in ['EG', 'TEVA', 'CRISTERS', 'ZYDUS', 'ACCORD']:
                if pattern in denom:
                    patterns_trouves[f"{pattern} -> {premier_mot}"] += 1

# Afficher les resultats
for pattern, count in patterns_trouves.most_common(50):
    print(f"{count:5d} | {pattern}")
```

3. **Resultat attendu :**
```
  847 | EG -> PARACETAMOL
  523 | EG -> METFORMINE
  412 | TEVA -> OMEPRAZOLE
  ...
```

### 10.3 Nouveaux patterns a implementer (apres analyse)

```python
# A COMPLETER apres analyse BDPM
LAB_PATTERNS = {
    # Labos actuels
    'BIOGARAN': ['BIOGARAN', 'BGR'],
    'SANDOZ': ['SANDOZ'],
    'ARROW': ['ARROW'],
    'ZENTIVA': ['ZENTIVA'],
    'VIATRIS': ['VIATRIS', 'MYLAN', 'VIAT'],  # A confirmer VIAT

    # Labos a ajouter (patterns a decouvrir via analyse)
    'EG': ['EG'],           # PAS 'STADA' - EG seulement
    'TEVA': ['TEVA'],       # A completer apres analyse
    'CRISTERS': ['CRISTERS'],  # A completer apres analyse
    'ZYDUS': ['ZYDUS'],     # A completer apres analyse
    'ACCORD': ['ACCORD'],   # A completer apres analyse
}
```

### 10.4 Probleme identifie : Princeps non importes

**Etat actuel du code (`bdpm_import.py` ligne 351) :**
```python
# Les princeps sont EXCLUS de l'import !
if gener_data['type'] == 'princeps':
    continue  # <- PROBLEME : on perd l'info du princeps referent
```

**Consequence :**
- La colonne `princeps_denomination` dans `bdpm_equivalences` n'est jamais remplie
- Impossible d'afficher le princeps de reference pour chaque groupe

### 10.5 Solution : Importer le princeps referent par groupe

**Modification du workflow d'import :**

```python
def get_princeps_by_groupe(cis_bdpm: Dict, cis_gener: Dict) -> Dict[int, str]:
    """
    Pour chaque groupe generique, trouve le princeps referent.

    Returns: {groupe_id: princeps_denomination}
    """
    princeps_map = {}

    for cis, gener_data in cis_gener.items():
        if gener_data['type'] == 'princeps':
            groupe_id = gener_data['groupe_id']
            if cis in cis_bdpm and groupe_id not in princeps_map:
                princeps_map[groupe_id] = cis_bdpm[cis]['denomination']

    return princeps_map

# Dans build_products_list() :
princeps_map = get_princeps_by_groupe(cis_bdpm, cis_gener)

for p in products:
    p.princeps_denomination = princeps_map.get(p.groupe_id)
```

### 10.6 Affichage Frontend du princeps

**Modification de `RepertoireGenerique.tsx` :**

```tsx
// Ligne du princeps en GRAS
<TableRow key={item.cip13}>
  <TableCell className="font-mono text-sm">{item.cip13}</TableCell>
  <TableCell className={item.type_generique === 0 ? "font-bold" : ""}>
    {item.type_generique === 0 && <span className="mr-1">★</span>}
    {item.denomination || '-'}
  </TableCell>
  ...
</TableRow>
```

**Ou affichage du princeps referent dans chaque ligne generique :**

```tsx
<TableCell>
  <div>{item.denomination}</div>
  {item.princeps_denomination && (
    <div className="text-xs text-blue-600 font-semibold">
      Ref: {item.princeps_denomination}
    </div>
  )}
</TableCell>
```

### 10.7 Vue materialisee avec princeps (reference section 3.4)

**Note** : La vue `mv_clusters_equivalences` est definie en detail dans la section 3.4.
Elle inclut deja `princeps_cip13` et `princeps_ref` pour chaque groupe.

**Resume des colonnes princeps disponibles** :
```sql
-- Extrait de mv_clusters_equivalences (voir section 3.4 pour definition complete)
SELECT
    groupe_generique_id,
    princeps_cip13,    -- CIP13 du princeps referent
    princeps_ref,      -- Denomination du princeps referent
    equivalences,      -- Liste des generiques
    ...
FROM mv_clusters_equivalences;
```

**Utilisation dans le drawer (section 12)** :
- Le `princeps_cip13` permet d'afficher le CIP du princeps dans le drawer
- Utile pour copier le CIP du princeps de reference

### 10.8 Checklist implementation

- [ ] **Etape 1** : Executer script analyse BDPM pour decouvrir patterns EG, TEVA, CRISTERS, ZYDUS
- [ ] **Etape 2** : Completer `LAB_PATTERNS` avec les patterns decouverts
- [ ] **Etape 3** : Modifier import pour extraire `princeps_denomination` par groupe
- [ ] **Etape 4** : Ajouter migration pour remplir `princeps_denomination` existants
- [ ] **Etape 5** : Modifier frontend pour afficher princeps en gras
- [ ] **Etape 6** : Mettre a jour vue materialisee avec colonne `princeps_ref`

---

## 11. HISTORIQUE DES PRIX BDPM

### 11.1 Probleme

Actuellement, quand le PFHT change lors d'un import BDPM, l'ancien prix est **ecrase et perdu**.

```python
# Code actuel - pas d'historique
existing.pfht = new_pfht  # L'ancien prix disparait
```

### 11.2 Solution : Table d'historique

```sql
-- Historique des changements de prix BDPM
CREATE TABLE bdpm_prix_historique (
    id SERIAL PRIMARY KEY,
    cip13 VARCHAR(13) NOT NULL,
    pfht_ancien DECIMAL(10,4),
    pfht_nouveau DECIMAL(10,4),
    variation_pct DECIMAL(5,2),      -- % de variation (+ ou -)
    date_changement TIMESTAMP DEFAULT NOW(),
    source_import VARCHAR(50)        -- 'bdpm_2024-12', 'bdpm_2025-01', etc.
);

-- Index pour requetes rapides
CREATE INDEX idx_prix_hist_cip ON bdpm_prix_historique(cip13);
CREATE INDEX idx_prix_hist_date ON bdpm_prix_historique(date_changement DESC);
```

### 11.3 Modification de l'import BDPM

```python
def update_pfht_with_history(db: Session, cip13: str, new_pfht: Decimal, source: str):
    """
    Met a jour le PFHT en conservant l'historique si changement.
    """
    existing = db.query(BdpmEquivalence).filter_by(cip13=cip13).first()

    if not existing:
        return

    # Pas de changement = rien a faire
    if existing.pfht == new_pfht:
        return

    # Calculer la variation
    variation = None
    if existing.pfht and existing.pfht > 0:
        variation = ((new_pfht - existing.pfht) / existing.pfht) * 100

    # Archiver l'ancien prix
    historique = BdpmPrixHistorique(
        cip13=cip13,
        pfht_ancien=existing.pfht,
        pfht_nouveau=new_pfht,
        variation_pct=variation,
        source_import=source
    )
    db.add(historique)

    # Mettre a jour le prix actuel
    existing.pfht = new_pfht
```

### 11.4 Cas d'utilisation

1. **Alerte variations significatives** :
```sql
-- Prix ayant varie de plus de 10% ce mois
SELECT cip13, pfht_ancien, pfht_nouveau, variation_pct
FROM bdpm_prix_historique
WHERE date_changement > NOW() - INTERVAL '30 days'
  AND ABS(variation_pct) > 10
ORDER BY ABS(variation_pct) DESC;
```

2. **Historique d'un produit specifique** :
```sql
-- Evolution du prix d'un CIP
SELECT date_changement, pfht_ancien, pfht_nouveau, variation_pct
FROM bdpm_prix_historique
WHERE cip13 = '3400930000001'
ORDER BY date_changement DESC;
```

3. **Dashboard stats** :
```sql
-- Tendance globale du mois
SELECT
    COUNT(*) as nb_changements,
    AVG(variation_pct) as variation_moyenne,
    COUNT(*) FILTER (WHERE variation_pct > 0) as hausses,
    COUNT(*) FILTER (WHERE variation_pct < 0) as baisses
FROM bdpm_prix_historique
WHERE date_changement > NOW() - INTERVAL '30 days';
```

### 11.5 Frontend - Alerte variations prix significatives

**OPTIMISATION** : Ajouter une alerte visible dans le header de la page BDPM quand des prix ont varie de plus de 10% lors du dernier import.

**Bandeau d'alerte (header page Repertoire BDPM) :**
```tsx
// components/PriceAlertBanner.tsx
import { AlertTriangle, TrendingUp, TrendingDown } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface PriceAlertBannerProps {
  variations: {
    total: number
    hausses: number
    baisses: number
    variation_max: number
  }
}

export function PriceAlertBanner({ variations }: PriceAlertBannerProps) {
  if (variations.total === 0) return null

  return (
    <Alert variant="warning" className="mb-4 border-orange-300 bg-orange-50">
      <AlertTriangle className="h-4 w-4" />
      <AlertDescription className="flex items-center justify-between">
        <span>
          <strong>{variations.total} prix</strong> ont varie de plus de 10% ce mois :
          {variations.hausses > 0 && (
            <span className="ml-2 text-red-600">
              <TrendingUp className="inline h-4 w-4" /> {variations.hausses} hausses
            </span>
          )}
          {variations.baisses > 0 && (
            <span className="ml-2 text-green-600">
              <TrendingDown className="inline h-4 w-4" /> {variations.baisses} baisses
            </span>
          )}
          <span className="ml-2 text-muted-foreground">
            (max: {variations.variation_max > 0 ? '+' : ''}{variations.variation_max.toFixed(1)}%)
          </span>
        </span>
        <Button variant="ghost" size="sm" asChild>
          <a href="/repertoire?filter=price_changed">Voir details</a>
        </Button>
      </AlertDescription>
    </Alert>
  )
}
```

**Endpoint API pour stats variations :**
```python
@router.get("/prix-variations/stats")
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
```

**Icone sur les produits avec historique :**
```tsx
{item.has_price_history && (
  <Tooltip content="Prix a change recemment">
    <TrendingUp className="h-4 w-4 text-orange-500" />
  </Tooltip>
)}
```

**Modal historique au clic :**
```
+------------------------------------------------------------------+
| HISTORIQUE PRIX - AMLODIPINE BIOGARAN 5MG (CIP: 3400930000001)   |
+------------------------------------------------------------------+
| DATE       | ANCIEN  | NOUVEAU | VARIATION | SOURCE              |
+------------+---------+---------+-----------+---------------------+
| 2024-12-15 | 2.30 E  | 2.50 E  | +8.7%     | bdpm_2024-12       |
| 2024-06-01 | 2.20 E  | 2.30 E  | +4.5%     | bdpm_2024-06       |
| 2024-01-10 | 2.50 E  | 2.20 E  | -12.0%    | bdpm_2024-01       |
+------------------------------------------------------------------+
```

### 11.6 Impact technique

| Aspect | Impact |
|--------|--------|
| **Nouvelle table** | 1 table, 2 index |
| **Code import** | +15 lignes (comparaison + insert) |
| **Requetes existantes** | Aucun changement |
| **Performance** | Negligeable (ecriture rare) |
| **Stockage** | ~1 KB par changement de prix |

### 11.7 Checklist implementation

- [ ] **Etape 1** : Creer table `bdpm_prix_historique` + index
- [ ] **Etape 2** : Modifier `bdpm_import.py` pour appeler `update_pfht_with_history()`
- [ ] **Etape 3** : (Optionnel) Ajouter endpoint `/api/prix-historique/{cip13}`
- [ ] **Etape 4** : (Optionnel) Ajouter icone + modal dans le frontend

---

## 12. DRAWER GROUPE GENERIQUE

### 12.1 Concept

Ajouter une **colonne "Groupe" cliquable** dans TOUTES les tables contenant des references medicaments.
Le clic ouvre un **drawer lateral** affichant :
- Le princeps referent
- Tous les equivalents du groupe
- Actions utiles (copier CIP, naviguer)

**Pourquoi un drawer plutot qu'un hover/tooltip ?**

| Aspect | Hover (tooltip) | Drawer (panneau) |
|--------|----------------|------------------|
| Mobile | Inutilisable | Fonctionne |
| Contenu long | Limite, disparait | Scrollable |
| Actions | Impossible | Boutons, liens |
| UX | Frustrant | Controle utilisateur |

### 12.2 Tables concernees

Toutes les tables affichant des references avec `groupe_generique_id` :

- `mes_ventes` - Page Mes Ventes
- `vente_matching` - Page Rapprochement
- `resultats_simulation` - Page Simulation
- `catalogue_produits` - Page Catalogues
- `bdpm_equivalences` - Page Repertoire

### 12.3 Maquette colonne cliquable

```
+--------+------------------------+------------+--------+
| CIP    | DESIGNATION            | GROUPE     | PFHT   |
+--------+------------------------+------------+--------+
| 340093 | AMLODIPINE BIOGARAN 5MG| [1234] 👆  | 2.50 € |
| 340094 | METFORMINE EG 850MG    | [2345] 👆  | 1.80 € |
| 340095 | DOLIPRANE 1000MG       | [5678] 👆  | 1.50 € |
+--------+------------------------+------------+--------+
                                    ^
                                    Clic = ouvre drawer
```

### 12.4 Maquette Drawer

```
+--------------------------------------------------+
|  ✕  GROUPE GENERIQUE #1234                       |
+--------------------------------------------------+
|                                                  |
|  ★ PRINCEPS REFERENT                             |
|  ┌────────────────────────────────────────────┐  |
|  │ AMLOR 5MG GELULE                           │  |
|  │ CIP: 3400930000001  |  PFHT: 2.50 €        │  |
|  │ Laboratoire: PFIZER                        │  |
|  └────────────────────────────────────────────┘  |
|                                                  |
|  📋 EQUIVALENTS GENERIQUES (12 references)       |
|  ┌────────────────────────────────────────────┐  |
|  │ ✓ AMLODIPINE BIOGARAN 5MG  | 2.50 € | BGR  │  |
|  │   AMLODIPINE EG 5MG        | 2.50 € | EG   │  |
|  │   AMLODIPINE SANDOZ 5MG    | 2.50 € | SDZ  │  |
|  │   AMLODIPINE TEVA 5MG      | 2.50 € | TVA  │  |
|  │   AMLODIPINE ARROW 5MG     | 2.50 € | ARW  │  |
|  │   AMLODIPINE ZENTIVA 5MG   | 2.50 € | ZTV  │  |
|  │   AMLODIPINE VIATRIS 5MG   | 2.50 € | VIA  │  |
|  │   AMLODIPINE CRISTERS 5MG  | 2.50 € | CRS  │  |
|  │   AMLODIPINE ZYDUS 5MG     | 2.50 € | ZYD  │  |
|  │   AMLODIPINE ACCORD 5MG    | 2.50 € | ACC  │  |
|  │   ...                                      │  |
|  └────────────────────────────────────────────┘  |
|                                                  |
|  [Copier tous les CIP]  [Voir dans Repertoire]   |
|                                                  |
+--------------------------------------------------+

✓ = reference actuellement selectionnee/affichee dans le tableau
```

### 12.5 Architecture technique

**Pas de redondance** - les tables stockent uniquement `groupe_generique_id` (un entier).
Les details sont charges a la demande depuis la vue materialisee.

```
Tables existantes              Vue materialisee            Composant
┌────────────────────┐        ┌──────────────────────┐    ┌──────────────┐
│ mes_ventes         │        │ mv_clusters_equiv    │    │ GroupeDrawer │
│ └─ groupe_gen_id ──┼───────→│ - groupe_gen_id      │───→│              │
├────────────────────┤        │ - princeps_ref       │    │ Props:       │
│ vente_matching     │        │ - equivalences       │    │ - groupeId   │
│ └─ groupe_gen_id ──┼───────→│ - cips               │    │ - currentCip │
├────────────────────┤        │ - nb_labos           │    └──────────────┘
│ resultats_simul    │        │ - pfht_groupe        │
│ └─ groupe_gen_id ──┼───────→└──────────────────────┘
├────────────────────┤
│ catalogue_produits │
│ └─ groupe_gen_id ──┼───────→ (meme vue)
└────────────────────┘
```

### 12.6 Endpoint API

**OPTIMISATION** : Inclure `princeps_cip13` dans la reponse pour permettre l'affichage et la copie du CIP du princeps.

```python
@router.get("/groupe/{groupe_id}/details")
async def get_groupe_details(groupe_id: int, db: Session = Depends(get_db)):
    """
    Retourne les details d'un groupe generique pour le drawer.
    Utilise la vue materialisee pour performance instantanee.
    """
    # Query sur vue materialisee (inclut princeps_cip13)
    cluster = db.execute(
        text("""
            SELECT
                groupe_generique_id,
                princeps_cip13,    -- CIP du princeps (nouveau)
                princeps_ref,
                equivalences,
                cips,
                nb_labos,
                pfht_groupe,
                nb_references
            FROM mv_clusters_equivalences
            WHERE groupe_generique_id = :groupe_id
        """),
        {"groupe_id": groupe_id}
    ).fetchone()

    if not cluster:
        raise HTTPException(404, "Groupe non trouve")

    # Transformer en liste structuree
    equivalents = []
    for cip in cluster.cips.split(', '):
        equiv = db.query(BdpmEquivalence).filter_by(cip13=cip).first()
        if equiv:
            equivalents.append({
                "cip13": equiv.cip13,
                "denomination": equiv.denomination,
                "pfht": float(equiv.pfht) if equiv.pfht else None,
                "type_generique": equiv.type_generique,
                "labo": extract_labo_from_denomination(equiv.denomination)
            })

    return {
        "groupe_id": cluster.groupe_generique_id,
        "princeps": {
            "cip13": cluster.princeps_cip13,     # CIP du princeps (nouveau)
            "denomination": cluster.princeps_ref,
            "pfht": float(cluster.pfht_groupe) if cluster.pfht_groupe else None
        },
        "equivalents": equivalents,
        "stats": {
            "nb_labos": cluster.nb_labos,
            "nb_references": cluster.nb_references
        }
    }
```

### 12.7 Composant React

```tsx
// components/GroupeDrawer.tsx
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Star, Copy, ExternalLink } from "lucide-react"

interface GroupeDrawerProps {
  groupeId: number | null
  currentCip?: string  // CIP actuellement affiche dans le tableau
  open: boolean
  onClose: () => void
}

export function GroupeDrawer({ groupeId, currentCip, open, onClose }: GroupeDrawerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['groupe-details', groupeId],
    queryFn: () => api.get(`/groupe/${groupeId}/details`),
    enabled: !!groupeId && open
  })

  const copyAllCips = () => {
    const cips = data.equivalents.map(e => e.cip13).join('\n')
    navigator.clipboard.writeText(cips)
    toast.success('CIP copies dans le presse-papier')
  }

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-[400px] sm:w-[540px]">
        <SheetHeader>
          <SheetTitle>Groupe Generique #{groupeId}</SheetTitle>
        </SheetHeader>

        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {/* Princeps avec CIP */}
            <div>
              <h3 className="flex items-center gap-2 font-semibold mb-2">
                <Star className="h-4 w-4 text-yellow-500" />
                Princeps Referent
              </h3>
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="font-bold">{data.princeps.denomination}</p>
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>CIP: {data.princeps.cip13}</span>
                  <span>PFHT: {data.princeps.pfht?.toFixed(2)} €</span>
                </div>
                {/* Bouton copier CIP princeps */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 h-7 text-xs"
                  onClick={() => {
                    navigator.clipboard.writeText(data.princeps.cip13)
                    toast.success('CIP princeps copie')
                  }}
                >
                  <Copy className="h-3 w-3 mr-1" />
                  Copier CIP princeps
                </Button>
              </div>
            </div>

            {/* Equivalents */}
            <div>
              <h3 className="font-semibold mb-2">
                Equivalents ({data.stats.nb_references} references)
              </h3>
              <div className="max-h-[400px] overflow-y-auto space-y-1">
                {data.equivalents.map((equiv) => (
                  <div
                    key={equiv.cip13}
                    className={`p-2 rounded flex justify-between items-center ${
                      equiv.cip13 === currentCip
                        ? 'bg-green-100 border border-green-300'
                        : 'bg-gray-50'
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">{equiv.denomination}</p>
                      <p className="text-xs text-muted-foreground">
                        CIP: {equiv.cip13}
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge variant="outline">{equiv.labo}</Badge>
                      <p className="text-sm">{equiv.pfht?.toFixed(2)} €</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t">
              <Button variant="outline" onClick={copyAllCips}>
                <Copy className="h-4 w-4 mr-2" />
                Copier tous les CIP
              </Button>
              <Button variant="outline" asChild>
                <a href={`/repertoire?groupe=${groupeId}`}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Voir dans Repertoire
                </a>
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
```

### 12.8 Utilisation dans les pages

```tsx
// Dans n'importe quelle page avec tableau de references
import { GroupeDrawer } from "@/components/GroupeDrawer"

function MesVentes() {
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>CIP</TableHead>
            <TableHead>Designation</TableHead>
            <TableHead>Groupe</TableHead>  {/* Nouvelle colonne */}
            <TableHead>PFHT</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ventes.map((vente) => (
            <TableRow key={vente.id}>
              <TableCell>{vente.code_cip_achete}</TableCell>
              <TableCell>{vente.designation}</TableCell>
              <TableCell>
                {vente.groupe_generique_id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedGroupe(vente.groupe_generique_id)
                      setSelectedCip(vente.code_cip_achete)
                    }}
                  >
                    [{vente.groupe_generique_id}]
                  </Button>
                )}
              </TableCell>
              <TableCell>{vente.pfht}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <GroupeDrawer
        groupeId={selectedGroupe}
        currentCip={selectedCip}
        open={!!selectedGroupe}
        onClose={() => setSelectedGroupe(null)}
      />
    </>
  )
}
```

### 12.9 Checklist implementation

- [ ] **Etape 1** : Creer composant `GroupeDrawer.tsx`
- [ ] **Etape 2** : Creer endpoint `/api/groupe/{id}/details`
- [ ] **Etape 3** : Ajouter colonne "Groupe" dans `MesVentes.tsx`
- [ ] **Etape 4** : Ajouter colonne "Groupe" dans `RapprochementVentes.tsx`
- [ ] **Etape 5** : Ajouter colonne "Groupe" dans `SimulationIntelligente.tsx`
- [ ] **Etape 6** : Ajouter colonne "Groupe" dans `Catalogues.tsx`
- [ ] **Etape 7** : Ajouter colonne "Groupe" dans `RepertoireGenerique.tsx`
- [ ] **Etape 8** : Tester sur mobile (responsive)

---

## 13. LOGS ET AUDIT

### 13.1 Objectif

Tracer toutes les actions critiques pour :
- Audit de securite et conformite
- Debug et analyse d'incidents
- Historique des modifications de donnees
- Suivi des actions utilisateurs

### 13.2 Table audit_logs

```sql
-- Table centrale des logs d'audit
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    -- Identifiant unique de l'evenement
    event_id UUID DEFAULT gen_random_uuid(),

    -- Quand
    created_at TIMESTAMP DEFAULT NOW(),

    -- Qui
    user_id INT,                           -- FK vers users (si authentification)
    user_email VARCHAR(255),               -- Email pour tracabilite
    ip_address INET,                       -- IP client
    user_agent TEXT,                       -- Navigateur/client

    -- Quoi
    action VARCHAR(50) NOT NULL,           -- 'create', 'update', 'delete', 'validate', 'reject', 'import', 'export'
    resource_type VARCHAR(50) NOT NULL,    -- 'matching', 'vente', 'simulation', 'catalogue', 'bdpm'
    resource_id VARCHAR(100),              -- ID de la ressource concernee

    -- Details
    description TEXT,                      -- Description lisible de l'action
    old_values JSONB,                      -- Valeurs avant modification
    new_values JSONB,                      -- Valeurs apres modification
    metadata JSONB,                        -- Donnees supplementaires contextuelles

    -- Resultat
    status VARCHAR(20) DEFAULT 'success',  -- 'success', 'failure', 'partial'
    error_message TEXT                     -- Message d'erreur si echec
);

-- Index pour requetes frequentes
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_user ON audit_logs(user_email);
CREATE INDEX idx_audit_status ON audit_logs(status);

-- Index GIN pour recherche dans JSONB
CREATE INDEX idx_audit_metadata ON audit_logs USING gin(metadata);
```

### 13.3 Actions a logger

| Action | Resource Type | Description |
|--------|---------------|-------------|
| `validate` | `matching` | Validation d'un matching fuzzy |
| `reject` | `matching` | Rejet d'un matching propose |
| `auto_validate` | `matching` | Auto-validation (score > seuil) |
| `import` | `vente` | Import fichier ventes |
| `import` | `bdpm` | Synchronisation BDPM |
| `delete` | `vente` | Suppression de ventes |
| `create` | `simulation` | Creation d'une simulation |
| `export` | `rapport` | Export PDF/Excel |
| `blacklist` | `bdpm` | Ajout a la blacklist |
| `price_update` | `bdpm` | Changement de prix detecte |

### 13.4 Service de logging Python

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Request
from typing import Optional, Dict, Any
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

        Args:
            action: Type d'action (create, update, delete, validate, etc.)
            resource_type: Type de ressource (matching, vente, simulation, etc.)
            resource_id: ID de la ressource concernee
            description: Description lisible de l'action
            old_values: Valeurs avant modification (pour update/delete)
            new_values: Valeurs apres modification (pour create/update)
            metadata: Donnees contextuelles supplementaires
            request: Objet Request FastAPI pour extraire IP/user-agent
            status: Resultat de l'action (success, failure, partial)
            error_message: Message d'erreur si echec
        """
        # Extraire infos de la requete si disponible
        user_email = None
        ip_address = None
        user_agent = None

        if request:
            # Extraire email depuis token JWT si auth implementee
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


# Utilisation dans les endpoints
@router.post("/validations/{id}/validate")
async def validate_matching(
    id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    validation = db.query(PendingValidation).get(id)
    if not validation:
        raise HTTPException(404, "Validation non trouvee")

    # Sauvegarder anciennes valeurs pour audit
    old_values = {
        "status": validation.status,
        "validated_at": str(validation.validated_at) if validation.validated_at else None
    }

    # Effectuer la validation
    validation.status = "validated"
    validation.validated_at = datetime.now()
    db.commit()

    # Logger l'action
    audit = AuditLogger(db)
    audit.log(
        action="validate",
        resource_type="matching",
        resource_id=str(id),
        description=f"Validation du matching {validation.source_designation} -> {validation.proposed_designation}",
        old_values=old_values,
        new_values={"status": "validated", "validated_at": str(validation.validated_at)},
        metadata={
            "match_score": validation.match_score,
            "match_type": validation.validation_type,
            "source_cip": validation.source_cip13,
            "proposed_cip": validation.proposed_cip13
        },
        request=request
    )

    return {"message": "Validation effectuee"}
```

### 13.5 Requetes d'analyse

```sql
-- 1. Actions des 7 derniers jours par type
SELECT
    action,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'success') as success,
    COUNT(*) FILTER (WHERE status = 'failure') as failure
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY action
ORDER BY total DESC;

-- 2. Activite par utilisateur
SELECT
    user_email,
    COUNT(*) as nb_actions,
    array_agg(DISTINCT action) as actions
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '30 days'
  AND user_email IS NOT NULL
GROUP BY user_email
ORDER BY nb_actions DESC;

-- 3. Historique d'une ressource specifique
SELECT
    created_at,
    action,
    description,
    old_values,
    new_values,
    user_email
FROM audit_logs
WHERE resource_type = 'matching'
  AND resource_id = '12345'
ORDER BY created_at DESC;

-- 4. Erreurs recentes
SELECT
    created_at,
    action,
    resource_type,
    error_message,
    metadata
FROM audit_logs
WHERE status = 'failure'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### 13.6 Retention et archivage

```python
# Politique de retention des logs
AUDIT_RETENTION_DAYS = 365  # 1 an

def archive_old_logs(db: Session):
    """
    Archive les logs de plus de 1 an vers une table d'archive.
    Execute mensuellement via cron.
    """
    # Deplacer vers table archive
    db.execute(text("""
        INSERT INTO audit_logs_archive
        SELECT * FROM audit_logs
        WHERE created_at < NOW() - INTERVAL '365 days'
    """))

    # Supprimer de la table principale
    db.execute(text("""
        DELETE FROM audit_logs
        WHERE created_at < NOW() - INTERVAL '365 days'
    """))

    db.commit()
```

### 13.7 Checklist implementation

- [ ] **Etape 1** : Creer table `audit_logs` + index
- [ ] **Etape 2** : Creer classe `AuditLogger` dans `backend/services/`
- [ ] **Etape 3** : Integrer logging dans endpoint validation matching
- [ ] **Etape 4** : Integrer logging dans import ventes
- [ ] **Etape 5** : Integrer logging dans sync BDPM
- [ ] **Etape 6** : Integrer logging dans exports
- [ ] **Etape 7** : (Optionnel) Page admin visualisation logs

---

## 14. TESTS AUTOMATISES PERFORMANCE

### 14.1 Objectif

Valider que les optimisations atteignent les objectifs de performance :
- Matching batch < 100ms pour 1000 ventes
- Lookup cache < 10ms
- Vue materialisee < 5ms

### 14.2 Structure des tests

```python
# tests/performance/test_matching_performance.py
import pytest
import time
from unittest.mock import patch
from app.services.matching_service import MatchingService, batch_match_products


class TestMatchingPerformance:
    """Tests de performance du systeme de matching."""

    @pytest.fixture
    def sample_ventes(self):
        """Genere 1000 ventes de test."""
        return [
            {"cip13": f"340093{i:07d}", "designation": f"PRODUIT TEST {i}"}
            for i in range(1000)
        ]

    @pytest.fixture
    def sample_bdpm(self):
        """Genere 50000 references BDPM de test."""
        return [
            {"cip13": f"340094{i:07d}", "denomination": f"MEDICAMENT BDPM {i}", "pfht": 2.50}
            for i in range(50000)
        ]

    def test_batch_matching_under_100ms(self, sample_ventes, sample_bdpm):
        """
        OBJECTIF : Batch matching de 1000 ventes vs 50000 BDPM < 100ms
        """
        start = time.perf_counter()
        results = batch_match_products(sample_ventes, sample_bdpm, score_threshold=70.0)
        elapsed = (time.perf_counter() - start) * 1000  # en ms

        assert elapsed < 100, f"Batch matching trop lent: {elapsed:.2f}ms (objectif: <100ms)"
        assert len(results) == 1000, f"Nombre de resultats incorrect: {len(results)}"
        print(f"✓ Batch matching 1000 ventes: {elapsed:.2f}ms")

    def test_cache_lookup_under_10ms(self, db_session):
        """
        OBJECTIF : Lookup cache (CIP connu) < 10ms
        """
        service = MatchingService(db_session)

        # Pre-remplir le cache avec des donnees
        service._cache = {
            f"340093{i:07d}": {"matched_cip13": f"340094{i:07d}", "match_score": 95.0}
            for i in range(10000)
        }

        # Mesurer 1000 lookups consecutifs
        start = time.perf_counter()
        for i in range(1000):
            result = service.get_or_compute_match(f"340093{i:07d}", f"PRODUIT {i}")
        elapsed = (time.perf_counter() - start) * 1000

        avg_per_lookup = elapsed / 1000
        assert avg_per_lookup < 10, f"Lookup cache trop lent: {avg_per_lookup:.2f}ms (objectif: <10ms)"
        print(f"✓ Lookup cache moyen: {avg_per_lookup:.4f}ms")


class TestMaterializedViewPerformance:
    """Tests de performance des vues materialisees."""

    def test_clusters_lookup_under_5ms(self, db_session):
        """
        OBJECTIF : Requete mv_clusters_equivalences < 5ms
        """
        # Creer des donnees de test si necessaire
        # ...

        start = time.perf_counter()
        result = db_session.execute(text("""
            SELECT *
            FROM mv_clusters_equivalences
            WHERE groupe_generique_id = 1234
        """)).fetchone()
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 5, f"Lookup vue materialisee trop lent: {elapsed:.2f}ms (objectif: <5ms)"
        print(f"✓ Lookup mv_clusters_equivalences: {elapsed:.2f}ms")

    def test_refresh_under_30s(self, db_session):
        """
        OBJECTIF : Refresh vue materialisee < 30 secondes
        """
        start = time.perf_counter()
        db_session.execute(text("""
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_clusters_equivalences
        """))
        elapsed = time.perf_counter() - start

        assert elapsed < 30, f"Refresh vue trop lent: {elapsed:.2f}s (objectif: <30s)"
        print(f"✓ Refresh mv_clusters_equivalences: {elapsed:.2f}s")


class TestPreprocessingPerformance:
    """Tests de performance du preprocessing."""

    def test_preprocess_pharma_batch_under_50ms(self):
        """
        OBJECTIF : Preprocessing de 1000 noms < 50ms
        """
        from app.services.intelligent_matching import preprocess_pharma

        test_names = [
            "AMLODIPINE BIOGARAN 5MG CPR B/30",
            "METFORMINE EG 850MG B/90",
            "LOSARTAN ARROW 50MG COMPRIME",
        ] * 333 + ["DOLIPRANE 1000MG"]  # = 1000 noms

        start = time.perf_counter()
        for name in test_names:
            preprocess_pharma(name)
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 50, f"Preprocessing trop lent: {elapsed:.2f}ms (objectif: <50ms)"
        print(f"✓ Preprocessing 1000 noms: {elapsed:.2f}ms")
```

### 14.3 Configuration pytest

```ini
# pytest.ini
[pytest]
markers =
    performance: tests de performance (deselect with '-m "not performance"')
    slow: tests lents (>1s)

testpaths = tests
python_files = test_*.py
python_functions = test_*

# Options par defaut
addopts = -v --tb=short
```

### 14.4 Script d'execution

```bash
#!/bin/bash
# scripts/run_perf_tests.sh

echo "=== Tests de performance Pharma-Remises ==="
echo ""

# Preparer l'environnement de test
export DATABASE_URL="postgresql://localhost/pharma_remises_test"

# Executer les tests de performance
pytest tests/performance/ -v -m performance --tb=short

# Generer rapport
pytest tests/performance/ -v -m performance --html=reports/perf_report.html

echo ""
echo "=== Rapport genere dans reports/perf_report.html ==="
```

### 14.5 Integration CI/CD

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 6 * * 1'  # Chaque lundi a 6h

jobs:
  performance:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: pharma_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-html

      - name: Run performance tests
        run: |
          pytest tests/performance/ -v -m performance --html=perf_report.html
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/pharma_test

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: perf_report.html
```

### 14.6 Checklist implementation

- [ ] **Etape 1** : Creer dossier `tests/performance/`
- [ ] **Etape 2** : Implementer `test_matching_performance.py`
- [ ] **Etape 3** : Implementer `test_materialized_view_performance.py`
- [ ] **Etape 4** : Configurer `pytest.ini` avec markers
- [ ] **Etape 5** : Creer script `run_perf_tests.sh`
- [ ] **Etape 6** : (Optionnel) Configurer CI/CD GitHub Actions

---

**Date de creation** : 2024-12-21
**Mise a jour** : 2024-12-22 - Ajout sections 13 (Audit) et 14 (Tests Performance)
**Statut** : A valider avant implementation
