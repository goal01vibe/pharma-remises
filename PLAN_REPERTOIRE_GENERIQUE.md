# Plan - Repertoire Generique Global + Systeme de Matching Persistant

## 1. Architecture du Systeme de Memoire de Matching

### Concept : Groupes d'Equivalence Transitifs

Si A match B, et B match C, alors A-B-C sont dans le meme groupe d'equivalence.
Tout futur matching impliquant A, B ou C sera instantane.

### Nouvelle Table : `matching_memory`

```sql
CREATE TABLE matching_memory (
    id SERIAL PRIMARY KEY,
    groupe_equivalence_id INTEGER NOT NULL,  -- Groupe transitif
    cip13 VARCHAR(13) NOT NULL UNIQUE,       -- Code CIP (cle unique)
    designation VARCHAR(500),                 -- Nom du produit
    source VARCHAR(50),                       -- 'vente', 'catalogue', 'bdpm'
    source_id INTEGER,                        -- ID dans la table source
    groupe_generique_id INTEGER,              -- Groupe BDPM si connu
    match_origin VARCHAR(100),                -- 'exact_cip', 'groupe_generique', 'fuzzy', 'manuel'
    match_score NUMERIC(5,2),                 -- Score du match initial
    validated BOOLEAN DEFAULT FALSE,          -- Valide par l'utilisateur
    validated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_groupe_equiv (groupe_equivalence_id),
    INDEX idx_groupe_gener (groupe_generique_id)
);
```

### Logique de Fusion des Groupes

```python
def register_match(cip_a: str, cip_b: str, match_type: str, score: float):
    """Enregistre un match et fusionne les groupes si necessaire."""

    groupe_a = get_groupe_for_cip(cip_a)
    groupe_b = get_groupe_for_cip(cip_b)

    if groupe_a and groupe_b and groupe_a != groupe_b:
        # Fusionner : tous les CIP du groupe_b rejoignent groupe_a
        merge_groupes(groupe_a, groupe_b)
    elif groupe_a:
        # Ajouter cip_b au groupe de cip_a
        add_to_groupe(cip_b, groupe_a)
    elif groupe_b:
        # Ajouter cip_a au groupe de cip_b
        add_to_groupe(cip_a, groupe_b)
    else:
        # Creer nouveau groupe avec les deux
        create_groupe([cip_a, cip_b])
```

---

## 2. Systeme de Mise a Jour BDPM

### Nouvelle Table : `bdpm_file_status`

```sql
CREATE TABLE bdpm_file_status (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(100) NOT NULL UNIQUE,  -- 'CIS_bdpm.txt', 'CIS_CIP_bdpm.txt', etc.
    file_url VARCHAR(500),                   -- URL de telechargement
    file_hash VARCHAR(64),                   -- SHA256 du fichier
    file_size INTEGER,                       -- Taille en octets
    last_checked TIMESTAMP,                  -- Derniere verification
    last_downloaded TIMESTAMP,               -- Dernier telechargement
    last_integrated TIMESTAMP,               -- Derniere integration en base
    records_count INTEGER,                   -- Nombre d'enregistrements
    new_records INTEGER DEFAULT 0,           -- Nouveaux depuis derniere integration
    removed_records INTEGER DEFAULT 0        -- Supprimes depuis derniere integration
);
```

### Fichiers BDPM a Telecharger

| Fichier | URL | Utilisation |
|---------|-----|-------------|
| CIS_bdpm.txt | https://base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier=CIS_bdpm.txt | Denominations, statut |
| CIS_CIP_bdpm.txt | idem?fichier=CIS_CIP_bdpm.txt | CIP13, prix PFHT |
| CIS_GENER_bdpm.txt | idem?fichier=CIS_GENER_bdpm.txt | Groupes generiques |
| CIS_COMPO_bdpm.txt | idem?fichier=CIS_COMPO_bdpm.txt | Composition (optionnel) |

### Workflow de Mise a Jour

```
1. Au demarrage OU bouton manuel :
   - Telecharger HEAD de chaque fichier (taille, date)
   - Comparer hash avec bdpm_file_status

2. Si hash different :
   - Telecharger le fichier complet
   - Parser et comparer avec donnees actuelles
   - Identifier : nouveaux CIP, CIP modifies, CIP absents

3. Integration :
   - Nouveaux CIP → INSERT automatique
   - CIP modifies → UPDATE automatique
   - CIP absents → NE PAS SUPPRIMER, mais :
     * Marquer comme "absent_bdpm = true"
     * Ajouter a la liste de revue utilisateur

4. Afficher liste des CIP absents pour action manuelle
```

### Indicateur en Haut de Page

```typescript
// Header global affichant :
<BdpmStatusBadge />
// "BDPM: verifie le 17/12/2024" (vert si < 7 jours)
// "BDPM: mis a jour le 17/12/2024" (bleu si MaJ recente)
// "BDPM: verifier les mises a jour" (orange si > 7 jours)
```

---

## 3. Menu Repertoire Generique Global

### Structure Frontend

