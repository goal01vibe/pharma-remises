# Architecture Pharma-Remises

> **Document de reference** - Mis a jour automatiquement lors des modifications structurelles.
> Derniere mise a jour: 2024-12-15

## Vue d'ensemble

Pharma-Remises est une application de simulation de remises pour pharmacies, permettant de comparer les offres de differents laboratoires generiques et d'optimiser les achats.

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React/Vite)     │  Backend (FastAPI)                 │
│  Port: 5174                │  Port: 8847                        │
├────────────────────────────┼────────────────────────────────────┤
│  TanStack Query            │  SQLAlchemy ORM                    │
│  shadcn/ui + Tailwind      │  Alembic Migrations                │
│  React Router              │  OR-Tools (Optimisation)           │
│                            │  RapidFuzz (Matching)              │
├────────────────────────────┴────────────────────────────────────┤
│                     PostgreSQL (Docker)                          │
│                     Port: 5433                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Base de Donnees

### Tables Principales

| Table | Description | Fichier |
|-------|-------------|---------|
| `laboratoires` | Labos generiques (Viatris, Zentiva, etc.) | models.py:18 |
| `catalogue_produits` | Produits par labo avec prix et remises | models.py:58 |
| `mes_ventes` | Historique ventes pharmacie importees | models.py:130 |
| `vente_matching` | Cache matching ventes <-> produits labo | models.py:230 |
| `scenarios` | Scenarios de simulation | models.py:187 |
| `resultats_simulation` | Resultats calcules par scenario | models.py:204 |
| `bdpm_equivalences` | Referentiel BDPM (CIP13 -> groupe generique) | models.py:274 |

### Tables Secondaires

| Table | Description |
|-------|-------------|
| `presentations` | Referentiel presentations (code interne) |
| `imports` | Historique des imports fichiers |
| `regles_remontee` | Regles d'exclusion/remontee partielle |
| `regles_remontee_produits` | Liaison regles <-> produits |
| `correspondances_manuelles` | Matchings manuels utilisateur |
| `parametres` | Parametres globaux application |

### Relations Cles

```
laboratoires (1) ──────< (N) catalogue_produits
     │
     └──────< (N) vente_matching >──────(1) mes_ventes
                      │
                      └──────(1) catalogue_produits

mes_ventes (N) >────── (1) imports

bdpm_equivalences ─── lookup par CIP13 ───> groupe_generique_id
```

### Colonnes Importantes MesVentes

| Colonne | Type | Description |
|---------|------|-------------|
| `code_cip_achete` | String | CIP13 du produit achete |
| `designation` | String | Nom complet produit |
| `quantite_annuelle` | Integer | Quantite sur la periode |
| `prix_bdpm` | Numeric | Prix BDPM de reference (enrichi) |
| `has_bdpm_price` | Boolean | True si prix BDPM trouve |
| `groupe_generique_id` | Integer | ID groupe pour matching rapide |

### Colonnes Importantes CatalogueProduit

| Colonne | Type | Description |
|---------|------|-------------|
| `code_cip` | String | Code CIP officiel |
| `prix_ht` | Numeric | Prix d'achat HT |
| `remise_pct` | Numeric | % remise ligne |
| `remontee_pct` | Numeric | % remontee (NULL=normale, 0=exclu) |
| `groupe_generique_id` | Integer | ID groupe BDPM pour matching |
| `source` | String | 'bdpm' ou 'manuel' |

---

## Backend (FastAPI)

### Structure Fichiers

```
backend/
├── main.py                 # Point d'entree FastAPI
├── alembic/               # Migrations DB
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_*.py
│       ├── 003_*.py
│       └── 004_bdpm_price_enrichment.py
├── app/
│   ├── api/               # Endpoints REST
│   │   ├── __init__.py    # Export routers
│   │   ├── laboratoires.py
│   │   ├── catalogues.py
│   │   ├── ventes.py
│   │   ├── matching.py
│   │   ├── simulations.py
│   │   ├── optimization.py  # Multi-labo OR-Tools
│   │   ├── import_data.py
│   │   ├── import_rapprochement.py
│   │   ├── coverage.py
│   │   ├── reports.py
│   │   ├── presentations.py
│   │   └── parametres.py
│   ├── models/
│   │   └── models.py      # SQLAlchemy models
│   ├── schemas/
│   │   └── schemas.py     # Pydantic schemas
│   ├── services/
│   │   ├── matching.py           # Matching basique
│   │   ├── intelligent_matching.py # RapidFuzz matching
│   │   ├── simulation.py         # Calculs simulation
│   │   ├── optimizer.py          # OR-Tools ILP solver
│   │   ├── bdpm_lookup.py        # Enrichissement BDPM
│   │   ├── bdpm_import.py        # Import BDPM complet
│   │   ├── combo_optimizer.py    # Best combo labos
│   │   ├── report_generator.py   # Generation PDF
│   │   └── pdf_extraction.py     # Extraction PDF
│   ├── db/
│   │   └── database.py    # Config SQLAlchemy
│   ├── scripts/
│   │   ├── import_bdpm.py
│   │   └── update_pfht_catalogues.py
│   └── utils/
│       └── logger.py      # Logging configuration
```

