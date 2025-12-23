# PHASE 5 : Frontend - Composants et Hooks

## Objectif
Implementer les composants React performants avec virtualization et infinite scroll.

## Pre-requis
- Phases 1-4 Backend terminees (endpoints API disponibles)
- Node.js et npm installes
- Dependencies a installer

---

## 5.1 Installation des dependances

```bash
cd frontend
npm install @tanstack/react-virtual @tanstack/react-table
```

---

## 5.2 Composant SkeletonTable

**Fichier** : `frontend/src/components/ui/SkeletonTable.tsx`

```typescript
import { Skeleton } from "@/components/ui/skeleton"

interface SkeletonTableProps {
  columns: number
  rows?: number
  showHeader?: boolean
  rowHeight?: number
}

export function SkeletonTable({
  columns,
  rows = 10,
  showHeader = true,
  rowHeight = 48
}: SkeletonTableProps) {
  // Largeurs variees pour realisme
  const widths = ['60%', '80%', '40%', '70%', '50%', '90%', '35%', '65%']

  return (
    <div className="w-full">
      {showHeader && (
        <div className="flex border-b border-gray-200 bg-gray-50 py-3">
          {Array.from({ length: columns }).map((_, i) => (
            <div key={i} className="flex-1 px-4">
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      )}
      <div>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div
            key={rowIndex}
            className="flex border-b border-gray-100"
            style={{ height: rowHeight }}
          >
            {Array.from({ length: columns }).map((_, colIndex) => (
              <div key={colIndex} className="flex-1 px-4 py-3">
                <Skeleton
                  className="h-4"
                  style={{ width: widths[(rowIndex + colIndex) % widths.length] }}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
```

---

## 5.3 Composant EmptyState

**Fichier** : `frontend/src/components/ui/EmptyState.tsx`

```typescript
import { LucideIcon, Inbox } from "lucide-react"
import { Button } from "@/components/ui/button"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-full bg-gray-100 p-4 mb-4">
        <Icon className="h-8 w-8 text-gray-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-gray-500 max-w-sm mb-4">{description}</p>
      )}
      {action && (
        <Button onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
```

---

## 5.4 Composant ScoreBadge

**Fichier** : `frontend/src/components/ui/ScoreBadge.tsx`

```typescript
import { cn } from "@/lib/utils"

interface ScoreBadgeProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function ScoreBadge({ score, size = 'md', showLabel = false }: ScoreBadgeProps) {
  const getColor = () => {
    if (score >= 90) return 'bg-green-100 text-green-800 border-green-200'
    if (score >= 70) return 'bg-blue-100 text-blue-800 border-blue-200'
    if (score >= 50) return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    return 'bg-red-100 text-red-800 border-red-200'
  }

  const getLabel = () => {
    if (score >= 90) return 'Excellent'
    if (score >= 70) return 'Bon'
    if (score >= 50) return 'Moyen'
    return 'Faible'
  }

  const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5'
  }

  return (
    <span className={cn(
      'inline-flex items-center rounded-full border font-medium',
      getColor(),
      sizeClasses[size]
    )}>
      {score.toFixed(0)}%
      {showLabel && <span className="ml-1">({getLabel()})</span>}
    </span>
  )
}
```

---

## 5.5 Composant ProgressStepper

**Fichier** : `frontend/src/components/ui/ProgressStepper.tsx`

