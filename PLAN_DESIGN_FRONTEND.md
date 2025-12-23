# PLAN DESIGN FRONTEND - Pharma Remises

> Plan d'amélioration de l'interface utilisateur avec focus sur la performance et l'UX moderne
>
> **Date**: 2025-01-XX
> **Statut**: En attente d'approbation
> **Backend associé**: Voir `ARCHITECTURE_FUTURE.md` (sections API pagination)

---

## 1. OBJECTIFS PRINCIPAUX

### 1.1 Performance critique
- **Virtualization** : Afficher 200k+ lignes sans lag (BDPM, catalogues)
- **Infinite Scroll** : Chargement progressif des données
- **Lazy Loading** : Composants chargés à la demande

### 1.2 Expérience utilisateur
- **Feedback visuel** : L'utilisateur sait toujours ce qui se passe
- **États de chargement** : Skeletons au lieu d'écrans blancs
- **Gestion d'erreurs** : Messages clairs et actions de récupération

---

## 2. STACK TECHNIQUE FRONTEND

### 2.1 Bibliothèques existantes (à conserver)
```
React + TypeScript + Vite
TailwindCSS
Shadcn/ui
TanStack Query (React Query)
```

### 2.2 Bibliothèques à ajouter
```bash
npm install @tanstack/react-virtual    # Virtualization
npm install @tanstack/react-table      # Table headless (optionnel si déjà présent)
```

---

## 3. COMPOSANTS À CRÉER

### 3.1 VirtualizedTable - Tables avec virtualization

**Fichier**: `src/components/ui/VirtualizedTable.tsx`

**Props**:
```typescript
interface VirtualizedTableProps<T> {
  data: T[]
  columns: ColumnDef<T>[]
  rowHeight?: number           // Défaut: 48px
  overscan?: number            // Lignes pré-rendues hors écran (défaut: 5)
  containerHeight?: string     // Défaut: "calc(100vh - 200px)"
  onRowClick?: (row: T) => void
  selectedRowId?: string | number
  isLoading?: boolean
  emptyMessage?: string
}
```

**Comportement**:
- Rend uniquement les lignes visibles + overscan
- Support du tri par colonnes
- Support de la sélection de ligne
- Scroll fluide même avec 200k+ lignes
- Affiche SkeletonTable pendant le chargement

**Utilisation**:
```tsx
<VirtualizedTable
  data={repertoireGenerique}
  columns={columns}
  rowHeight={48}
  overscan={10}
  onRowClick={(row) => openDrawer(row)}
/>
```

---

### 3.2 InfiniteScrollTable - Tables avec pagination infinie

**Fichier**: `src/components/ui/InfiniteScrollTable.tsx`

**Props**:
```typescript
interface InfiniteScrollTableProps<T> {
  queryKey: string[]
  queryFn: (params: { pageParam: string | null }) => Promise<PaginatedResponse<T>>
  columns: ColumnDef<T>[]
  rowHeight?: number
  threshold?: number           // Distance avant fetch (défaut: 500px)
  onRowClick?: (row: T) => void
}

interface PaginatedResponse<T> {
  items: T[]
  nextCursor: string | null
  totalCount: number
}
```

**Comportement**:
- Utilise `useInfiniteQuery` de TanStack Query
- Charge automatiquement la page suivante à l'approche du bas
- Combine virtualization + infinite scroll
- Affiche indicateur de chargement en bas
- Gère les erreurs avec retry automatique

**Utilisation**:
```tsx
<InfiniteScrollTable
  queryKey={['catalogues', fournisseurId]}
  queryFn={({ pageParam }) => fetchCatalogues({ cursor: pageParam, limit: 100 })}
  columns={catalogueColumns}
  onRowClick={handleRowClick}
/>
```

---

### 3.3 SkeletonTable - État de chargement

**Fichier**: `src/components/ui/SkeletonTable.tsx`

**Props**:
```typescript
interface SkeletonTableProps {
  columns: number              // Nombre de colonnes
  rows?: number                // Nombre de lignes (défaut: 10)
  showHeader?: boolean         // Afficher header skeleton (défaut: true)
  rowHeight?: number           // Hauteur des lignes (défaut: 48px)
}
```