```
/repertoire-generique
├── Vue principale : Liste complete du repertoire (12101 lignes)
├── Filtres : Groupe, Molecule, Labo, Type (princeps/generique)
├── Export Excel
└── Actions :
    ├── "Rapprocher mes ventes" → /repertoire-generique/rapprochement
    └── "Verifier BDPM" → Declenche mise a jour
```

### Workflow Rapprochement Ventes / Repertoire

```
ETAPE 1 : Analyse
┌─────────────────────────────────────────────────────────────┐
│  Analyser mes ventes vs repertoire generique                │
│                                                             │
│  [Lancer l'analyse]                                         │
└─────────────────────────────────────────────────────────────┘

ETAPE 2 : Resultats avec 3 categories
┌─────────────────────────────────────────────────────────────┐
│  DANS LE REPERTOIRE (match exact CIP) : 2340 ventes         │
│  ✅ Ces ventes sont des generiques substituables            │
├─────────────────────────────────────────────────────────────┤
│  MATCH PROBABLE (groupe generique + fuzzy) : 45 ventes      │
│  ⚠️ Verifier ces correspondances                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ □ Tout cocher  □ Tout decocher                       │   │
│  │ ☑ DOLIPRANE 500MG → PARACETAMOL BIOGARAN (92%)       │   │
│  │ ☐ EFFERALGAN 1G → PARACETAMOL ARROW (87%)            │   │
│  │ ...                                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│  [Valider les correspondances selectionnees]                │
├─────────────────────────────────────────────────────────────┤
│  HORS REPERTOIRE : 156 ventes                               │
│  ❌ Ces ventes ne sont PAS des generiques substituables     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ □ Tout cocher  □ Tout decocher                       │   │
│  │ ☑ DOLIPRANE CODEINE (hors repertoire)                │   │
│  │ ☑ SPASFON LYOC (princeps sans generique)             │   │
│  │ ...                                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│  [Supprimer les ventes selectionnees]                       │
└─────────────────────────────────────────────────────────────┘

ETAPE 3 : Confirmation suppression
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ CONFIRMATION                                            │
│                                                             │
│  Vous allez supprimer 156 ventes hors repertoire.           │
│  Cette action est irreversible.                             │
│                                                             │
│  [Annuler]  [Confirmer la suppression]                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Integration avec le Matching Existant

### Modification de `intelligent_matching.py`

Avant chaque matching, verifier la memoire :

```python
def find_matches_for_vente(vente: MesVentes, catalogues: List[CatalogueProduit]):
    # 1. Verifier la memoire d'abord
    if vente.code_cip:
        memory_matches = get_from_matching_memory(vente.code_cip)
        if memory_matches:
            return memory_matches  # Match instantane !

    # 2. Sinon, faire le matching normal
    matches = do_normal_matching(vente, catalogues)

    # 3. Enregistrer le resultat dans la memoire
    for match in matches:
        register_match(vente.code_cip, match.code_cip, match.match_type, match.score)

    return matches
```

---

## 5. Fichiers a Creer/Modifier

### Backend

| Fichier | Action | Description |
|---------|--------|-------------|
| `app/models/models.py` | MODIFIER | Ajouter MatchingMemory, BdpmFileStatus |
| `app/services/matching_memory.py` | CREER | Service de memoire transitive |
| `app/services/bdpm_downloader.py` | CREER | Telechargement + hash BDPM |
| `app/api/repertoire.py` | CREER | Endpoints repertoire generique |
| `app/api/bdpm.py` | MODIFIER | Ajouter endpoints status/update |
| `alembic/versions/xxx_matching_memory.py` | CREER | Migration |

### Frontend

| Fichier | Action | Description |
|---------|--------|-------------|
| `src/pages/RepertoireGenerique.tsx` | CREER | Page principale |
| `src/pages/RapprochementVentes.tsx` | CREER | Workflow 2 etapes |
| `src/components/BdpmStatusBadge.tsx` | CREER | Indicateur header |
| `src/components/Layout.tsx` | MODIFIER | Ajouter badge BDPM |
| `src/lib/api.ts` | MODIFIER | Ajouter endpoints |

---

## 6. Ordre d'Implementation

1. ☐ Tables SQL (matching_memory, bdpm_file_status)
2. ☐ Service matching_memory.py (logique transitive)
3. ☐ Service bdpm_downloader.py (hash + download)
4. ☐ Endpoints API /repertoire/*
5. ☐ Frontend RepertoireGenerique.tsx
6. ☐ Frontend RapprochementVentes.tsx
7. ☐ Composant BdpmStatusBadge.tsx
8. ☐ Integration dans le matching existant
9. ☐ Tests

---

## Questions Avant Implementation

1. **URL de telechargement BDPM** : Est-ce bien https://base-donnees-publique.medicaments.gouv.fr/telechargement.php?fichier=XXX ou une autre URL ?

2. **Frequence de verification** : Au demarrage de l'app uniquement, ou aussi toutes les X heures ?

3. **Stockage des fichiers BDPM** : Garder dans `C:\pdf-extractor\data\bdpm\raw\` ou deplacer dans `C:\pharma-remises\backend\data\bdpm\` ?