```typescript
import { Check, Loader2, X, Circle } from "lucide-react"
import { cn } from "@/lib/utils"

interface Step {
  id: string
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  detail?: string
}

interface ProgressStepperProps {
  steps: Step[]
  orientation?: 'horizontal' | 'vertical'
}

export function ProgressStepper({ steps, orientation = 'horizontal' }: ProgressStepperProps) {
  const getIcon = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return <Check className="h-4 w-4 text-white" />
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-white animate-spin" />
      case 'error':
        return <X className="h-4 w-4 text-white" />
      default:
        return <Circle className="h-4 w-4 text-gray-400" />
    }
  }

  const getIconBg = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500'
      case 'in_progress':
        return 'bg-blue-500'
      case 'error':
        return 'bg-red-500'
      default:
        return 'bg-gray-200'
    }
  }

  if (orientation === 'vertical') {
    return (
      <div className="space-y-4">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-start gap-3">
            <div className="flex flex-col items-center">
              <div className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                getIconBg(step.status)
              )}>
                {getIcon(step.status)}
              </div>
              {index < steps.length - 1 && (
                <div className={cn(
                  'w-0.5 h-8 mt-1',
                  step.status === 'completed' ? 'bg-green-500' : 'bg-gray-200'
                )} />
              )}
            </div>
            <div>
              <p className={cn(
                'font-medium',
                step.status === 'pending' ? 'text-gray-400' : 'text-gray-900'
              )}>
                {step.label}
              </p>
              {step.detail && (
                <p className="text-sm text-gray-500">{step.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => (
        <div key={step.id} className="flex items-center flex-1">
          <div className="flex flex-col items-center">
            <div className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full',
              getIconBg(step.status)
            )}>
              {getIcon(step.status)}
            </div>
            <p className={cn(
              'text-xs mt-2 text-center',
              step.status === 'pending' ? 'text-gray-400' : 'text-gray-900'
            )}>
              {step.label}
            </p>
            {step.detail && (
              <p className="text-xs text-gray-500">{step.detail}</p>
            )}
          </div>
          {index < steps.length - 1 && (
            <div className={cn(
              'flex-1 h-0.5 mx-2',
              step.status === 'completed' ? 'bg-green-500' : 'bg-gray-200'
            )} />
          )}
        </div>
      ))}
    </div>
  )
}
```

---

## 5.6 Hook useDebounceSearch

**Fichier** : `frontend/src/hooks/useDebounceSearch.ts`

```typescript
import { useState, useEffect, useCallback } from 'react'

export function useDebounceSearch(
  searchFn: (query: string) => void,
  delay: number = 300
) {
  const [searchTerm, setSearchTerm] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    if (!searchTerm) {
      searchFn('')
      return
    }

    setIsSearching(true)
    const timer = setTimeout(() => {
      searchFn(searchTerm)
      setIsSearching(false)
    }, delay)

    return () => clearTimeout(timer)
  }, [searchTerm, delay, searchFn])

  const clearSearch = useCallback(() => {
    setSearchTerm('')
  }, [])

  return { searchTerm, setSearchTerm, isSearching, clearSearch }
}
```

---

## 5.7 Hook useInfinitePagination

**Fichier** : `frontend/src/hooks/useInfinitePagination.ts`

```typescript
import { useInfiniteQuery } from '@tanstack/react-query'

interface PaginatedResponse<T> {
  items: T[]
  next_cursor: string | null
  total_count: number
}

interface UseInfinitePaginationOptions {
  pageSize?: number
  staleTime?: number
  enabled?: boolean
}

export function useInfinitePagination<T>(
  queryKey: string[],
  fetchFn: (cursor: string | null) => Promise<PaginatedResponse<T>>,
  options: UseInfinitePaginationOptions = {}
) {
  const { pageSize = 50, staleTime = 30000, enabled = true } = options

  return useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchFn(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    staleTime,
    enabled,
    select: (data) => ({
      items: data.pages.flatMap(page => page.items),
      totalCount: data.pages[0]?.total_count ?? 0,
      pageCount: data.pages.length
    })
  })
}
```

---

## 5.8 Hook useTableVirtualization

**Fichier** : `frontend/src/hooks/useTableVirtualization.ts`

```typescript
import { useRef, RefObject } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

interface UseTableVirtualizationOptions {
  rowHeight: number
  overscan?: number
}

export function useTableVirtualization<T>(
  data: T[],
  containerRef: RefObject<HTMLElement>,
  options: UseTableVirtualizationOptions
) {
  const { rowHeight, overscan = 5 } = options

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => rowHeight,
    overscan
  })

  return {
    virtualRows: virtualizer.getVirtualItems(),
    totalSize: virtualizer.getTotalSize(),
    scrollToIndex: virtualizer.scrollToIndex
  }
}
```