**Design**:
- Animation pulse subtile
- Largeurs de colonnes variées (réaliste)
- Transition fluide vers les vraies données

---

### 3.4 ProgressStepper - Indicateur de progression

**Fichier**: `src/components/ui/ProgressStepper.tsx`

**Props**:
```typescript
interface ProgressStepperProps {
  steps: {
    id: string
    label: string
    status: 'pending' | 'in_progress' | 'completed' | 'error'
    detail?: string
  }[]
  orientation?: 'horizontal' | 'vertical'
}
```

**Utilisation** (page Matching):
```tsx
<ProgressStepper
  steps={[
    { id: 'load', label: 'Chargement données', status: 'completed' },
    { id: 'match', label: 'Matching en cours', status: 'in_progress', detail: '45%' },
    { id: 'validate', label: 'Validation', status: 'pending' },
    { id: 'save', label: 'Sauvegarde', status: 'pending' }
  ]}
/>
```

---

### 3.5 FilterBar - Barre de filtres unifiée

**Fichier**: `src/components/ui/FilterBar.tsx`

**Props**:
```typescript
interface FilterBarProps {
  filters: FilterConfig[]
  onFilterChange: (filters: Record<string, any>) => void
  onReset: () => void
  activeCount?: number
}

interface FilterConfig {
  key: string
  label: string
  type: 'text' | 'select' | 'date' | 'range' | 'checkbox'
  options?: { value: string; label: string }[]
  placeholder?: string
}
```

**Design**:
- Filtres inline horizontaux
- Badge avec nombre de filtres actifs
- Bouton "Réinitialiser"
- Sauvegarde des filtres dans URL (query params)

---

### 3.6 EmptyState - État vide

**Fichier**: `src/components/ui/EmptyState.tsx`

**Props**:
```typescript
interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
}
```

**Variantes**:
- Aucun résultat de recherche
- Aucune donnée
- Erreur de chargement
- Premiers pas (onboarding)

---

### 3.7 ScoreBadge - Badge de score coloré

**Fichier**: `src/components/ui/ScoreBadge.tsx`

**Props**:
```typescript
interface ScoreBadgeProps {
  score: number                // 0-100
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean          // Affiche "Excellent", "Bon", etc.
}
```

**Couleurs**:
- 90-100: Vert (Excellent)
- 70-89: Bleu (Bon)
- 50-69: Jaune (Moyen)
- 0-49: Rouge (Faible)

---

### 3.8 GroupeDrawer - Drawer détails groupe

**Fichier**: `src/components/GroupeDrawer.tsx`

**Amélioration de l'existant**:
```typescript
interface GroupeDrawerProps {
  groupeId: number | null
  onClose: () => void
  // Nouveaux champs
  showPrincepsCip13?: boolean  // Afficher CIP13 du princeps
  showHistory?: boolean        // Afficher historique des matchings
}
```

**Sections**:
1. Informations groupe générique
2. **Nouveau**: CIP13 du princeps (si disponible)
3. Liste des produits matchés
4. **Nouveau**: Historique des modifications

---

## 4. HOOKS PERSONNALISÉS

### 4.1 useInfinitePagination

**Fichier**: `src/hooks/useInfinitePagination.ts`

```typescript
export function useInfinitePagination<T>(
  queryKey: string[],
  fetchFn: (cursor: string | null) => Promise<PaginatedResponse<T>>,
  options?: {
    pageSize?: number
    staleTime?: number
  }
) {
  // Utilise useInfiniteQuery avec configuration optimisée
  // Retourne: data, fetchNextPage, hasNextPage, isFetching, error
}
```

---

### 4.2 useTableVirtualization

**Fichier**: `src/hooks/useTableVirtualization.ts`

```typescript
export function useTableVirtualization<T>(
  data: T[],
  options: {
    rowHeight: number
    containerRef: RefObject<HTMLElement>
    overscan?: number
  }
) {
  // Utilise useVirtualizer de @tanstack/react-virtual
  // Retourne: virtualRows, totalSize, scrollToIndex
}
```

