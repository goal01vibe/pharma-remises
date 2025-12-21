# Architecture Future - Pharma-Remises

## Objectif

Optimiser le systeme de matching pour qu'il soit fait UNE SEULE FOIS et reutilise instantanement pour toutes les simulations/rapprochements ulterieurs.

---

## 1. SCHEMA DATABASE OPTIMISE

### 1.1 Table des signatures canoniques

Chaque combinaison unique molecule+dosage+forme = une entree canonique.

```sql
-- Activer les extensions necessaires
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

-- Table des produits canoniques (molecule+dosage+forme)
CREATE TABLE canonical_products (
    id SERIAL PRIMARY KEY,
    molecule_signature TEXT NOT NULL UNIQUE,  -- Ex: "AMLODIPINE 5MG COMPRIME"
    groupe_generique_id INT,
    pfht_reference DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index trigram pour recherche fuzzy rapide
CREATE INDEX idx_canonical_trgm ON canonical_products
    USING gin (molecule_signature gin_trgm_ops);
```

### 1.2 Table de cache des matchs pre-calcules

```sql
-- Cache des matchs (calcule une fois, utilise pour toujours)
CREATE TABLE product_matches (
    id SERIAL PRIMARY KEY,
    source_cip13 VARCHAR(13) UNIQUE,      -- CIP de la vente ou externe
    source_designation TEXT,               -- Nom original du produit
    canonical_id INT REFERENCES canonical_products(id),
    matched_cip13 VARCHAR(13),            -- CIP correspondant dans BDPM
    match_type VARCHAR(20),               -- 'cip_exact', 'groupe_exact', 'fuzzy'
    match_score FLOAT,                    -- Score 0-100
    pfht DECIMAL(10,4),                   -- Prix PFHT du match
    matched_at TIMESTAMP DEFAULT NOW()
);

-- Index pour lookups ultra-rapides
CREATE INDEX idx_matches_cip ON product_matches(source_cip13);
CREATE INDEX idx_matches_canonical ON product_matches(canonical_id);
CREATE INDEX idx_matches_type ON product_matches(match_type);
```

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

```sql
-- Vue materialisee des clusters d'equivalences par groupe generique
CREATE MATERIALIZED VIEW mv_clusters_equivalences AS
SELECT
    groupe_generique_id,
    -- Tous les noms du groupe concatenes
    string_agg(DISTINCT denomination, ' | ' ORDER BY denomination) as equivalences,
    -- Tous les CIP du groupe
    string_agg(DISTINCT cip13, ', ' ORDER BY cip13) as cips,
    -- Nombre de laboratoires differents
    count(DISTINCT
        CASE WHEN denomination ~ '^[A-Z]+ '
        THEN split_part(denomination, ' ', 1)
        ELSE 'INCONNU' END
    ) as nb_labos,
    -- Prix PFHT (tous identiques dans un groupe, on prend le max non-null)
    MAX(pfht) as pfht_groupe,
    -- Nombre total de references dans le groupe
    count(*) as nb_references,
    -- Date derniere MAJ du groupe
    MAX(updated_at) as derniere_maj
FROM bdpm_equivalence
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

### 4.1 Matching matriciel avec RapidFuzz

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
    # Extraction des noms
    vente_names = [v['designation'] for v in ventes]
    bdpm_names = [b['denomination'] for b in bdpm]

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

### 4.2 Service de matching incremental

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
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'validated', 'rejected'
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP
);

CREATE INDEX idx_pending_status ON pending_validations(status);
CREATE INDEX idx_pending_type ON pending_validations(validation_type);
CREATE INDEX idx_pending_created ON pending_validations(created_at);

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

### 10.7 Vue materialisee avec princeps

```sql
CREATE MATERIALIZED VIEW mv_clusters_equivalences AS
SELECT
    groupe_generique_id,
    -- Princeps du groupe (type_generique = 0)
    MAX(CASE WHEN type_generique = 0 THEN denomination END) as princeps_ref,
    -- Tous les generiques du groupe
    string_agg(
        DISTINCT CASE WHEN type_generique != 0 THEN denomination END,
        ' | '
    ) as generiques,
    -- Autres colonnes...
    MAX(pfht) as pfht_groupe,
    count(*) as nb_references
FROM bdpm_equivalence
WHERE groupe_generique_id IS NOT NULL
GROUP BY groupe_generique_id;
```

### 10.8 Checklist implementation

- [ ] **Etape 1** : Executer script analyse BDPM pour decouvrir patterns EG, TEVA, CRISTERS, ZYDUS
- [ ] **Etape 2** : Completer `LAB_PATTERNS` avec les patterns decouverts
- [ ] **Etape 3** : Modifier import pour extraire `princeps_denomination` par groupe
- [ ] **Etape 4** : Ajouter migration pour remplir `princeps_denomination` existants
- [ ] **Etape 5** : Modifier frontend pour afficher princeps en gras
- [ ] **Etape 6** : Mettre a jour vue materialisee avec colonne `princeps_ref`

---

**Date de creation** : 2024-12-21
**Mise a jour** : 2024-12-21 - Ajout section 10 (Corrections Import BDPM)
**Statut** : A valider avant implementation