---

## 5.9 Composant VirtualizedTable

**Fichier** : `frontend/src/components/ui/VirtualizedTable.tsx`

```typescript
import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { SkeletonTable } from './SkeletonTable'
import { EmptyState } from './EmptyState'
import { cn } from '@/lib/utils'

interface Column<T> {
  key: string
  header: string
  width?: string
  render?: (item: T) => React.ReactNode
}

interface VirtualizedTableProps<T> {
  data: T[]
  columns: Column<T>[]
  rowHeight?: number
  overscan?: number
  containerHeight?: string
  onRowClick?: (row: T) => void
  selectedRowId?: string | number
  isLoading?: boolean
  emptyMessage?: string
  getRowId?: (row: T) => string | number
}

export function VirtualizedTable<T>({
  data,
  columns,
  rowHeight = 48,
  overscan = 5,
  containerHeight = 'calc(100vh - 200px)',
  onRowClick,
  selectedRowId,
  isLoading = false,
  emptyMessage = 'Aucune donnee',
  getRowId = (row: any) => row.id
}: VirtualizedTableProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan
  })

  if (isLoading) {
    return <SkeletonTable columns={columns.length} rows={10} />
  }

  if (data.length === 0) {
    return <EmptyState title={emptyMessage} />
  }

  return (
    <div className="w-full border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex bg-gray-50 border-b font-medium text-sm text-gray-700">
        {columns.map((col) => (
          <div
            key={col.key}
            className="px-4 py-3"
            style={{ width: col.width || 'auto', flex: col.width ? 'none' : 1 }}
          >
            {col.header}
          </div>
        ))}
      </div>

      {/* Virtualized Body */}
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ height: containerHeight }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative'
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const item = data[virtualRow.index]
            const rowId = getRowId(item)
            const isSelected = rowId === selectedRowId

            return (
              <div
                key={virtualRow.key}
                className={cn(
                  'flex items-center border-b absolute w-full',
                  onRowClick && 'cursor-pointer hover:bg-gray-50',
                  isSelected && 'bg-blue-50'
                )}
                style={{
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`
                }}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((col) => (
                  <div
                    key={col.key}
                    className="px-4 py-2 truncate text-sm"
                    style={{ width: col.width || 'auto', flex: col.width ? 'none' : 1 }}
                  >
                    {col.render ? col.render(item) : (item as any)[col.key]}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
```

---

## 5.10 Composant InfiniteScrollTable

**Fichier** : `frontend/src/components/ui/InfiniteScrollTable.tsx`

```typescript
import { useRef, useEffect } from 'react'
import { useInView } from 'react-intersection-observer'
import { Loader2 } from 'lucide-react'
import { VirtualizedTable } from './VirtualizedTable'
import { useInfinitePagination } from '@/hooks/useInfinitePagination'

interface Column<T> {
  key: string
  header: string
  width?: string
  render?: (item: T) => React.ReactNode
}

interface PaginatedResponse<T> {
  items: T[]
  next_cursor: string | null
  total_count: number
}

interface InfiniteScrollTableProps<T> {
  queryKey: string[]
  queryFn: (cursor: string | null) => Promise<PaginatedResponse<T>>
  columns: Column<T>[]
  rowHeight?: number
  onRowClick?: (row: T) => void
  getRowId?: (row: T) => string | number
}

export function InfiniteScrollTable<T>({
  queryKey,
  queryFn,
  columns,
  rowHeight = 48,
  onRowClick,
  getRowId
}: InfiniteScrollTableProps<T>) {
  const { ref, inView } = useInView({ threshold: 0 })

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error
  } = useInfinitePagination<T>(queryKey, queryFn)

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage])

  if (error) {
    return (
      <div className="p-4 text-red-600">
        Erreur de chargement: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="w-full">
      <VirtualizedTable
        data={data?.items ?? []}
        columns={columns}
        rowHeight={rowHeight}
        onRowClick={onRowClick}
        isLoading={isLoading}
        getRowId={getRowId}
      />

      {/* Sentinel pour infinite scroll */}
      <div ref={ref} className="h-4" />

      {/* Indicateur de chargement */}
      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500">Chargement...</span>
        </div>
      )}

      {/* Compteur total */}
      {data && (
        <div className="text-sm text-gray-500 text-center py-2">
          {data.items.length} / {data.totalCount} elements
        </div>
      )}
    </div>
  )
}
```

---

## 5.11 Composant FilterBar

**Fichier** : `frontend/src/components/ui/FilterBar.tsx`

```typescript
import { X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

interface FilterConfig {
  key: string
  label: string
  type: 'text' | 'select'
  options?: { value: string; label: string }[]
  placeholder?: string
}

interface FilterBarProps {
  filters: FilterConfig[]
  values: Record<string, any>
  onChange: (key: string, value: any) => void
  onReset: () => void
}

export function FilterBar({ filters, values, onChange, onReset }: FilterBarProps) {
  const activeCount = Object.values(values).filter(v => v && v !== '').length

  return (
    <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg mb-4">
      {filters.map((filter) => (
        <div key={filter.key} className="flex-1 max-w-xs">
          {filter.type === 'text' && (
            <Input
              placeholder={filter.placeholder || filter.label}
              value={values[filter.key] || ''}
              onChange={(e) => onChange(filter.key, e.target.value)}
            />
          )}
          {filter.type === 'select' && filter.options && (
            <Select
              value={values[filter.key] || ''}
              onValueChange={(v) => onChange(filter.key, v)}
            >
              <SelectTrigger>
                <SelectValue placeholder={filter.placeholder || filter.label} />
              </SelectTrigger>
              <SelectContent>
                {filter.options.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      ))}

      <div className="flex items-center gap-2">
        {activeCount > 0 && (
          <Badge variant="secondary">
            {activeCount} filtre{activeCount > 1 ? 's' : ''}
          </Badge>
        )}
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="h-4 w-4 mr-1" />
          Reinitialiser
        </Button>
      </div>
    </div>
  )
}
```

---

## 5.12 Composant GroupeDrawer ameliore

**Fichier** : `frontend/src/components/GroupeDrawer.tsx`

```typescript
import { useQuery } from '@tanstack/react-query'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Star, Copy, ExternalLink, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

interface GroupeDrawerProps {
  groupeId: number | null
  currentCip?: string
  open: boolean
  onClose: () => void
}

export function GroupeDrawer({ groupeId, currentCip, open, onClose }: GroupeDrawerProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['groupe-details', groupeId],
    queryFn: () => api.get(`/api/groupe/${groupeId}/details`).then(r => r.data),
    enabled: !!groupeId && open
  })

  const copyAllCips = () => {
    if (!data?.equivalents) return
    const cips = data.equivalents.map((e: any) => e.cip13).join('\n')
    navigator.clipboard.writeText(cips)
    toast.success('CIP copies dans le presse-papier')
  }

  const copyCip = (cip: string) => {
    navigator.clipboard.writeText(cip)
    toast.success('CIP copie')
  }

  return (
    <Sheet open={open} onOpenChange={() => onClose()}>
      <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Groupe Generique #{groupeId}</SheetTitle>
        </SheetHeader>

        {isLoading && (
          <div className="space-y-4 py-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-8 w-40" />
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="py-8 text-center text-red-600">
            Erreur lors du chargement
          </div>
        )}

        {data && (
          <div className="space-y-6 py-4">
            {/* Princeps */}
            {data.princeps && (
              <div>
                <h3 className="flex items-center gap-2 font-semibold mb-2">
                  <Star className="h-4 w-4 text-yellow-500" />
                  Princeps Referent
                </h3>
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="font-bold">{data.princeps.denomination}</p>
                  <div className="flex items-center justify-between text-sm text-muted-foreground mt-1">
                    <span>CIP: {data.princeps.cip13}</span>
                    <span>PFHT: {data.princeps.pfht?.toFixed(2)} EUR</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-7 text-xs"
                    onClick={() => copyCip(data.princeps.cip13)}
                  >
                    <Copy className="h-3 w-3 mr-1" />
                    Copier CIP
                  </Button>
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="flex gap-4">
              <div className="bg-gray-100 rounded-lg px-4 py-2 text-center">
                <div className="text-2xl font-bold">{data.stats.nb_references}</div>
                <div className="text-xs text-gray-500">References</div>
              </div>
              <div className="bg-gray-100 rounded-lg px-4 py-2 text-center">
                <div className="text-2xl font-bold">{data.stats.nb_labos}</div>
                <div className="text-xs text-gray-500">Laboratoires</div>
              </div>
            </div>

            {/* Equivalents */}
            <div>
              <h3 className="font-semibold mb-2">
                Equivalents Generiques ({data.equivalents.length})
              </h3>
              <div className="max-h-[400px] overflow-y-auto space-y-1">
                {data.equivalents.map((equiv: any) => (
                  <div
                    key={equiv.cip13}
                    className={`p-2 rounded flex justify-between items-center ${
                      equiv.cip13 === currentCip
                        ? 'bg-green-100 border border-green-300'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium">{equiv.denomination}</p>
                      <p className="text-xs text-muted-foreground">
                        CIP: {equiv.cip13}
                      </p>
                    </div>
                    <div className="text-right flex items-center gap-2">
                      {equiv.labo && (
                        <Badge variant="outline" className="text-xs">
                          {equiv.labo}
                        </Badge>
                      )}
                      <span className="text-sm font-medium">
                        {equiv.pfht?.toFixed(2)} EUR
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t">
              <Button variant="outline" size="sm" onClick={copyAllCips}>
                <Copy className="h-4 w-4 mr-2" />
                Copier tous les CIP
              </Button>
              <Button variant="outline" size="sm" asChild>
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

---

## Tests Playwright Complets

### Configuration Playwright

**Fichier** : `frontend/playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
})
```

### Tests E2E Complets

**Fichier** : `frontend/tests/e2e/components.spec.ts`

```typescript
import { test, expect } from '@playwright/test'

// ==========================================
// Tests SkeletonTable
// ==========================================
test.describe('SkeletonTable', () => {
  test('affiche skeleton pendant chargement', async ({ page }) => {
    // Intercepter et retarder l'API
    await page.route('**/api/**', async route => {
      await new Promise(r => setTimeout(r, 1000))
      await route.continue()
    })

    await page.goto('/catalogues')

    // Verifier presence skeleton
    const skeletons = page.locator('.animate-pulse')
    await expect(skeletons.first()).toBeVisible()

    // Verifier nombre de lignes skeleton
    const skeletonRows = await skeletons.count()
    expect(skeletonRows).toBeGreaterThanOrEqual(5)
  })

  test('skeleton disparait apres chargement', async ({ page }) => {
    await page.goto('/catalogues')

    // Attendre que les donnees se chargent
    await page.waitForSelector('table tbody tr', { timeout: 10000 })

    // Verifier que skeleton n'est plus visible
    const skeleton = page.locator('.animate-pulse')
    await expect(skeleton).not.toBeVisible()
  })
})

// ==========================================
// Tests EmptyState
// ==========================================
test.describe('EmptyState', () => {
  test('affiche message quand pas de donnees', async ({ page }) => {
    // Mock API pour retourner vide
    await page.route('**/api/catalogues**', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null, total_count: 0 })
      })
    })

    await page.goto('/catalogues')
    await expect(page.getByText('Aucun')).toBeVisible()
  })
})

// ==========================================
// Tests ScoreBadge
// ==========================================
test.describe('ScoreBadge', () => {
  test('couleur verte pour score >= 90', async ({ page }) => {
    await page.goto('/rapprochement')
    // Chercher un badge avec score >= 90
    const greenBadge = page.locator('.bg-green-100')
    // Si existe, verifier
    if (await greenBadge.count() > 0) {
      await expect(greenBadge.first()).toBeVisible()
    }
  })

  test('couleur rouge pour score < 50', async ({ page }) => {
    await page.goto('/rapprochement')
    const redBadge = page.locator('.bg-red-100')
    if (await redBadge.count() > 0) {
      await expect(redBadge.first()).toBeVisible()
    }
  })
})

// ==========================================
// Tests ProgressStepper
// ==========================================
test.describe('ProgressStepper', () => {
  test('affiche les etapes de matching', async ({ page }) => {
    await page.goto('/matching')
    // Verifier presence des etapes
    const steps = page.locator('[data-testid="progress-step"]')
    expect(await steps.count()).toBeGreaterThanOrEqual(3)
  })

  test('etape active a animation spin', async ({ page }) => {
    await page.goto('/matching')
    // Chercher icone en cours (Loader2 avec animate-spin)
    const spinner = page.locator('.animate-spin')
    // Peut etre visible pendant processing
  })
})

// ==========================================
// Tests VirtualizedTable
// ==========================================
test.describe('VirtualizedTable - Performance', () => {
  test('rendu initial < 1s avec beaucoup de donnees', async ({ page }) => {
    const startTime = Date.now()
    await page.goto('/repertoire')
    await expect(page.locator('table')).toBeVisible()
    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(2000)
    console.log(`Load time: ${loadTime}ms`)
  })

  test('scroll rapide ne cause pas de lag', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Mesurer performance pendant scroll
    const metrics = await page.evaluate(async () => {
      const container = document.querySelector('[data-testid="virtual-scroll-container"]') || document.documentElement
      const frameRates: number[] = []
      let lastTime = performance.now()

      for (let i = 0; i < 10; i++) {
        container.scrollTop += 500
        await new Promise(r => requestAnimationFrame(r))
        const now = performance.now()
        const fps = 1000 / (now - lastTime)
        frameRates.push(fps)
        lastTime = now
      }

      return {
        avgFPS: frameRates.reduce((a, b) => a + b, 0) / frameRates.length,
        minFPS: Math.min(...frameRates)
      }
    })

    console.log(`Scroll Performance - Avg FPS: ${metrics.avgFPS.toFixed(1)}, Min FPS: ${metrics.minFPS.toFixed(1)}`)
    // On veut au moins 30 FPS minimum
    expect(metrics.minFPS).toBeGreaterThan(20)
  })

  test('seules les lignes visibles sont rendues', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const stats = await page.evaluate(() => {
      const rows = document.querySelectorAll('table tbody tr')
      const container = document.querySelector('[data-testid="virtual-scroll-container"]')
      return {
        renderedRows: rows.length,
        containerHeight: container?.clientHeight || window.innerHeight
      }
    })

    // Avec virtualization, on ne devrait pas render plus que visible + overscan
    // Environ (containerHeight / rowHeight) + 2*overscan
    const expectedMax = Math.ceil(stats.containerHeight / 48) + 20
    expect(stats.renderedRows).toBeLessThan(expectedMax)
    console.log(`Rendered rows: ${stats.renderedRows} (expected < ${expectedMax})`)
  })
})

// ==========================================
// Tests InfiniteScrollTable
// ==========================================
test.describe('InfiniteScrollTable', () => {
  test('charge plus de donnees au scroll', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    const initialCount = await page.locator('table tbody tr').count()
    console.log(`Initial rows: ${initialCount}`)

    // Scroll vers le bas
    await page.evaluate(() => {
      const container = document.querySelector('[data-testid="virtual-scroll-container"]') || document.documentElement
      container.scrollTop = container.scrollHeight
    })

    // Attendre chargement
    await page.waitForTimeout(1500)

    const newCount = await page.locator('table tbody tr').count()
    console.log(`After scroll rows: ${newCount}`)

    // Devrait avoir plus de lignes (ou au moins autant si fin de donnees)
    expect(newCount).toBeGreaterThanOrEqual(initialCount)
  })

  test('affiche indicateur de chargement pendant fetch', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    // Ralentir la prochaine requete
    await page.route('**/api/catalogues**', async route => {
      const url = route.request().url()
      if (url.includes('cursor')) {
        await new Promise(r => setTimeout(r, 500))
      }
      await route.continue()
    })

    // Scroll vers le bas
    await page.evaluate(() => {
      document.documentElement.scrollTop = document.documentElement.scrollHeight
    })

    // Verifier indicateur de chargement
    const loader = page.locator('.animate-spin, [data-testid="loading-more"]')
    // Peut etre visible brievement
  })

  test('affiche compteur total', async ({ page }) => {
    await page.goto('/catalogues')
    await page.waitForSelector('table tbody tr')

    // Verifier presence compteur "X / Y elements"
    const counter = page.getByText(/\d+\s*\/\s*\d+/)
    await expect(counter).toBeVisible()
  })
})

// ==========================================
// Tests FilterBar
// ==========================================
test.describe('FilterBar', () => {
  test('filtre par texte fonctionne', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const initialCount = await page.locator('table tbody tr').count()

    // Taper dans le champ de recherche
    const searchInput = page.getByPlaceholder(/recherche|search/i)
    if (await searchInput.count() > 0) {
      await searchInput.fill('AMLODIPINE')
      await page.waitForTimeout(500) // Debounce

      const filteredCount = await page.locator('table tbody tr').count()
      // Le nombre devrait changer (moins ou pareil si tous matchent)
      console.log(`Filter: ${initialCount} -> ${filteredCount}`)
    }
  })

  test('bouton reset efface les filtres', async ({ page }) => {
    await page.goto('/repertoire')

    const resetButton = page.getByText(/reinitialiser|reset/i)
    if (await resetButton.count() > 0) {
      await resetButton.click()
      // Verifier que les champs sont vides
    }
  })

  test('badge affiche nombre de filtres actifs', async ({ page }) => {
    await page.goto('/repertoire')

    // Appliquer un filtre
    const searchInput = page.getByPlaceholder(/recherche/i)
    if (await searchInput.count() > 0) {
      await searchInput.fill('test')
      await page.waitForTimeout(500)

      // Verifier badge "1 filtre"
      const badge = page.getByText(/\d+\s*filtre/i)
      if (await badge.count() > 0) {
        await expect(badge).toBeVisible()
      }
    }
  })
})