### Endpoints API

#### Laboratoires (`/api/laboratoires`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Liste tous les labos |
| GET | `/{id}` | Details d'un labo |
| POST | `/` | Creer un labo |
| PUT | `/{id}` | Modifier un labo |
| DELETE | `/{id}` | Supprimer un labo |
| GET | `/{id}/catalogue` | Catalogue du labo |
| GET | `/{id}/regles-remontee` | Regles du labo |

#### Catalogues (`/api/catalogues`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Liste produits (avec filtres) |
| GET | `/{id}` | Details produit |
| POST | `/` | Ajouter produit |
| PUT | `/{id}` | Modifier produit |
| DELETE | `/{id}` | Supprimer produit |
| PATCH | `/{id}/remontee` | Modifier remontee |
| PATCH | `/bulk/remontee` | Modifier remontee en masse |
| DELETE | `/laboratoire/{id}/clear` | Vider catalogue labo |
| GET | `/compare/{id1}/{id2}` | Comparer 2 catalogues |

#### Ventes (`/api/ventes`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Liste ventes (paginee) |
| GET | `/imports` | Liste imports ventes |
| DELETE | `/{id}` | Supprimer une vente |
| GET | `/incomplete` | Ventes sans prix BDPM |
| GET | `/incomplete/count` | Comptage incompletes |
| DELETE | `/incomplete/bulk` | Supprimer incompletes |
| POST | `/re-enrich/{import_id}` | Re-enrichir BDPM |

#### Matching (`/api/matching`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/process-sales` | Lancer matching intelligent |
| POST | `/analyze` | Analyser matching potentiel |
| GET | `/stats/{import_id}` | Stats matching par import |
| GET | `/details/{import_id}/{labo_id}` | Details matching labo |
| DELETE | `/clear/{import_id}` | Supprimer matchings |
| GET | `/search-products/{labo_id}` | Recherche produits |
| PUT | `/manual/{vente_id}/{labo_id}` | Match manuel |
| DELETE | `/manual/{vente_id}/{labo_id}` | Supprimer match manuel |

#### Simulations (`/api/simulations`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Liste scenarios |
| GET | `/{id}` | Details scenario |
| POST | `/` | Creer scenario |
| DELETE | `/{id}` | Supprimer scenario |
| POST | `/{id}/run` | Executer simulation |
| GET | `/{id}/resultats` | Resultats details |
| GET | `/{id}/totaux` | Totaux simulation |
| POST | `/comparaison` | Comparer scenarios |
| POST | `/run-with-matching` | Simulation + matching |

#### Optimization (`/api/optimization`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/labos-disponibles` | Labos avec matchings |
| GET | `/produits-labo` | Autocomplete produits |
| POST | `/run` | Lancer optimisation |
| POST | `/preview` | Previsualisation |

#### Import (`/api/import`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/catalogue` | Importer catalogue CSV |
| POST | `/ventes` | Importer ventes CSV |
| GET | `/ventes/list` | Liste imports ventes |
| DELETE | `/ventes/{id}` | Supprimer import |
| POST | `/extract-pdf` | Extraire PDF |
| POST | `/bdpm/import-all` | Import BDPM complet |
| POST | `/bdpm/import-target-labs` | Import BDPM labos cibles |
| GET | `/bdpm/stats` | Stats BDPM |

#### Coverage (`/api/coverage`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/best-combo/{labo_id}` | Meilleure combinaison |
| GET | `/gaps/{labo_id}` | Produits manquants |
| GET | `/matrix` | Matrice couverture |

#### Reports (`/api/reports`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/simulation/pdf` | Export PDF simulation |

---

## Services Backend

### `intelligent_matching.py`
Algorithme de matching en 4 etapes:
1. **Exact CIP** - Match par code CIP13 identique
2. **Groupe generique** - Match par groupe_generique_id BDPM
3. **Fuzzy molecule** - RapidFuzz sur molecule+dosage+forme
4. **Fuzzy commercial** - RapidFuzz sur nom commercial

### `optimizer.py` (OR-Tools)
Optimisation lineaire (ILP) pour repartition multi-labos:
- **Variables**: x[vente_id, labo_id] = 0 ou 1
- **Objectif**: Maximiser somme(quantite × prix × taux_remise)
- **Contraintes**: Objectifs minimum par labo

### `bdpm_lookup.py`
Enrichissement ventes avec prix BDPM:
- Lookup CIP13 -> prix fabricant HT
- Stockage groupe_generique_id pour matching rapide

### `simulation.py`
Calcul des remises:
- **Remise ligne** = prix × remise_pct
- **Remontee** = (prix - remise_ligne) × remontee_pct
- **Chiffre perdu** = total_BDPM - realisable_labo

---

## Frontend (React/Vite)

### Structure Fichiers

