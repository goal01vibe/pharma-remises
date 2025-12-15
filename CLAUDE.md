# Instructions Claude Code - Pharma Remises

## Documentation de Reference

**IMPORTANT**: Avant de lire les fichiers du projet, consulte d'abord:

| Fichier | Description | Quand le lire |
|---------|-------------|---------------|
| **ARCHITECTURE.md** | Structure complete du projet | Au debut de chaque session |
| **ISSUES_AND_FIXES.md** | Bugs connus et corrections | Avant de debugger |

### ARCHITECTURE.md contient:
- Schema base de donnees (tables, colonnes, relations)
- Tous les endpoints API avec descriptions
- Structure fichiers backend et frontend
- Algorithmes cles (matching, calculs remises, optimisation)
- Configuration et ports

**Avantage**: Evite de relire tous les fichiers a chaque session.

---

## Contexte Projet

**Pharma-Remises** = Application de simulation de remises pour pharmacies.

### Fonctionnalites principales:
1. **Import catalogues** labos generiques (CSV)
2. **Import ventes** pharmacie (historique achats)
3. **Matching intelligent** ventes <-> catalogues (RapidFuzz + BDPM)
4. **Simulation remises** (remise ligne + remontee)
5. **Optimisation multi-labos** (OR-Tools ILP)
6. **Comparaison labos** (best combo)

### Stack technique:
- **Frontend**: React + Vite + TanStack Query + shadcn/ui (port 5174)
- **Backend**: FastAPI + SQLAlchemy + Alembic (port 8847)
- **Database**: PostgreSQL Docker (port 5433)
- **Matching**: RapidFuzz (fuzzy) + BDPM (groupe generique)
- **Optimisation**: Google OR-Tools (ILP solver)

---

## Regles de Developpement

### 1. Toujours mettre a jour ARCHITECTURE.md si:
- Nouvelle table ou colonne ajoutee
- Nouvel endpoint API cree
- Nouvelle page frontend ajoutee
- Nouveau service backend cree
- Changement d'algorithme important

### 2. Commits
Apres chaque tache importante terminee, proposer:
> "Tu veux que je commit et push ?"

### 3. Tests
Utiliser Playwright pour tester les fonctionnalites UI.

### 4. Ne pas supprimer sans demander
- Catalogues
- Ventes
- Donnees de matching

---

## Fichiers Cles a Connaitre

### Backend
| Fichier | Role |
|---------|------|
| `backend/main.py` | Point d'entree FastAPI |
| `backend/app/models/models.py` | Tous les modeles SQLAlchemy |
| `backend/app/api/*.py` | Endpoints par domaine |
| `backend/app/services/intelligent_matching.py` | Algorithme matching |
| `backend/app/services/optimizer.py` | OR-Tools multi-labos |
| `backend/app/services/bdpm_lookup.py` | Enrichissement BDPM |

### Frontend
| Fichier | Role |
|---------|------|
| `frontend/src/App.tsx` | Routes |
| `frontend/src/lib/api.ts` | Client API + types |
| `frontend/src/pages/SimulationIntelligente.tsx` | Workflow complet |
| `frontend/src/pages/Optimization.tsx` | Multi-labo config |
| `frontend/src/pages/MesVentes.tsx` | Ventes + incompletes |

---

## Commandes Utiles

```bash
# Demarrer tout
start.bat

# Backend seul
cd backend && python -m uvicorn main:app --reload --port 8847

# Frontend seul
cd frontend && npm run dev

# Migrations
cd backend && alembic upgrade head

# Build frontend
cd frontend && npm run build
```

---

## Calculs a Connaitre

### Chiffre Perdu
```
chiffre_perdu = chiffre_total_BDPM - chiffre_realisable_labo
```

### Remise Totale
```
remise_ligne = prix × remise_pct
remontee = (prix - remise_ligne) × remontee_pct
total = remise_ligne + remontee
```

### Matching (priorite)
1. `exact_cip` (100%) - CIP13 identique
2. `groupe_generique` (95%) - Meme groupe BDPM
3. `fuzzy_molecule` (70-90%) - Molecule similaire
4. `fuzzy_commercial` (60-80%) - Nom commercial

---

## Ports et URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5174 |
| Backend | http://localhost:8847 |
| API Docs | http://localhost:8847/docs |
| PostgreSQL | localhost:5433 |

---

## A Eviter

- Ne pas modifier les catalogues sans demander
- Ne pas supprimer les matchings sans raison
- Ne pas changer la structure DB sans migration
- Ne pas oublier de redemarrer le backend apres modif routes