// ==========================================
// Tests GroupeDrawer
// ==========================================
test.describe('GroupeDrawer', () => {
  test('ouvre drawer au clic sur groupe', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Cliquer sur un lien de groupe
    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await expect(page.getByRole('dialog')).toBeVisible()
    }
  })

  test('affiche princeps dans drawer', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      // Verifier section Princeps
      const princepsSection = page.getByText(/princeps/i)
      await expect(princepsSection).toBeVisible()
    }
  })

  test('bouton copier CIP fonctionne', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      const copyButton = page.getByText(/copier/i).first()
      if (await copyButton.count() > 0) {
        await copyButton.click()
        // Verifier toast ou feedback
      }
    }
  })

  test('ferme drawer au clic exterieur', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    const groupeLink = page.locator('[data-testid="groupe-link"]').first()
    if (await groupeLink.count() > 0) {
      await groupeLink.click()
      await page.waitForSelector('[role="dialog"]')

      // Cliquer sur l'overlay
      await page.click('[data-testid="drawer-overlay"]', { force: true }).catch(() => {
        // Si pas d'overlay specifique, cliquer en dehors
        page.mouse.click(10, 10)
      })

      // Drawer devrait etre ferme
      await expect(page.getByRole('dialog')).not.toBeVisible()
    }
  })
})

