# Pharma Remises

Application de simulation et comparaison des remises laboratoires generiques.

## Stack Technique

- **Frontend**: React 18 + Vite + TypeScript + Shadcn/ui + TanStack
- **Backend**: FastAPI + SQLAlchemy + Alembic
- **Database**: PostgreSQL
- **IA**: OpenAI (gpt-4o-mini / gpt-4o) pour extraction PDF

## Installation

### 1. Base de donnees

```bash
docker-compose up -d
```

PostgreSQL sera disponible sur `localhost:5433`.

### 2. Backend

```bash
cd backend
pip install -r requirements.txt

# Migration initiale
alembic upgrade head

# Lancer le serveur
uvicorn main:app --reload --port 8003
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend disponible sur `http://localhost:5174`.

## Configuration

Copier `.env` et configurer:

- `DATABASE_URL`: URL PostgreSQL
- `OPENAI_API_KEY`: Cle API OpenAI (pour extraction PDF)

## Fonctionnalites

1. **Gestion laboratoires**: CRUD labos avec remise negociee
2. **Import catalogues**: Excel/CSV ou PDF (extraction IA)
3. **Import ventes**: Historique achats annuels
4. **Matching produits**: Auto + manuel (click-to-match)
5. **Simulation**: Calcul remises par scenario
6. **Comparaison**: Trouver le meilleur labo
7. **Exclusions**: Gerer les produits exclus de la remontee

## Ports

- Frontend: 5174
- Backend: 8003
- PostgreSQL: 5433

## Calcul des remises

```
Remise totale = Remise ligne + Complement remontee

Où:
- Remise ligne = % sur le catalogue du produit (35%, 40%...)
- Complement remontee = max(0, % cible - % ligne)
- % cible peut etre:
  - Normal: % negocie du labo (ex: 55%)
  - Partiel: % specifique au produit (ex: 30%)
  - Exclu: 0% (pas de complement)
```