---

### 4.3 useDebounceSearch

**Fichier**: `src/hooks/useDebounceSearch.ts`

```typescript
export function useDebounceSearch(
  searchFn: (query: string) => void,
  delay?: number  // Défaut: 300ms
) {
  // Debounce la recherche pour éviter trop de requêtes
  // Retourne: { searchTerm, setSearchTerm, isSearching }
}
```

---

## 5. PAGES À MODIFIER

### 5.1 Page Catalogues (`/catalogues`)

**État actuel**: Limite à 2000 lignes, pas de pagination

**Modifications**:
1. Remplacer table standard par `InfiniteScrollTable`
2. Ajouter `FilterBar` avec filtres:
   - Fournisseur (select)
   - Recherche produit (text)
   - Date import (date range)
3. Ajouter `SkeletonTable` pendant chargement initial
4. Ajouter `EmptyState` si aucun catalogue

**API requise**: `GET /api/catalogues?cursor=xxx&limit=100` (voir ARCHITECTURE_FUTURE.md)

---

### 5.2 Page MesVentes (`/mes-ventes`)

**État actuel**: Limite à 1000 lignes

**Modifications**:
1. Remplacer par `InfiniteScrollTable`
2. Ajouter filtres:
   - Période (date range)
   - Produit (text search)
   - Statut matching (select)
3. Ajouter export CSV avec progression

**API requise**: `GET /api/ventes?cursor=xxx&limit=100`

---

### 5.3 Page RepertoireGenerique (`/repertoire`)

**État actuel**: Potentiellement 200k+ lignes (BDPM)

**Modifications**:
1. **CRITIQUE**: Utiliser `VirtualizedTable` avec virtualization
2. Ajouter recherche debounced côté serveur
3. Filtres:
   - Type (générique/princeps)
   - Laboratoire
   - Recherche DCI/nom

**API requise**: `GET /api/repertoire?search=xxx&cursor=xxx&limit=100`

---

### 5.4 Page Matching (`/matching`)

**Modifications**:
1. Ajouter `ProgressStepper` pour le processus de matching
2. Ajouter alertes visuelles pour variations prix significatives
3. Améliorer feedback pendant calculs longs
4. Table résultats avec `InfiniteScrollTable`

---

### 5.5 Page Validation (`/validation`)

**Modifications**:
1. Badge visuel pour `auto_validated`
2. Filtres par statut de validation
3. Actions bulk avec confirmation
4. `InfiniteScrollTable` pour historique

---

## 6. DESIGN TOKENS

### 6.1 Couleurs sémantiques (à définir dans tailwind.config.js)

```javascript
colors: {
  score: {
    excellent: '#22c55e',  // green-500
    good: '#3b82f6',       // blue-500
    medium: '#eab308',     // yellow-500
    low: '#ef4444',        // red-500
  },
  status: {
    pending: '#6b7280',    // gray-500
    inProgress: '#3b82f6', // blue-500
    completed: '#22c55e',  // green-500
    error: '#ef4444',      // red-500
  }
}
```

---

## 7. ANIMATIONS ET TRANSITIONS

### 7.1 Transitions standard

```css
/* Transition par défaut pour tous les éléments interactifs */
.transition-default {
  @apply transition-all duration-200 ease-in-out;
}

/* Skeleton loading pulse */
.skeleton-pulse {
  @apply animate-pulse bg-gray-200 dark:bg-gray-700;
}

/* Fade in pour les données chargées */
.fade-in {
  @apply animate-in fade-in duration-300;
}
```

---

## 8. ACCESSIBILITÉ (a11y)

### 8.1 Règles obligatoires

- [ ] Navigation clavier complète dans les tables (Tab, Enter, Arrow keys)
- [ ] ARIA labels sur tous les éléments interactifs
- [ ] Focus visible sur tous les éléments focusables
- [ ] Contraste minimum 4.5:1 pour le texte
- [ ] Annonces screen reader pour les chargements