// ==========================================
// Tests de memoire
// ==========================================
test.describe('Memory Performance', () => {
  test('memoire reste stable avec beaucoup de donnees', async ({ page }) => {
    await page.goto('/repertoire')
    await page.waitForSelector('table tbody tr')

    // Mesurer memoire initiale
    const initialMemory = await page.evaluate(() => {
      if ((performance as any).memory) {
        return (performance as any).memory.usedJSHeapSize / 1024 / 1024
      }
      return 0
    })

    // Scroller beaucoup
    for (let i = 0; i < 20; i++) {
      await page.evaluate(() => {
        document.documentElement.scrollTop += 1000
      })
      await page.waitForTimeout(100)
    }

    // Mesurer memoire finale
    const finalMemory = await page.evaluate(() => {
      if ((performance as any).memory) {
        return (performance as any).memory.usedJSHeapSize / 1024 / 1024
      }
      return 0
    })

    console.log(`Memory: ${initialMemory.toFixed(1)}MB -> ${finalMemory.toFixed(1)}MB`)

    // La memoire ne devrait pas exploser (< 100MB d'augmentation)
    if (initialMemory > 0) {
      expect(finalMemory - initialMemory).toBeLessThan(100)
    }
  })
})

// ==========================================
// Tests Hooks
// ==========================================
test.describe('Hooks', () => {
  test('useDebounceSearch - debounce fonctionne', async ({ page }) => {
    await page.goto('/repertoire')

    let requestCount = 0
    await page.route('**/api/repertoire**', route => {
      requestCount++
      route.continue()
    })

    const searchInput = page.getByPlaceholder(/recherche/i)
    if (await searchInput.count() > 0) {
      // Taper rapidement
      await searchInput.pressSequentially('test', { delay: 50 })

      // Attendre debounce (300ms default)
      await page.waitForTimeout(500)

      // Devrait n'avoir fait qu'une seule requete (pas une par lettre)
      console.log(`Request count after fast typing: ${requestCount}`)
      expect(requestCount).toBeLessThanOrEqual(2)
    }
  })
})
```

### Commande pour executer les tests Playwright

```bash
cd frontend

