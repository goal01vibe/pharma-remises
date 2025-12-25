import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Database,
  Search,
  RefreshCw,
  RotateCcw,
  FileSpreadsheet,
  GitCompare,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  AlertTriangle,
  Loader2,
  X,
} from 'lucide-react'

import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { repertoireApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { GroupeDrawer } from '@/components/GroupeDrawer'

// Types for BDPM status
interface BdpmFile {
  filename: string
  records_count: number | null
  last_downloaded: string | null
  new_records: number
  removed_records: number
}

interface BdpmStatus {
  status: 'ok' | 'warning' | 'outdated' | string
  message: string
  files: BdpmFile[]
}

// Type for sort configuration
type SortField = 'denomination' | 'cip13' | 'princeps_denomination' | 'pfht' | 'type_generique'
type SortOrder = 'asc' | 'desc'

export default function RepertoireGenerique() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<number | null>(null)
  const [priceFilter, setPriceFilter] = useState<boolean | null>(null)
  const [showBdpmDetail, setShowBdpmDetail] = useState(false)
  const [page, setPage] = useState(0)
  const [sortBy, setSortBy] = useState<SortField>('denomination')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()
  const limit = 50

  // Stats du repertoire
  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['repertoire-stats'],
    queryFn: () => repertoireApi.getStats(true),
  })

  // Liste du repertoire
  const { data: items, isLoading: loadingItems } = useQuery({
    queryKey: ['repertoire-list', search, typeFilter, priceFilter, page, sortBy, sortOrder],
    queryFn: () => repertoireApi.list({
      skip: page * limit,
      limit,
      search: search || undefined,
      type_generique: typeFilter ?? undefined,
      has_price: priceFilter ?? undefined,
      only_with_groupe: true,
      sort_by: sortBy,
      sort_order: sortOrder,
    }),
  })

  // Statut BDPM
  const { data: bdpmStatus } = useQuery({
    queryKey: ['bdpm-status'],
    queryFn: repertoireApi.getBdpmStatus,
  })

  // Mutation check BDPM
  const checkBdpmMutation = useMutation({
    mutationFn: (force: boolean) => repertoireApi.checkBdpmUpdates(force),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['bdpm-status'] })
      queryClient.invalidateQueries({ queryKey: ['repertoire-stats'] })
      queryClient.invalidateQueries({ queryKey: ['repertoire-list'] })
      if (data.force_reintegration) {
        alert(`BDPM re-integre:\n- ${data.new_cips} nouveaux CIP\n- ${data.updated_cips || 0} mis a jour\n- ${data.removed_cips} marques absents`)
      } else if (data.files_updated > 0) {
        alert(`BDPM mis a jour: ${data.new_cips} nouveaux CIP, ${data.removed_cips} absents`)
      } else {
        alert('BDPM deja a jour')
      }
    },
    onError: () => {
      alert('Erreur lors de la verification BDPM')
    },
  })

  const formatCurrency = (value: number | null) => {
    if (value === null) return '-'
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(value)
  }

  // Handler pour clic sur carte stats (type generique)
  const handleCardClick = (filter: number | null) => {
    setPriceFilter(null) // Reset price filter when clicking type
    setTypeFilter(filter === typeFilter ? null : filter)
    setPage(0)
  }

  // Handler pour clic sur carte prix
  const handlePriceCardClick = (hasPrice: boolean | null) => {
    setTypeFilter(null) // Reset type filter when clicking price
    setPriceFilter(hasPrice === priceFilter ? null : hasPrice)
    setPage(0)
  }

  // Handler pour tri des colonnes
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
    setPage(0)
  }

  // Composant pour header de colonne triable
  const SortableHeader = ({ field, children, className }: { field: SortField; children: React.ReactNode; className?: string }) => (
    <TableHead
      className={cn("cursor-pointer hover:bg-muted/50 select-none", className)}
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        {sortBy === field && (
          sortOrder === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
        )}
      </div>
    </TableHead>
  )

  return (
    <div className="flex flex-col">
      <Header title="Repertoire Generique" description="Base de donnees BDPM des generiques substituables" />
      <div className="flex-1 space-y-6 p-6">
        {/* Stats Cards - Cliquables pour filtrer */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <Card
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              typeFilter === null && priceFilter === null && "ring-2 ring-primary"
            )}
            onClick={() => { setTypeFilter(null); setPriceFilter(null); setPage(0); }}
          >
            <CardHeader className="pb-2">
              <CardDescription>Total CIP</CardDescription>
              <CardTitle className="text-2xl">
                {loadingStats ? '...' : stats?.total_cips.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Groupes</CardDescription>
              <CardTitle className="text-2xl">
                {loadingStats ? '...' : stats?.total_groupes.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              typeFilter === 0 && "ring-2 ring-blue-500"
            )}
            onClick={() => handleCardClick(0)}
          >
            <CardHeader className="pb-2">
              <CardDescription>Princeps</CardDescription>
              <CardTitle className="text-2xl text-blue-600">
                {loadingStats ? '...' : stats?.princeps.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              typeFilter === 1 && "ring-2 ring-green-500"
            )}
            onClick={() => handleCardClick(1)}
          >
            <CardHeader className="pb-2">
              <CardDescription>Generiques</CardDescription>
              <CardTitle className="text-2xl text-green-600">
                {loadingStats ? '...' : stats?.generiques.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              priceFilter === true && "ring-2 ring-emerald-500"
            )}
            onClick={() => handlePriceCardClick(true)}
          >
            <CardHeader className="pb-2">
              <CardDescription>Avec prix</CardDescription>
              <CardTitle className="text-2xl text-emerald-600">
                {loadingStats ? '...' : stats?.avec_prix.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              priceFilter === false && "ring-2 ring-orange-500"
            )}
            onClick={() => handlePriceCardClick(false)}
          >
            <CardHeader className="pb-2">
              <CardDescription>Sans prix</CardDescription>
              <CardTitle className="text-2xl text-orange-600">
                {loadingStats ? '...' : stats?.sans_prix.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-4 mb-6">
          <Button
            onClick={() => navigate('/repertoire/rapprochement')}
            className="gap-2"
          >
            <GitCompare className="h-4 w-4" />
            Rapprocher mes ventes
          </Button>

          <Button
            variant="outline"
            onClick={() => checkBdpmMutation.mutate(false)}
            disabled={checkBdpmMutation.isPending}
            className="gap-2"
          >
            {checkBdpmMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Verifier BDPM
          </Button>

          <Button
            variant="outline"
            onClick={() => {
              if (confirm('Forcer la re-integration de tous les CIP depuis les fichiers BDPM existants ?')) {
                checkBdpmMutation.mutate(true)
              }
            }}
            disabled={checkBdpmMutation.isPending}
            className="gap-2"
            title="Re-integre tous les CIP meme si les fichiers n'ont pas change"
          >
            {checkBdpmMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Forcer sync
          </Button>

          <Button variant="outline" className="gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Exporter Excel
          </Button>
        </div>

        {/* BDPM Status Detail */}
        {bdpmStatus && (
          <Collapsible open={showBdpmDetail} onOpenChange={setShowBdpmDetail} className="mb-6">
            <Card>
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Database className="h-5 w-5" />
                      <CardTitle className="text-lg">Statut BDPM</CardTitle>
                      <Badge variant={(bdpmStatus as BdpmStatus).status === 'ok' ? 'default' : 'secondary'}>
                        {(bdpmStatus as BdpmStatus).status === 'ok' ? (
                          <CheckCircle className="h-3 w-3 mr-1" />
                        ) : (
                          <AlertTriangle className="h-3 w-3 mr-1" />
                        )}
                        {(bdpmStatus as BdpmStatus).message}
                      </Badge>
                    </div>
                    <ChevronDown className={`h-5 w-5 transition-transform ${showBdpmDetail ? 'rotate-180' : ''}`} />
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {(bdpmStatus as BdpmStatus).files.map((file) => (
                      <div key={file.filename} className="p-3 border rounded-lg">
                        <p className="font-medium text-sm">{file.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {file.records_count?.toLocaleString() || 0} enregistrements
                        </p>
                        {file.last_downloaded && (
                          <p className="text-xs text-muted-foreground">
                            MaJ: {new Date(file.last_downloaded).toLocaleDateString('fr-FR')}
                          </p>
                        )}
                        {(file.new_records > 0 || file.removed_records > 0) && (
                          <p className="text-xs">
                            <span className="text-green-600">+{file.new_records}</span>
                            {' / '}
                            <span className="text-red-600">-{file.removed_records}</span>
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        )}

        {/* Search & Active Filter */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-wrap gap-4 items-center">
              <div className="relative flex-1 min-w-[300px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Rechercher par CIP, molecule ou nom..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value)
                    setPage(0)
                  }}
                  className="pl-10"
                />
              </div>
              {typeFilter !== null && (
                <Badge variant="secondary" className="gap-1 py-1.5">
                  Filtre: {typeFilter === 0 ? 'Princeps' : 'Generiques'}
                  <X
                    className="h-3 w-3 cursor-pointer"
                    onClick={() => setTypeFilter(null)}
                  />
                </Badge>
              )}
              {priceFilter !== null && (
                <Badge variant="secondary" className="gap-1 py-1.5">
                  Filtre: {priceFilter ? 'Avec prix' : 'Sans prix'}
                  <X
                    className="h-3 w-3 cursor-pointer"
                    onClick={() => setPriceFilter(null)}
                  />
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Table avec colonnes triables */}
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHeader field="cip13" className="w-[140px]">CIP13</SortableHeader>
                  <SortableHeader field="denomination">Designation</SortableHeader>
                  <SortableHeader field="princeps_denomination">Princeps</SortableHeader>
                  <SortableHeader field="type_generique" className="w-[100px]">Type</SortableHeader>
                  <SortableHeader field="pfht" className="text-right w-[100px]">Prix PFHT</SortableHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loadingItems ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    </TableCell>
                  </TableRow>
                ) : items?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      Aucun resultat
                    </TableCell>
                  </TableRow>
                ) : (
                  items?.map((item) => (
                    <TableRow
                      key={item.cip13}
                      className={item.groupe_generique_id ? "cursor-pointer hover:bg-muted/50" : ""}
                      onClick={() => {
                        if (item.groupe_generique_id) {
                          setSelectedGroupe(item.groupe_generique_id)
                          setSelectedCip(item.cip13)
                        }
                      }}
                    >
                      <TableCell className="font-mono text-sm">{item.cip13}</TableCell>
                      <TableCell className="max-w-md">
                        <div className="truncate" title={item.denomination || item.libelle_groupe || ''}>
                          {item.denomination || item.libelle_groupe || '-'}
                        </div>
                        {item.denomination && item.libelle_groupe && (
                          <div className="text-xs text-muted-foreground truncate">
                            {item.libelle_groupe}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="max-w-xs">
                        <div className="truncate text-blue-600" title={item.princeps_denomination || ''}>
                          {item.princeps_denomination || '-'}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.type_generique === 0 ? 'secondary' : 'default'}>
                          {item.type_generique === 0 ? 'Princeps' : 'Generique'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{formatCurrency(item.pfht)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
          {/* Pagination */}
          <div className="flex items-center justify-between p-4 border-t">
            <p className="text-sm text-muted-foreground">
              Page {page + 1} - {items?.length || 0} resultats
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                Precedent
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={(items?.length || 0) < limit}
              >
                Suivant
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Drawer details groupe */}
      <GroupeDrawer
        groupeId={selectedGroupe}
        currentCip={selectedCip}
        open={!!selectedGroupe}
        onClose={() => setSelectedGroupe(null)}
      />
    </div>
  )
}
