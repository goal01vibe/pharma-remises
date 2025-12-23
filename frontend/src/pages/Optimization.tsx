import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Loader2, Plus, X, Target, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  ventesApi,
  optimizationApi,
  type LaboObjectiveInput,
  type OptimizeResponse,
  type ProduitLabo,
} from '@/lib/api'
import { formatCurrency } from '@/lib/utils'

interface LaboConfig extends LaboObjectiveInput {
  labo_nom: string
  potentiel_ht: number
  remise_negociee: number
  nb_matchings: number
  enabled: boolean
  objectif_type: 'pct' | 'montant'
  exclusion_names: string[] // Pour afficher les noms
}

export function Optimization() {
  // State
  const [selectedImportId, setSelectedImportId] = useState<number | null>(null)
  const [laboConfigs, setLaboConfigs] = useState<LaboConfig[]>([])
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [exclusionDialogLabo, setExclusionDialogLabo] = useState<number | null>(null)
  const [exclusionSearch, setExclusionSearch] = useState('')

  // Queries
  const { data: imports } = useQuery({
    queryKey: ['imports-ventes'],
    queryFn: ventesApi.getImports,
  })

  const { data: labosData, isLoading: labosLoading } = useQuery({
    queryKey: ['optimization-labos', selectedImportId],
    queryFn: () => optimizationApi.getLabosDisponibles(selectedImportId!),
    enabled: !!selectedImportId,
  })

  const { data: produitsSearch } = useQuery({
    queryKey: ['produits-labo', selectedImportId, exclusionDialogLabo, exclusionSearch],
    queryFn: () => optimizationApi.getProduitsLabo(selectedImportId!, exclusionDialogLabo!, exclusionSearch),
    enabled: !!selectedImportId && !!exclusionDialogLabo && exclusionSearch.length >= 2,
  })

  // Mutations
  const previewMutation = useMutation({
    mutationFn: optimizationApi.preview,
  })

  const runMutation = useMutation({
    mutationFn: (request: { import_id: number; objectives: LaboObjectiveInput[] }) =>
      optimizationApi.run(request, true),
    onSuccess: (data) => {
      setResult(data)
    },
  })

  // Initialize labo configs when data loads
  useEffect(() => {
    if (labosData?.labos) {
      setLaboConfigs(
        labosData.labos.map((labo) => ({
          labo_id: labo.labo_id,
          labo_nom: labo.labo_nom,
          potentiel_ht: labo.potentiel_ht,
          remise_negociee: labo.remise_negociee,
          nb_matchings: labo.nb_matchings,
          enabled: true,
          objectif_type: 'pct',
          objectif_pct: 50, // Default 50%
          objectif_montant: undefined,
          exclusions: [],
          exclusion_names: [],
        }))
      )
      setResult(null)
    }
  }, [labosData])

  // Handlers
  const updateLaboConfig = (laboId: number, updates: Partial<LaboConfig>) => {
    setLaboConfigs((prev) =>
      prev.map((c) => (c.labo_id === laboId ? { ...c, ...updates } : c))
    )
  }

  const addExclusion = (laboId: number, produit: ProduitLabo) => {
    setLaboConfigs((prev) =>
      prev.map((c) => {
        if (c.labo_id === laboId && !c.exclusions?.includes(produit.id)) {
          return {
            ...c,
            exclusions: [...(c.exclusions || []), produit.id],
            exclusion_names: [...(c.exclusion_names || []), produit.nom_commercial],
          }
        }
        return c
      })
    )
  }

  const removeExclusion = (laboId: number, produitId: number) => {
    setLaboConfigs((prev) =>
      prev.map((c) => {
        if (c.labo_id === laboId) {
          const idx = c.exclusions?.indexOf(produitId) ?? -1
          if (idx >= 0) {
            const newExclusions = [...(c.exclusions || [])]
            const newNames = [...(c.exclusion_names || [])]
            newExclusions.splice(idx, 1)
            newNames.splice(idx, 1)
            return { ...c, exclusions: newExclusions, exclusion_names: newNames }
          }
        }
        return c
      })
    )
  }

  const handlePreview = () => {
    if (!selectedImportId) return
    const enabledLabos = laboConfigs.filter((c) => c.enabled)
    previewMutation.mutate({
      import_id: selectedImportId,
      objectives: enabledLabos.map((c) => ({
        labo_id: c.labo_id,
        objectif_pct: c.objectif_type === 'pct' ? c.objectif_pct : undefined,
        objectif_montant: c.objectif_type === 'montant' ? c.objectif_montant : undefined,
        exclusions: c.exclusions,
      })),
    })
  }

  const handleRun = () => {
    if (!selectedImportId) return
    const enabledLabos = laboConfigs.filter((c) => c.enabled)
    runMutation.mutate({
      import_id: selectedImportId,
      objectives: enabledLabos.map((c) => ({
        labo_id: c.labo_id,
        objectif_pct: c.objectif_type === 'pct' ? c.objectif_pct : undefined,
        objectif_montant: c.objectif_type === 'montant' ? c.objectif_montant : undefined,
        exclusions: c.exclusions,
      })),
    })
  }

  const ventesImports = imports?.filter((i) => i.type_import === 'ventes') || []
  const enabledCount = laboConfigs.filter((c) => c.enabled).length

  return (
    <div className="flex flex-col">
      <Header
        title="Optimisation Multi-Labos"
        description="Repartition optimale des achats entre plusieurs laboratoires"
      />

      <div className="flex-1 space-y-6 p-6">
        {/* Step 1: Selection Import */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              1. Selection de l'import
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-w-md">
              <Select
                value={selectedImportId?.toString() || ''}
                onValueChange={(v) => setSelectedImportId(parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selectionnez un import de ventes" />
                </SelectTrigger>
                <SelectContent>
                  {ventesImports.map((imp) => (
                    <SelectItem key={imp.id} value={imp.id.toString()}>
                      {imp.nom || imp.nom_fichier} ({imp.nb_lignes_importees} lignes)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Step 2: Configuration Labos */}
        {selectedImportId && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                2. Configuration des laboratoires
              </CardTitle>
              <CardDescription>
                Selectionnez les labos, definissez les objectifs et exclusions
              </CardDescription>
            </CardHeader>
            <CardContent>
              {labosLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : laboConfigs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Aucun labo disponible. Lancez d'abord le matching.
                </div>
              ) : (
                <div className="space-y-4">
                  {laboConfigs.map((config) => (
                    <div
                      key={config.labo_id}
                      className={`p-4 border rounded-lg transition-colors ${
                        config.enabled ? 'bg-background' : 'bg-muted/50 opacity-60'
                      }`}
                    >
                      <div className="flex items-start gap-4">
                        {/* Checkbox enable */}
                        <Checkbox
                          checked={config.enabled}
                          onCheckedChange={(checked) =>
                            updateLaboConfig(config.labo_id, { enabled: !!checked })
                          }
                          className="mt-1"
                        />

                        {/* Labo info */}
                        <div className="flex-1 space-y-3">
                          <div className="flex items-center justify-between">
                            <div>
                              <h4 className="font-medium">{config.labo_nom}</h4>
                              <p className="text-sm text-muted-foreground">
                                Potentiel: {formatCurrency(config.potentiel_ht)} |
                                Remise: {config.remise_negociee}% |
                                {config.nb_matchings} produits
                              </p>
                            </div>
                            {config.enabled && (
                              <Badge variant="outline" className="bg-green-50 text-green-700">
                                Actif
                              </Badge>
                            )}
                          </div>

                          {config.enabled && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {/* Objectif */}
                              <div className="space-y-2">
                                <Label className="text-sm">Objectif minimum</Label>
                                <div className="flex gap-2">
                                  <Select
                                    value={config.objectif_type}
                                    onValueChange={(v: 'pct' | 'montant') =>
                                      updateLaboConfig(config.labo_id, { objectif_type: v })
                                    }
                                  >
                                    <SelectTrigger className="w-[100px]">
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="pct">%</SelectItem>
                                      <SelectItem value="montant">EUR</SelectItem>
                                    </SelectContent>
                                  </Select>
                                  <Input
                                    type="number"
                                    value={
                                      config.objectif_type === 'pct'
                                        ? config.objectif_pct || ''
                                        : config.objectif_montant || ''
                                    }
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value) || 0
                                      if (config.objectif_type === 'pct') {
                                        updateLaboConfig(config.labo_id, { objectif_pct: val })
                                      } else {
                                        updateLaboConfig(config.labo_id, { objectif_montant: val })
                                      }
                                    }}
                                    className="w-[120px]"
                                    placeholder={config.objectif_type === 'pct' ? '50' : '10000'}
                                  />
                                  <span className="text-sm text-muted-foreground self-center">
                                    {config.objectif_type === 'pct'
                                      ? `= ${formatCurrency((config.potentiel_ht * (config.objectif_pct || 0)) / 100)}`
                                      : `= ${(((config.objectif_montant || 0) / config.potentiel_ht) * 100).toFixed(1)}%`}
                                  </span>
                                </div>
                              </div>

                              {/* Exclusions */}
                              <div className="space-y-2">
                                <Label className="text-sm">Exclusions</Label>
                                <div className="flex flex-wrap gap-1">
                                  {config.exclusion_names?.map((name, idx) => (
                                    <Badge
                                      key={idx}
                                      variant="secondary"
                                      className="text-xs cursor-pointer hover:bg-destructive hover:text-destructive-foreground"
                                      onClick={() =>
                                        removeExclusion(config.labo_id, config.exclusions![idx])
                                      }
                                    >
                                      {name.slice(0, 20)}...
                                      <X className="h-3 w-3 ml-1" />
                                    </Badge>
                                  ))}
                                  <Dialog
                                    open={exclusionDialogLabo === config.labo_id}
                                    onOpenChange={(open) => {
                                      setExclusionDialogLabo(open ? config.labo_id : null)
                                      setExclusionSearch('')
                                    }}
                                  >
                                    <DialogTrigger asChild>
                                      <Button variant="outline" size="sm" className="h-6 px-2">
                                        <Plus className="h-3 w-3 mr-1" />
                                        Ajouter
                                      </Button>
                                    </DialogTrigger>
                                    <DialogContent>
                                      <DialogHeader>
                                        <DialogTitle>Exclure un produit</DialogTitle>
                                        <DialogDescription>
                                          Recherchez et selectionnez les produits a exclure de{' '}
                                          {config.labo_nom}
                                        </DialogDescription>
                                      </DialogHeader>
                                      <div className="space-y-4">
                                        <Input
                                          placeholder="Rechercher un produit..."
                                          value={exclusionSearch}
                                          onChange={(e) => setExclusionSearch(e.target.value)}
                                          autoFocus
                                        />
                                        {produitsSearch?.produits && produitsSearch.produits.length > 0 ? (
                                          <div className="max-h-[300px] overflow-y-auto border rounded-lg">
                                            {produitsSearch.produits.map((p) => (
                                              <div
                                                key={p.id}
                                                className={`p-2 hover:bg-muted cursor-pointer border-b last:border-b-0 ${
                                                  config.exclusions?.includes(p.id)
                                                    ? 'bg-muted opacity-50'
                                                    : ''
                                                }`}
                                                onClick={() => {
                                                  if (!config.exclusions?.includes(p.id)) {
                                                    addExclusion(config.labo_id, p)
                                                  }
                                                }}
                                              >
                                                <div className="font-medium text-sm">
                                                  {p.nom_commercial}
                                                </div>
                                                <div className="text-xs text-muted-foreground">
                                                  CIP: {p.code_cip || '-'} | {formatCurrency(p.prix_ht)}
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        ) : exclusionSearch.length >= 2 ? (
                                          <p className="text-sm text-muted-foreground text-center py-4">
                                            Aucun produit trouve
                                          </p>
                                        ) : (
                                          <p className="text-sm text-muted-foreground text-center py-4">
                                            Tapez au moins 2 caracteres
                                          </p>
                                        )}
                                      </div>
                                    </DialogContent>
                                  </Dialog>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {/* Actions */}
                  <div className="flex gap-4 pt-4 border-t">
                    <Button
                      variant="outline"
                      onClick={handlePreview}
                      disabled={enabledCount < 2 || previewMutation.isPending}
                    >
                      {previewMutation.isPending && (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      )}
                      Previsualiser
                    </Button>
                    <Button
                      onClick={handleRun}
                      disabled={enabledCount < 2 || runMutation.isPending}
                    >
                      {runMutation.isPending && (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      )}
                      Lancer l'optimisation
                    </Button>
                    {enabledCount < 2 && (
                      <span className="text-sm text-muted-foreground self-center">
                        Selectionnez au moins 2 labos
                      </span>
                    )}
                  </div>

                  {/* Preview result */}
                  {previewMutation.data && (
                    <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                      <h4 className="font-medium mb-2">Previsualisation</h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        {previewMutation.data.labos.map((labo) => (
                          <div
                            key={labo.labo_id}
                            className={`p-2 rounded ${
                              labo.realisable ? 'bg-green-50' : 'bg-red-50'
                            }`}
                          >
                            <div className="font-medium">{labo.labo_nom}</div>
                            <div className="text-xs">
                              Objectif: {formatCurrency(labo.objectif_minimum_calcule)}
                            </div>
                            <div className="text-xs">
                              Potentiel: {formatCurrency(labo.potentiel_ht)}
                            </div>
                            {labo.realisable ? (
                              <Badge variant="outline" className="mt-1 text-green-700">
                                OK
                              </Badge>
                            ) : (
                              <Badge variant="destructive" className="mt-1">
                                Impossible
                              </Badge>
                            )}
                          </div>
                        ))}
                      </div>
                      {!previewMutation.data.tous_realisables && (
                        <div className="mt-2 p-2 bg-red-100 text-red-700 rounded text-sm flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4" />
                          {previewMutation.data.message}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Step 3: Results */}
        {result && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {result.success ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                )}
                3. Resultats de l'optimisation
              </CardTitle>
              <CardDescription>
                {result.message} (temps: {Number(result.solver_time_ms).toFixed(0)}ms)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.success ? (
                <div className="space-y-6">
                  {/* KPIs */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Chiffre Total</div>
                      <div className="text-xl font-bold">
                        {formatCurrency(result.chiffre_total_ht)}
                      </div>
                    </Card>
                    <Card className="p-4 bg-green-50 border-green-200">
                      <div className="text-sm text-green-700">Remise Totale</div>
                      <div className="text-xl font-bold text-green-700">
                        {formatCurrency(result.remise_totale)}
                      </div>
                    </Card>
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Couverture</div>
                      <div className="text-xl font-bold">{result.couverture_pct}%</div>
                    </Card>
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Status</div>
                      <Badge
                        variant={result.status === 'OPTIMAL' ? 'default' : 'secondary'}
                        className="mt-1"
                      >
                        {result.status}
                      </Badge>
                    </Card>
                  </div>

                  {/* Repartition by labo */}
                  <div className="space-y-4">
                    <h4 className="font-medium">Repartition par laboratoire</h4>
                    {result.repartition.map((rep) => (
                      <div key={rep.labo_id} className="border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <h5 className="font-medium">{rep.labo_nom}</h5>
                            <p className="text-sm text-muted-foreground">
                              {rep.nb_produits} produits | Objectif:{' '}
                              {formatCurrency(rep.objectif_minimum)}
                            </p>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold">
                              {formatCurrency(rep.chiffre_ht)}
                            </div>
                            <div className="text-sm text-green-600">
                              Remise: {formatCurrency(rep.remise_totale)}
                            </div>
                          </div>
                        </div>
                        <Progress
                          value={(rep.chiffre_ht / rep.potentiel_ht) * 100}
                          className="h-2"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground mt-1">
                          <span>
                            {((rep.chiffre_ht / rep.potentiel_ht) * 100).toFixed(1)}% du potentiel
                          </span>
                          {rep.objectif_atteint ? (
                            <Badge variant="outline" className="text-green-600">
                              Objectif atteint
                            </Badge>
                          ) : (
                            <Badge variant="destructive">Objectif non atteint</Badge>
                          )}
                        </div>

                        {/* Details ventes */}
                        {rep.ventes && rep.ventes.length > 0 && (
                          <details className="mt-4">
                            <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                              Voir les {rep.ventes.length} produits
                            </summary>
                            <div className="mt-2 max-h-[200px] overflow-y-auto border rounded">
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead>Produit</TableHead>
                                    <TableHead className="text-right">Qte</TableHead>
                                    <TableHead className="text-right">Montant</TableHead>
                                    <TableHead className="text-right">Remise</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {rep.ventes.slice(0, 20).map((v) => (
                                    <TableRow key={v.vente_id}>
                                      <TableCell className="text-sm truncate max-w-[200px]">
                                        {v.produit_nom || v.designation}
                                      </TableCell>
                                      <TableCell className="text-right text-sm">
                                        {v.quantite}
                                      </TableCell>
                                      <TableCell className="text-right text-sm">
                                        {formatCurrency(v.montant_ht)}
                                      </TableCell>
                                      <TableCell className="text-right text-sm text-green-600">
                                        {formatCurrency(v.gain_remise)}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                              {rep.ventes.length > 20 && (
                                <div className="text-center text-xs text-muted-foreground py-2 border-t">
                                  ... et {rep.ventes.length - 20} autres
                                </div>
                              )}
                            </div>
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-700">{result.message}</p>
                  <p className="text-sm text-red-600 mt-2">
                    Essayez de reduire les objectifs ou d'ajouter plus de labos.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
