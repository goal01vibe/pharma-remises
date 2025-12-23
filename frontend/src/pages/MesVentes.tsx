import { useState, useEffect } from 'react'
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
import { ShoppingCart, Upload, Trash2, FileX, AlertTriangle, RefreshCw } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ventesApi } from '@/lib/api'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { Link, useSearchParams } from 'react-router-dom'

export function MesVentes() {
  const [searchParams, setSearchParams] = useSearchParams()
  const importIdParam = searchParams.get('import_id')
  const [selectedImportId, setSelectedImportId] = useState<string>(importIdParam || '')

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
                    <TableHead>Code CIP</TableHead>
                    <TableHead>Designation</TableHead>
                    <TableHead>Labo Actuel</TableHead>
                    <TableHead className="text-right">Quantite</TableHead>
                    <TableHead className="text-right">Prix BDPM</TableHead>
                    <TableHead className="text-right">Montant Annuel</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ventes.slice(0, 100).map((vente) => (
                    <TableRow key={vente.id} className={!vente.has_bdpm_price ? 'bg-amber-50/50' : ''}>
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
                          onClick={() => deleteVenteMutation.mutate(vente.id)}
                          disabled={deleteVenteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {ventes.length > 100 && (
                <p className="text-center text-sm text-muted-foreground mt-4">
                  Affichage des 100 premiers resultats sur {ventes.length}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
