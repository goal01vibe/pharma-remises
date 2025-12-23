import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
} from '@tanstack/react-table'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Card } from '@/components/ui/card'
import {
  ArrowLeft,
  ArrowUpDown,
  Search,
  CheckCircle2,
  XCircle,
  Edit,
  Trash2,
} from 'lucide-react'
import {
  intelligentMatchingApi,
  type MatchingDetailItem,
} from '@/lib/api'

type FilterMode = 'all' | 'matched' | 'unmatched'

// Composant pour afficher du texte tronqué avec tooltip au hover
function TruncatedText({
  text,
  className = '',
  maxWidth = '250px'
}: {
  text: string | null | undefined
  className?: string
  maxWidth?: string
}) {
  const [showTooltip, setShowTooltip] = useState(false)
  const textRef = useRef<HTMLDivElement>(null)
  const [isOverflowing, setIsOverflowing] = useState(false)

  useEffect(() => {
    if (textRef.current) {
      setIsOverflowing(textRef.current.scrollWidth > textRef.current.clientWidth)
    }
  }, [text])

  if (!text) return <span className="text-muted-foreground">-</span>

  return (
    <div
      className="relative"
      onMouseEnter={() => isOverflowing && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div
        ref={textRef}
        className={`truncate ${className}`}
        style={{ maxWidth }}
      >
        {text}
      </div>
      {showTooltip && (
        <div className="absolute z-50 left-0 top-full mt-1 p-2 bg-popover border rounded-md shadow-lg text-sm max-w-[400px] whitespace-normal break-words">
          {text}
        </div>
      )}
    </div>
  )
}

export function MatchingDetails() {
  const { importId, laboId } = useParams<{ importId: string; laboId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // State
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

  // Scroll infini - charger 100 lignes a la fois
  const [visibleCount, setVisibleCount] = useState(100)
  const loaderRef = useRef<HTMLDivElement>(null)

  // Reset visibleCount quand tri/filtre change (pour performance)
  useEffect(() => {
    setVisibleCount(100)
  }, [sorting, globalFilter, filterMode])

  // IntersectionObserver pour scroll infini
  const loadMore = useCallback(() => {
    setVisibleCount((prev) => prev + 100)
  }, [])

  useEffect(() => {
    const currentLoader = loaderRef.current
    if (!currentLoader) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore()
        }
      },
      { threshold: 0.1, rootMargin: '100px' }
    )

    observer.observe(currentLoader)

    return () => observer.disconnect()
  }, [loadMore, visibleCount])  // Re-observer quand visibleCount change

  // Modal pour correction manuelle
  const [editingRow, setEditingRow] = useState<MatchingDetailItem | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Queries
  const { data: details, isLoading } = useQuery({
    queryKey: ['matching-details', importId, laboId],
    queryFn: () => intelligentMatchingApi.getDetails(parseInt(importId!), parseInt(laboId!)),
    enabled: !!importId && !!laboId,
  })

  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ['search-products', laboId, searchQuery],
    queryFn: () => intelligentMatchingApi.searchProducts(parseInt(laboId!), searchQuery),
    enabled: !!laboId && searchQuery.length >= 2,
  })

  // Mutations
  const setManualMatchMutation = useMutation({
    mutationFn: ({ venteId, produitId }: { venteId: number; produitId: number }) =>
      intelligentMatchingApi.setManualMatch(venteId, parseInt(laboId!), produitId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-details', importId, laboId] })
      queryClient.invalidateQueries({ queryKey: ['matching-stats', importId] })
      setEditingRow(null)
      setSearchQuery('')
    },
  })

  const deleteMatchMutation = useMutation({
    mutationFn: (venteId: number) =>
      intelligentMatchingApi.deleteMatch(venteId, parseInt(laboId!)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-details', importId, laboId] })
      queryClient.invalidateQueries({ queryKey: ['matching-stats', importId] })
    },
  })

  // Filtrer les donnees selon le mode
  const filteredData = useMemo(() => {
    if (!details?.details) return []
    switch (filterMode) {
      case 'matched':
        return details.details.filter((d) => d.matched)
      case 'unmatched':
        return details.details.filter((d) => !d.matched)
      default:
        return details.details
    }
  }, [details, filterMode])

  // Colonnes du tableau
  const columns = useMemo<ColumnDef<MatchingDetailItem>[]>(
    () => [
      {
        accessorKey: 'matched',
        header: 'Statut',
        size: 80,
        cell: ({ row }) => (
          row.original.matched ? (
            <Badge variant="default" className="bg-green-600">
              <CheckCircle2 className="w-3 h-3 mr-1" /> OK
            </Badge>
          ) : (
            <Badge variant="destructive">
              <XCircle className="w-3 h-3 mr-1" /> Non
            </Badge>
          )
        ),
      },
      {
        accessorKey: 'vente_designation',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="p-0 hover:bg-transparent"
          >
            Designation Vente
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => (
          <TruncatedText
            text={row.original.vente_designation}
            className="font-medium"
            maxWidth="280px"
          />
        ),
      },
      {
        accessorKey: 'vente_code_cip',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="p-0 hover:bg-transparent"
          >
            CIP Vente
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => (
          <div className="font-mono text-xs">
            {row.original.vente_code_cip || '-'}
          </div>
        ),
        filterFn: 'includesString',
      },
      {
        accessorKey: 'vente_quantite',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="p-0 hover:bg-transparent"
          >
            Qte
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        size: 60,
        cell: ({ row }) => (
          <div className="text-right">{row.original.vente_quantite ?? '-'}</div>
        ),
      },
      {
        accessorKey: 'produit_nom',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="p-0 hover:bg-transparent"
          >
            Produit Labo
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => (
          row.original.matched ? (
            <TruncatedText
              text={row.original.produit_nom}
              className="font-medium text-green-700"
              maxWidth="250px"
            />
          ) : (
            <span className="text-muted-foreground italic">Aucun match</span>
          )
        ),
      },
      {
        accessorKey: 'match_score',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="p-0 hover:bg-transparent"
          >
            Score
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        size: 70,
        cell: ({ row }) => (
          <div className="text-center">
            {row.original.match_score ? (
              <Badge
                variant={Number(row.original.match_score) >= 90 ? 'default' : Number(row.original.match_score) >= 70 ? 'secondary' : 'outline'}
              >
                {Number(row.original.match_score).toFixed(0)}%
              </Badge>
            ) : (
              '-'
            )}
          </div>
        ),
      },
      {
        accessorKey: 'match_type',
        header: 'Type',
        size: 120,
        cell: ({ row }) => (
          <div className="text-xs">
            {row.original.match_type ? (
              <Badge variant="outline">{row.original.match_type}</Badge>
            ) : (
              '-'
            )}
          </div>
        ),
      },
      {
        accessorKey: 'matched_on',
        header: 'Matched On',
        cell: ({ row }) => (
          <TruncatedText
            text={row.original.matched_on}
            className="text-xs text-muted-foreground"
            maxWidth="120px"
          />
        ),
      },
      {
        accessorKey: 'produit_libelle_groupe',
        header: 'Groupe Generique',
        cell: ({ row }) => (
          <TruncatedText
            text={row.original.produit_libelle_groupe}
            className="text-xs"
            maxWidth="180px"
          />
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
        size: 80,
        cell: ({ row }) => (
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditingRow(row.original)
                setSearchQuery(row.original.vente_designation?.split(' ').slice(0, 2).join(' ') || '')
              }}
              title="Modifier le matching"
            >
              <Edit className="h-4 w-4" />
            </Button>
            {row.original.matched && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (confirm('Supprimer ce matching ?')) {
                    deleteMatchMutation.mutate(row.original.vente_id)
                  }
                }}
                title="Supprimer le matching"
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </div>
        ),
      },
    ],
    [deleteMatchMutation]
  )

  const table = useReactTable({
    data: filteredData,
    columns,
    state: {
      sorting,
      columnFilters,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <Header title="Details du Matching" description="Chargement..." />
        <div className="p-6 text-center text-muted-foreground">Chargement...</div>
      </div>
    )
  }

  if (!details) {
    return (
      <div className="flex flex-col">
        <Header title="Details du Matching" description="Erreur" />
        <div className="p-6 text-center text-destructive">Donnees non trouvees</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        title={`Details Matching - ${details.labo_nom}`}
        description={`Import #${details.import_id} - ${details.total_ventes} ventes`}
      />

      <div className="flex-1 p-6 space-y-4 overflow-auto">
        {/* Stats en haut */}
        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Retour
          </Button>

          <div className="flex gap-4">
            <Card className="px-4 py-2">
              <div className="text-sm text-muted-foreground">Couverture</div>
              <div className="text-2xl font-bold text-primary">{details.couverture_pct}%</div>
            </Card>
            <Card
              className={`px-4 py-2 border-green-200 bg-green-50 cursor-pointer transition-all hover:shadow-md hover:scale-105 ${filterMode === 'matched' ? 'ring-2 ring-green-500' : ''}`}
              onClick={() => setFilterMode(filterMode === 'matched' ? 'all' : 'matched')}
            >
              <div className="text-sm text-green-700">Matches</div>
              <div className="text-2xl font-bold text-green-700">{details.matched_count}</div>
            </Card>
            <Card
              className={`px-4 py-2 border-red-200 bg-red-50 cursor-pointer transition-all hover:shadow-md hover:scale-105 ${filterMode === 'unmatched' ? 'ring-2 ring-red-500' : ''}`}
              onClick={() => setFilterMode(filterMode === 'unmatched' ? 'all' : 'unmatched')}
            >
              <div className="text-sm text-red-700">Non matches</div>
              <div className="text-2xl font-bold text-red-700">{details.unmatched_count}</div>
            </Card>
          </div>
        </div>

        {/* Filtres */}
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher dans toutes les colonnes (designation, CIP, etc.)..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-10"
            />
          </div>

          {filterMode !== 'all' && (
            <Button variant="outline" onClick={() => setFilterMode('all')}>
              Afficher tout ({details.total_ventes})
            </Button>
          )}
        </div>

        {/* Info filtre actif */}
        {filterMode !== 'all' && (
          <div className="text-sm text-muted-foreground">
            Filtre actif: <Badge variant={filterMode === 'matched' ? 'default' : 'destructive'}>
              {filterMode === 'matched' ? 'Matches uniquement' : 'Non matches uniquement'}
            </Badge>
          </div>
        )}

        {/* Tableau avec scroll infini */}
        <div className="border rounded-lg overflow-auto flex-1">
          <Table>
            <TableHeader className="sticky top-0 bg-background z-10">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id} style={{ width: header.getSize() }}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {(() => {
                const allRows = table.getRowModel().rows
                const visibleRows = allRows.slice(0, visibleCount)
                const hasMore = visibleCount < allRows.length

                if (!visibleRows.length) {
                  return (
                    <TableRow>
                      <TableCell colSpan={columns.length} className="h-24 text-center">
                        Aucun resultat.
                      </TableCell>
                    </TableRow>
                  )
                }

                return (
                  <>
                    {visibleRows.map((row) => (
                      <TableRow
                        key={row.id}
                        className={row.original.matched ? '' : 'bg-red-50/50'}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id}>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                    {hasMore && (
                      <TableRow>
                        <TableCell colSpan={columns.length} className="text-center py-4">
                          <div ref={loaderRef} className="flex flex-col items-center gap-2">
                            <span className="text-muted-foreground text-sm">
                              {visibleRows.length} / {allRows.length} lignes affichées
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={loadMore}
                            >
                              Charger 100 de plus
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                )
              })()}
            </TableBody>
          </Table>
        </div>

        {/* Info lignes */}
        <div className="text-sm text-muted-foreground">
          {Math.min(visibleCount, table.getRowModel().rows.length)} / {table.getFilteredRowModel().rows.length} ligne(s) affichee(s)
          {globalFilter && ` (filtre: "${globalFilter}")`}
        </div>
      </div>

      {/* Modal de correction manuelle */}
      <Dialog open={!!editingRow} onOpenChange={() => setEditingRow(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Correction manuelle du matching</DialogTitle>
            <DialogDescription>
              Recherchez et selectionnez le bon produit pour cette vente
            </DialogDescription>
          </DialogHeader>

          {editingRow && (
            <div className="space-y-4">
              {/* Vente concernee */}
              <Card className="p-4 bg-muted/50">
                <div className="text-sm text-muted-foreground">Vente a matcher:</div>
                <div className="font-medium">{editingRow.vente_designation}</div>
                {editingRow.vente_code_cip && (
                  <div className="text-sm font-mono">CIP: {editingRow.vente_code_cip}</div>
                )}
              </Card>

              {/* Recherche */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Rechercher un produit..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* Resultats */}
              <div className="max-h-[300px] overflow-auto border rounded-lg">
                {isSearching ? (
                  <div className="p-4 text-center text-muted-foreground">Recherche...</div>
                ) : searchResults?.results.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Produit</TableHead>
                        <TableHead>CIP</TableHead>
                        <TableHead>Groupe</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {searchResults.results.map((product) => (
                        <TableRow key={product.id}>
                          <TableCell className="font-medium">{product.nom_commercial}</TableCell>
                          <TableCell className="font-mono text-sm">{product.code_cip}</TableCell>
                          <TableCell className="text-xs max-w-[200px] truncate">
                            {product.libelle_groupe}
                          </TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              onClick={() =>
                                setManualMatchMutation.mutate({
                                  venteId: editingRow.vente_id,
                                  produitId: product.id,
                                })
                              }
                              disabled={setManualMatchMutation.isPending}
                            >
                              <CheckCircle2 className="h-4 w-4 mr-1" />
                              Selectionner
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : searchQuery.length >= 2 ? (
                  <div className="p-4 text-center text-muted-foreground">
                    Aucun produit trouve pour "{searchQuery}"
                  </div>
                ) : (
                  <div className="p-4 text-center text-muted-foreground">
                    Tapez au moins 2 caracteres pour rechercher
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