### 8.2 Composants accessibles

```typescript
// Exemple: VirtualizedTable avec a11y
<table role="grid" aria-label="Liste des catalogues" aria-rowcount={totalCount}>
  <tbody role="rowgroup">
    {virtualRows.map(row => (
      <tr
        key={row.id}
        role="row"
        tabIndex={0}
        aria-rowindex={row.index + 1}
        onKeyDown={handleKeyNavigation}
      >
        ...
      </tr>
    ))}
  </tbody>
</table>
```

---

## 9. TESTS E2E (Playwright)

### 9.1 Scénarios critiques à tester

```typescript
// tests/e2e/tables.spec.ts

test.describe('Tables avec virtualization', () => {
  test('Catalogue - scroll infini charge plus de données', async ({ page }) => {
    await page.goto('/catalogues')
    // Vérifier chargement initial
    await expect(page.getByRole('row')).toHaveCount.greaterThan(10)
    // Scroll vers le bas
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    // Vérifier que plus de données sont chargées
    await expect(page.getByText('Chargement...')).toBeVisible()
    await expect(page.getByRole('row')).toHaveCount.greaterThan(100)
  })

  test('Répertoire - virtualization avec 200k lignes', async ({ page }) => {
    await page.goto('/repertoire')
    // Performance: le rendu doit être < 1s
    const startTime = Date.now()
    await expect(page.getByRole('table')).toBeVisible()
    expect(Date.now() - startTime).toBeLessThan(1000)
    // Scroll rapide ne doit pas faire lag
    for (let i = 0; i < 10; i++) {
      await page.mouse.wheel(0, 1000)
      await page.waitForTimeout(100)
    }
  })
})

test.describe('États de chargement', () => {
  test('Skeleton visible pendant le chargement', async ({ page }) => {
    await page.route('**/api/catalogues*', route =>
      route.fulfill({ status: 200, body: '[]', headers: { 'Content-Type': 'application/json' } })
    )
    await page.goto('/catalogues')
    await expect(page.locator('.skeleton-pulse')).toBeVisible()
  })
})
```

---

## 10. ORDRE D'IMPLÉMENTATION

### Phase 1 - Composants de base (Priorité CRITIQUE)
1. `SkeletonTable`
2. `VirtualizedTable`
3. `InfiniteScrollTable`
4. `EmptyState`

### Phase 2 - Hooks et utilitaires
1. `useInfinitePagination`
2. `useTableVirtualization`
3. `useDebounceSearch`

### Phase 3 - Intégration pages
1. RepertoireGenerique (plus critique - 200k lignes)
2. Catalogues
3. MesVentes
4. Matching
5. Validation

### Phase 4 - Polish UX
1. `FilterBar`
2. `ProgressStepper`
3. `ScoreBadge`
4. `GroupeDrawer` amélioré
5. Design tokens et animations
6. Tests E2E complets

---

## 11. MÉTRIQUES DE SUCCÈS

| Métrique | Avant | Objectif |
|----------|-------|----------|
| Temps de rendu initial (200k lignes) | >5s | <1s |
| Mémoire utilisée (200k lignes) | >500MB | <100MB |
| FPS pendant scroll | <30 | >55 |
| Lighthouse Performance | ~60 | >85 |
| Lighthouse Accessibility | ~70 | >95 |

---

## 12. DÉPENDANCES AVEC BACKEND

Ce plan frontend dépend des endpoints paginés définis dans `ARCHITECTURE_FUTURE.md`:

| Endpoint | Section ARCHITECTURE_FUTURE.md |
|----------|-------------------------------|
| `GET /api/catalogues?cursor=&limit=` | Section API Pagination |
| `GET /api/ventes?cursor=&limit=` | Section API Pagination |
| `GET /api/repertoire?cursor=&limit=` | Section API Pagination |
| `GET /api/groupes?cursor=&limit=` | Section API Pagination |

**Important**: Le backend doit implémenter la pagination cursor-based AVANT l'intégration frontend.

---

**Dernière mise à jour**: 2025-01-XX
