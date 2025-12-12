import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  getPaginationRowModel,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'
import {
  intelligentMatchingApi,
  type MatchingDetailItem,
} from '@/lib/api'

type FilterMode = 'all' | 'matched' | 'unmatched'

export function MatchingDetails() {
  const { importId, laboId } = useParams<{ importId: string; laboId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // State
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

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
        filterFn: (row, _id, value) => {
          if (value === 'all') return true
          return value === 'matched' ? row.original.matched : !row.original.matched
        },
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
          <div className="max-w-[250px]">
            <div className="font-medium truncate" title={row.original.vente_designation || ''}>
              {row.original.vente_designation || '-'}
            </div>
            {row.original.vente_code_cip && (
              <div className="text-xs text-muted-foreground font-mono">
                CIP: {row.original.vente_code_cip}
              </div>
            )}
          </div>
        ),
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
          <div className="max-w-[250px]">
            {row.original.matched ? (
              <>
                <div className="font-medium truncate text-green-700" title={row.original.produit_nom || ''}>
                  {row.original.produit_nom || '-'}
                </div>
                {row.original.produit_code_cip && (
                  <div className="text-xs text-muted-foreground font-mono">
                    CIP: {row.original.produit_code_cip}
                  </div>
                )}
              </>
            ) : (
              <span className="text-muted-foreground italic">Aucun match</span>
            )}
          </div>
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
        cell: ({ row }) => (
          <div className="text-center">
            {row.original.match_score ? (
              <Badge
                variant={row.original.match_score >= 90 ? 'default' : row.original.match_score >= 70 ? 'secondary' : 'outline'}
              >
                {row.original.match_score.toFixed(0)}%
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
          <div className="max-w-[150px] text-xs text-muted-foreground truncate" title={row.original.matched_on || ''}>
            {row.original.matched_on || '-'}
          </div>
        ),
      },
      {
        accessorKey: 'produit_libelle_groupe',
        header: 'Groupe Generique',
        cell: ({ row }) => (
          <div className="max-w-[200px] text-xs truncate" title={row.original.produit_libelle_groupe || ''}>
            {row.original.produit_libelle_groupe || '-'}
          </div>
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
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
    [deleteMatchMutation, laboId]
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
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 50,
      },
    },
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
            <Card className="px-4 py-2 border-green-200 bg-green-50">
              <div className="text-sm text-green-700">Matches</div>
              <div className="text-2xl font-bold text-green-700">{details.matched_count}</div>
            </Card>
            <Card className="px-4 py-2 border-red-200 bg-red-50">
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
              placeholder="Rechercher dans toutes les colonnes..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-10"
            />
          </div>

          <Select value={filterMode} onValueChange={(v) => setFilterMode(v as FilterMode)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous ({details.total_ventes})</SelectItem>
              <SelectItem value="matched">Matches ({details.matched_count})</SelectItem>
              <SelectItem value="unmatched">Non matches ({details.unmatched_count})</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Tableau */}
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length ? (
                table.getRowModel().rows.map((row) => (
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
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center">
                    Aucun resultat.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {table.getFilteredRowModel().rows.length} ligne(s) sur {details.total_ventes}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronsLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">
              Page {table.getState().pagination.pageIndex + 1} sur {table.getPageCount()}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
            >
              <ChevronsRight className="h-4 w-4" />
            </Button>
            <Select
              value={table.getState().pagination.pageSize.toString()}
              onValueChange={(v) => table.setPageSize(Number(v))}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[25, 50, 100, 200].map((size) => (
                  <SelectItem key={size} value={size.toString()}>
                    {size} lignes
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