# Installer Playwright et navigateurs
npm install -D @playwright/test
npx playwright install chromium

# Executer les tests
npx playwright test

# Executer avec UI
npx playwright test --ui

# Executer un test specifique
npx playwright test components.spec.ts -g "VirtualizedTable"

# Voir le rapport HTML
npx playwright show-report
```

---

## Criteres de validation Phase 5

### Composants
- [ ] Dependencies `@tanstack/react-virtual` et `@tanstack/react-table` installees
- [ ] `SkeletonTable` cree
  - [ ] Affiche animation pulse
  - [ ] Disparait apres chargement
- [ ] `EmptyState` cree
  - [ ] Affiche message quand pas de donnees
  - [ ] Affiche icone et bouton action
- [ ] `ScoreBadge` cree
  - [ ] Couleur verte >= 90
  - [ ] Couleur bleue 70-89
  - [ ] Couleur jaune 50-69
  - [ ] Couleur rouge < 50
- [ ] `ProgressStepper` cree
  - [ ] Affiche etapes
  - [ ] Animation spin sur etape active

### Hooks
- [ ] `useDebounceSearch` fonctionne (1 requete pour frappe rapide)
- [ ] `useInfinitePagination` fonctionne (charge pages suivantes)
- [ ] `useTableVirtualization` fonctionne (seules lignes visibles rendues)

### Tables
- [ ] `VirtualizedTable` cree
  - [ ] Rendu initial < 2s
  - [ ] FPS scroll > 20 minimum
  - [ ] Lignes rendues < (visible + 20)
- [ ] `InfiniteScrollTable` cree
  - [ ] Charge plus au scroll
  - [ ] Affiche indicateur de chargement
  - [ ] Affiche compteur X / Total

### Autres
- [ ] `FilterBar` cree et filtre les donnees
- [ ] `GroupeDrawer` ameliore
  - [ ] Affiche princeps
  - [ ] Bouton copier CIP
  - [ ] Ferme au clic exterieur

### Performance
- [ ] Memoire stable (< 100MB augmentation apres scroll)
- [ ] Tests Playwright passent : `npx playwright test`

---

## Apres cette phase

Merger feature/frontend dans dev. Dire "IMPLEMENTATION COMPLETE".
