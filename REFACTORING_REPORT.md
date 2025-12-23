# Rapport Refactoring Pharma-Remises

## PROBLEMES CRITIQUES (8)

### 1. Deux systemes de matching coexistent
- Legacy: backend/app/services/matching.py
- Actuel: backend/app/services/intelligent_matching.py
- ACTION: Supprimer matching.py

### 2. Deux pages Simulations dupliquees
- frontend/src/pages/Simulations.tsx (322 lignes)
- frontend/src/pages/SimulationIntelligente.tsx (869 lignes)
- ACTION: Fusionner en une seule page

### 3. Requetes SQL N+1 dans optimization.py
- Lignes 129-144, 337-358
- Query dans une boucle for
- ACTION: Precharger avec .in_() avant la boucle

### 4. Route cassee /simulations/{id}
- Lien existe dans Simulations.tsx ligne 299
- Route n'existe pas dans App.tsx
- ACTION: Creer la page ou supprimer le lien

### 5. Types TypeScript dupliques
- Definis dans types/index.ts
- Redefinis dans lib/api.ts (lignes 219-1020)
- ACTION: Centraliser dans types/index.ts

### 6. Service manquant simulation_with_matching.py
- Reference dans le frontend
- N'existe pas dans le backend
- ACTION: Verifier et documenter

### 7. Import presentations_router peu utilise
- Table Presentation potentiellement obsolete
- ACTION: Verifier si encore necessaire

### 8. Colonne presentation_id inutilisee
- Dans table MesVentes
- Vestige de l'ancien systeme
- ACTION: Supprimer via migration

---

## OPTIMISATIONS RECOMMANDEES (11)

1. Cache TTL trop court (5min) -> Passer a 30min
2. Index manquant sur VenteMatching.match_type
3. Fonctions formatEuro/formatPct dupliquees
4. Appel ventesApi.getImports() avec queryKeys differentes
5. Fuzzy matching execute meme si match CIP exact trouve
6. Tous les produits charges en memoire a chaque matching
7. Pas de pagination sur les resultats (limite a 50 lignes)
8. simulation.py charge toutes les ventes sans filtre import_id
9. Types Decimal incoherents (melange float/Decimal)
10. MoleculeExtractor reinstancie a chaque fois
11. Pas de logging structure

---

## FICHIERS A SUPPRIMER

- backend/app/services/matching.py (Legacy)
- frontend/src/pages/Simulations.tsx (A fusionner)

---

## ORDRE DE REFACTORING

Phase 1 (1-2j): Supprimer legacy, corriger route, centraliser types
Phase 2 (1j): Optimiser SQL (N+1, index)
Phase 3 (2-3j): Fusionner pages Simulations
Phase 4 (1j): Cache, error boundary, tests