```
frontend/src/
├── main.tsx               # Point d'entree React
├── App.tsx                # Routes et providers
├── index.css              # Styles Tailwind
├── lib/
│   ├── api.ts            # Client API (fetch + types)
│   └── utils.ts          # Fonctions utilitaires
├── types/
│   └── index.ts          # Types TypeScript
├── components/
│   ├── ui/               # Composants shadcn/ui
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── select.tsx
│   │   ├── tabs.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── Layout.tsx    # Layout principal
│   │   ├── Sidebar.tsx   # Navigation laterale
│   │   └── Header.tsx    # En-tete page
│   └── dashboard/
│       └── KPICards.tsx  # Cartes KPI
└── pages/
    ├── Dashboard.tsx           # Accueil
    ├── Laboratoires.tsx        # Gestion labos
    ├── Catalogues.tsx          # Gestion catalogues
    ├── MesVentes.tsx           # Ventes importees
    ├── Simulations.tsx         # Scenarios classiques
    ├── SimulationIntelligente.tsx  # Workflow complet
    ├── MatchingDetails.tsx     # Details matching
    ├── Optimization.tsx        # Multi-labo optimizer
    ├── Comparaison.tsx         # Comparaison labos
    ├── Import.tsx              # Import fichiers
    └── Parametres.tsx          # Configuration
```

### Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Vue d'ensemble KPIs |
| `/laboratoires` | Laboratoires | CRUD laboratoires |
| `/catalogues` | Catalogues | Gestion produits |
| `/ventes` | MesVentes | Ventes importees |
| `/simulations` | Simulations | Scenarios basiques |
| `/simulation-intelligente` | SimulationIntelligente | Workflow complet |
| `/matching-details/:importId/:laboId` | MatchingDetails | Details matching |
| `/optimization` | Optimization | Multi-labo |
| `/comparaison` | Comparaison | Compare labos |
| `/import` | Import | Import fichiers |
| `/parametres` | Parametres | Configuration |

### Pages Principales

#### SimulationIntelligente.tsx
Workflow en 4 etapes:
1. Selection import + labo principal
2. Matching intelligent (multi-labos)
3. Simulation avec calculs
4. Best combo (meilleure combinaison)

#### Optimization.tsx
Configuration optimisation multi-labos:
1. Selection import ventes
2. Configuration labos (activer/desactiver)
3. Objectifs par labo (% ou montant fixe)
4. Exclusions par labo (autocomplete)
5. Lancement et resultats

#### MesVentes.tsx
Affichage ventes avec:
- Badge "Sans BDPM" pour ventes incompletes
- Actions: re-enrichir, supprimer incompletes
- Colonnes: CIP, designation, quantite, prix BDPM

---

## Demarrage

### Script `start.bat`
```
1. Verifie Docker
2. Lance PostgreSQL (docker-compose)
3. Lance Backend (port 8847)
4. Lance Frontend (port 5174)
5. Ouvre navigateur
```

### URLs
- Frontend: http://localhost:5174
- Backend: http://localhost:8847
- API Docs: http://localhost:8847/docs
- PostgreSQL: localhost:5433

### Logs
```
C:\pharma-remises\logs\
├── backend.log
└── frontend.log
```

---

## Algorithmes Cles

### Calcul Chiffre Perdu
```
chiffre_total_ht = SUM(prix_bdpm × quantite)      # Reference marche
chiffre_realisable_ht = SUM(prix_labo × quantite) # Ce qu'on peut acheter
chiffre_perdu_ht = chiffre_total_ht - chiffre_realisable_ht
```

### Calcul Remises
```
remise_ligne = prix_ht × remise_pct
base_remontee = prix_ht - remise_ligne
remontee = base_remontee × remontee_pct (si pas exclu)
total_remise = remise_ligne + remontee
```

### Matching Intelligent (Priorite)
```
1. exact_cip     → Score 100%  (CIP13 identique)
2. groupe_gen    → Score 95%   (meme groupe_generique_id)
3. fuzzy_molecule→ Score 70-90% (RapidFuzz molecule)
4. fuzzy_nom     → Score 60-80% (RapidFuzz nom commercial)
```

---

## Configuration

### Variables d'environnement
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/pharma_remises
```

### Ports
| Service | Port |
|---------|------|
| Frontend | 5174 |
| Backend | 8847 |
| PostgreSQL | 5433 |

---

## Migrations

| Version | Description |
|---------|-------------|
| 001 | Schema initial |
| 002 | Ajout BDPM tables |
| 003 | Ajout matching cache |
| 004 | Ajout prix_bdpm, has_bdpm_price, groupe_generique_id sur mes_ventes |

### Executer migrations
```bash
cd backend
alembic upgrade head
```

---

## Dependances Cles

### Backend
- `fastapi` - Framework API
- `sqlalchemy` - ORM
- `alembic` - Migrations
- `rapidfuzz` - Matching fuzzy
- `ortools` - Optimisation lineaire
- `pandas` - Traitement donnees
- `reportlab` - Generation PDF

### Frontend
- `react` - Framework UI
- `vite` - Build tool
- `@tanstack/react-query` - Data fetching
- `react-router-dom` - Routing
- `tailwindcss` - Styles
- `shadcn/ui` - Composants UI
- `lucide-react` - Icones
