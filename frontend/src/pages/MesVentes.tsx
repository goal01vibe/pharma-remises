import { useState, useEffect, useMemo } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ShoppingCart, Upload, Trash2, FileX, AlertTriangle, RefreshCw, ArrowUpDown, ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ventesApi } from '@/lib/api'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { Link, useSearchParams } from 'react-router-dom'
import { GroupeDrawer } from '@/components/GroupeDrawer'

type SortField = 'code_cip_achete' | 'designation' | 'labo_actuel' | 'quantite_annuelle' | 'prix_bdpm' | 'montant'
type SortOrder = 'asc' | 'desc'

export function MesVentes() {
  const [searchParams, setSearchParams] = useSearchParams()
  const importIdParam = searchParams.get('import_id')
  const [selectedImportId, setSelectedImportId] = useState<string>(importIdParam || '')
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()

  // Tri et pagination
  const [sortField, setSortField] = useState<SortField>('designation')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 100

  const queryClient = useQueryClient()

  const { data: ventesImports = [] } = useQuery({
    queryKey: ['ventes-imports'],
    queryFn: ventesApi.getImports,
  })

  // Auto-selectionner le premier import si aucun n'est selectionne
  useEffect(() => {
    if (!selectedImportId && ventesImports.length > 0) {
      const firstImportId = ventesImports[0].id.toString()
      setSelectedImportId(firstImportId)
      setSearchParams({ import_id: firstImportId })
    }
  }, [ventesImports, selectedImportId, setSearchParams])

  // Ne charger les ventes QUE si un import est selectionne
  const { data: ventes = [], isLoading } = useQuery({
    queryKey: ['ventes', selectedImportId],
    queryFn: () => ventesApi.list(parseInt(selectedImportId)),
    enabled: !!selectedImportId, // Ne pas charger si pas d'import selectionne
  })

  const deleteVenteMutation = useMutation({
    mutationFn: ventesApi.deleteVente,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ventes'] })
    },
  })

  const deleteImportMutation = useMutation({
    mutationFn: ventesApi.deleteImport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ventes-imports'] })
      queryClient.invalidateQueries({ queryKey: ['ventes'] })
      queryClient.invalidateQueries({ queryKey: ['incomplete-count'] })
      // Selectionner le prochain import disponible
      setSelectedImportId('')
    },
  })

  // Query pour le comptage des ventes incompletes
  const { data: incompleteCount } = useQuery({
    queryKey: ['incomplete-count', selectedImportId],
    queryFn: () => ventesApi.getIncompleteCount(parseInt(selectedImportId)),
    enabled: !!selectedImportId,
  })

  // Mutation pour supprimer les ventes incompletes
  const deleteIncompleteMutation = useMutation({
    mutationFn: () => ventesApi.deleteIncomplete(parseInt(selectedImportId)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['ventes'] })
      queryClient.invalidateQueries({ queryKey: ['incomplete-count'] })
      alert(`${result.deleted} ventes incompletes supprimees`)
    },
  })

  // Mutation pour re-enrichir les ventes avec BDPM
  const reEnrichMutation = useMutation({
    mutationFn: () => ventesApi.reEnrich(parseInt(selectedImportId)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['ventes'] })
      queryClient.invalidateQueries({ queryKey: ['incomplete-count'] })
      alert(`Re-enrichissement termine: ${result.stats.enriched}/${result.stats.total} ventes enrichies`)
    },
  })

  const handleImportChange = (value: string) => {
    setSelectedImportId(value)
    setSearchParams({ import_id: value })
  }

  // Calculer le montant: utiliser montant_annuel si dispo, sinon prix_bdpm × quantité
  const getMontant = (v: typeof ventes[0]) => {
    if (v.montant_annuel) return v.montant_annuel
    if (v.prix_bdpm && v.quantite_annuelle) return v.prix_bdpm * v.quantite_annuelle
    return 0
  }
  const totalMontant = ventes.reduce((sum, v) => sum + getMontant(v), 0)
  const totalQuantite = ventes.reduce((sum, v) => sum + (v.quantite_annuelle || 0), 0)

  // Reset page when import changes
  useEffect(() => {
    setCurrentPage(1)
  }, [selectedImportId])

  // Tri et pagination des ventes
  const sortedAndPaginatedVentes = useMemo(() => {
    if (!ventes.length) return { data: [], totalPages: 0 }

    // Trier les ventes
    const sorted = [...ventes].sort((a, b) => {
      let aVal: string | number = ''
      let bVal: string | number = ''

      switch (sortField) {
        case 'code_cip_achete':
          aVal = a.code_cip_achete || ''
          bVal = b.code_cip_achete || ''
          break
        case 'designation':
          aVal = (a.designation || '').toLowerCase()
          bVal = (b.designation || '').toLowerCase()
          break
        case 'labo_actuel':
          aVal = (a.labo_actuel || '').toLowerCase()
          bVal = (b.labo_actuel || '').toLowerCase()
          break
        case 'quantite_annuelle':
          aVal = a.quantite_annuelle || 0
          bVal = b.quantite_annuelle || 0
          break
        case 'prix_bdpm':
          aVal = a.prix_bdpm || 0
          bVal = b.prix_bdpm || 0
          break
        case 'montant':
          aVal = getMontant(a)
          bVal = getMontant(b)
          break
      }

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1
      return 0
    })

    // Paginer
    const totalPages = Math.ceil(sorted.length / pageSize)
    const start = (currentPage - 1) * pageSize
    const data = sorted.slice(start, start + pageSize)

    return { data, totalPages }
  }, [ventes, sortField, sortOrder, currentPage, pageSize])

  // Gestion du clic sur une colonne pour trier
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Inverse l'ordre si meme colonne
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // Nouvelle colonne, ordre ascendant par defaut
      setSortField(field)
      setSortOrder('asc')
    }
    setCurrentPage(1) // Reset a la premiere page
  }

  // Composant pour l'icone de tri
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-4 w-4 ml-1 opacity-50" />
    }
    return sortOrder === 'asc'
      ? <ArrowUp className="h-4 w-4 ml-1" />
      : <ArrowDown className="h-4 w-4 ml-1" />
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Mes Ventes"
        description="Historique de vos achats annuels"
      />

      <div className="flex-1 space-y-6 p-6">
        <div className="flex justify-between items-start gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Select value={selectedImportId} onValueChange={handleImportChange}>
                <SelectTrigger className="w-[350px]">
                  <SelectValue placeholder="Selectionnez un fichier de ventes" />
                </SelectTrigger>
                <SelectContent>
                  {ventesImports.map((imp) => (
                    <SelectItem key={imp.id} value={imp.id.toString()}>
                      {imp.nom || imp.nom_fichier} ({imp.nb_lignes_importees} lignes)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedImportId && (
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    if (confirm('Supprimer ce fichier et toutes ses ventes ?')) {
                      deleteImportMutation.mutate(parseInt(selectedImportId))
                    }
                  }}
                  disabled={deleteImportMutation.isPending}
                  title="Supprimer ce fichier de ventes"
                >
                  <FileX className="h-4 w-4 text-destructive" />
                </Button>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {ventes.length} ligne{ventes.length > 1 ? 's' : ''} de vente
            </p>
            {ventes.length > 0 && (
              <p className="text-lg font-medium">
                Total: {formatCurrency(totalMontant)} ({formatNumber(totalQuantite)} unites)
              </p>
            )}

            {/* Indicateur ventes incompletes */}
            {incompleteCount && incompleteCount.incomplete > 0 && (
              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <span className="text-sm font-medium text-amber-800">
                    {incompleteCount.incomplete} vente{incompleteCount.incomplete > 1 ? 's' : ''} sans prix BDPM
                  </span>
                  <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300">
                    {incompleteCount.completion_rate}% complete
                  </Badge>
                </div>
                <Progress value={incompleteCount.completion_rate} className="h-2 mb-2" />
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => reEnrichMutation.mutate()}
                    disabled={reEnrichMutation.isPending}
                  >
                    <RefreshCw className={`h-3 w-3 mr-1 ${reEnrichMutation.isPending ? 'animate-spin' : ''}`} />
                    Re-enrichir BDPM
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-amber-700 border-amber-300 hover:bg-amber-100"
                    onClick={() => {
                      if (confirm(`Supprimer ${incompleteCount.incomplete} ventes sans prix BDPM ?`)) {
                        deleteIncompleteMutation.mutate()
                      }
                    }}
                    disabled={deleteIncompleteMutation.isPending}
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    Supprimer incompletes
                  </Button>
                </div>
              </div>
            )}
          </div>
          <Button asChild>
            <Link to="/import?type=ventes">
              <Upload className="mr-2 h-4 w-4" />
              Importer mes ventes
            </Link>
          </Button>
        </div>

        {ventesImports.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <ShoppingCart className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Aucun fichier de ventes importe</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Importez votre historique de ventes pour lancer des simulations
              </p>
              <Button className="mt-4" asChild>
                <Link to="/import?type=ventes">Importer mes ventes</Link>
              </Button>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            Chargement...
          </div>
        ) : ventes.length === 0 && selectedImportId ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <ShoppingCart className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Aucune vente dans ce fichier</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Ce fichier ne contient aucune ligne de vente
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Historique des ventes</CardTitle>
              <CardDescription>
                Vos achats annuels par produit
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('code_cip_achete')}
                    >
                      <div className="flex items-center">
                        Code CIP
                        <SortIcon field="code_cip_achete" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('designation')}
                    >
                      <div className="flex items-center">
                        Designation
                        <SortIcon field="designation" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('labo_actuel')}
                    >
                      <div className="flex items-center">
                        Labo Actuel
                        <SortIcon field="labo_actuel" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="text-right cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('quantite_annuelle')}
                    >
                      <div className="flex items-center justify-end">
                        Quantite
                        <SortIcon field="quantite_annuelle" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="text-right cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('prix_bdpm')}
                    >
                      <div className="flex items-center justify-end">
                        Prix BDPM
                        <SortIcon field="prix_bdpm" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="text-right cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('montant')}
                    >
                      <div className="flex items-center justify-end">
                        Montant Annuel
                        <SortIcon field="montant" />
                      </div>
                    </TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedAndPaginatedVentes.data.map((vente) => (
                    <TableRow
                      key={vente.id}
                      className={`${!vente.has_bdpm_price ? 'bg-amber-50/50' : ''} ${vente.groupe_generique_id ? 'cursor-pointer hover:bg-muted/50' : ''}`}
                      onClick={() => {
                        if (vente.groupe_generique_id) {
                          setSelectedGroupe(vente.groupe_generique_id)
                          setSelectedCip(vente.code_cip_achete || undefined)
                        }
                      }}
                    >
                      <TableCell className="font-mono text-sm">
                        {vente.code_cip_achete || '-'}
                      </TableCell>
                      <TableCell className="max-w-[300px]">
                        <div className="flex items-center gap-2">
                          <span className="truncate">{vente.designation || '-'}</span>
                          {!vente.has_bdpm_price && (
                            <Badge variant="outline" className="bg-amber-100 text-amber-700 text-xs shrink-0">
                              Sans BDPM
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{vente.labo_actuel || '-'}</TableCell>
                      <TableCell className="text-right">
                        {vente.quantite_annuelle ? formatNumber(vente.quantite_annuelle) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {vente.prix_bdpm ? (
                          formatCurrency(vente.prix_bdpm)
                        ) : (
                          <span className="text-amber-600">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {getMontant(vente) > 0 ? formatCurrency(getMontant(vente)) : '-'}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteVenteMutation.mutate(vente.id)
                          }}
                          disabled={deleteVenteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {/* Pagination */}
              {sortedAndPaginatedVentes.totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    Page {currentPage} sur {sortedAndPaginatedVentes.totalPages} ({ventes.length} resultats)
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(1)}
                      disabled={currentPage === 1}
                    >
                      Debut
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Precedent
                    </Button>
                    <div className="flex items-center gap-1">
                      {/* Afficher quelques numeros de page */}
                      {Array.from({ length: Math.min(5, sortedAndPaginatedVentes.totalPages) }, (_, i) => {
                        let pageNum: number
                        const totalPages = sortedAndPaginatedVentes.totalPages
                        if (totalPages <= 5) {
                          pageNum = i + 1
                        } else if (currentPage <= 3) {
                          pageNum = i + 1
                        } else if (currentPage >= totalPages - 2) {
                          pageNum = totalPages - 4 + i
                        } else {
                          pageNum = currentPage - 2 + i
                        }
                        return (
                          <Button
                            key={pageNum}
                            variant={currentPage === pageNum ? 'default' : 'outline'}
                            size="sm"
                            className="w-8 h-8 p-0"
                            onClick={() => setCurrentPage(pageNum)}
                          >
                            {pageNum}
                          </Button>
                        )
                      })}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.min(sortedAndPaginatedVentes.totalPages, p + 1))}
                      disabled={currentPage === sortedAndPaginatedVentes.totalPages}
                    >
                      Suivant
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(sortedAndPaginatedVentes.totalPages)}
                      disabled={currentPage === sortedAndPaginatedVentes.totalPages}
                    >
                      Fin
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Drawer details groupe */}
        <GroupeDrawer
          groupeId={selectedGroupe}
          currentCip={selectedCip}
          open={!!selectedGroupe}
          onClose={() => setSelectedGroupe(null)}
        />
      </div>
    </div>
  )
}
