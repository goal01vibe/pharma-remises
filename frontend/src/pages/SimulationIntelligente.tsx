import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import { Loader2, AlertTriangle, Trash2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
  laboratoiresApi,
  ventesApi,
  intelligentMatchingApi,
  simulationWithMatchingApi,
  coverageApi,
  reportsApi,
  type SimulationWithMatchingResponse,
  type BestComboResponse,
  type ProcessSalesResponse,
} from '@/lib/api'

// Format currency
const formatEuro = (value: number) => {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  }).format(value)
}

// Format percentage
const formatPct = (value: number) => `${value.toFixed(1)}%`

export function SimulationIntelligente() {
  // State
  const [selectedImportId, setSelectedImportId] = useState<number | null>(null)
  const [selectedLaboId, setSelectedLaboId] = useState<number | null>(null)
  const [matchingResult, setMatchingResult] = useState<ProcessSalesResponse | null>(null)
  const [simulationResult, setSimulationResult] = useState<SimulationWithMatchingResponse | null>(null)
  const [comboResult, setComboResult] = useState<BestComboResponse | null>(null)
  const [activeTab, setActiveTab] = useState('matching')
  const [selectedLaboIds, setSelectedLaboIds] = useState<number[]>([])
  // State pour lignes ignorees
  const [showIgnoredDialog, setShowIgnoredDialog] = useState(false)
  const [selectedIgnoredIds, setSelectedIgnoredIds] = useState<number[]>([])

  // Queries
  const { data: imports } = useQuery({
    queryKey: ['imports-ventes'],
    queryFn: ventesApi.getImports,
  })

  const { data: labos } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const { data: matchingStats, refetch: refetchStats } = useQuery({
    queryKey: ['matching-stats', selectedImportId],
    queryFn: () => intelligentMatchingApi.getStats(selectedImportId!),
    enabled: !!selectedImportId,
  })

  // Mutations
  const processMatchingMutation = useMutation({
    mutationFn: intelligentMatchingApi.processSales,
    onSuccess: (data) => {
      setMatchingResult(data)
      refetchStats()
    },
  })

  const runSimulationMutation = useMutation({
    mutationFn: simulationWithMatchingApi.run,
    onSuccess: (data) => {
      setSimulationResult(data)
      setActiveTab('simulation')
    },
  })

  const getBestComboMutation = useMutation({
    mutationFn: ({ laboId, importId }: { laboId: number; importId: number }) =>
      coverageApi.getBestCombo(laboId, importId),
    onSuccess: (data) => {
      setComboResult(data)
      setActiveTab('combo')
    },
  })

  const deleteIgnoredMutation = useMutation({
    mutationFn: ventesApi.deleteByIds,
    onSuccess: () => {
      setShowIgnoredDialog(false)
      setSelectedIgnoredIds([])
      // Relancer la simulation pour mettre a jour les calculs
      if (selectedImportId && selectedLaboId) {
        runSimulationMutation.mutate({
          import_id: selectedImportId,
          labo_principal_id: selectedLaboId,
        })
      }
    },
  })

  // Memo pour filtrer les lignes ignorees (sans prix)
  const ignoredLines = useMemo(() => {
    if (!simulationResult?.details) return []
    return simulationResult.details.filter(
      (line) => line.match_type === 'sans_prix'
    )
  }, [simulationResult?.details])

  // Handlers
  const handleProcessMatching = () => {
    if (!selectedImportId || selectedLaboIds.length === 0) return
    processMatchingMutation.mutate({
      import_id: selectedImportId,
      min_score: 70,
      labo_ids: selectedLaboIds,
    })
  }

  const handleRunSimulation = () => {
    if (!selectedImportId || !selectedLaboId) return
    runSimulationMutation.mutate({
      import_id: selectedImportId,
      labo_principal_id: selectedLaboId,
    })
  }

  const handleGetBestCombo = () => {
    if (!selectedImportId || !selectedLaboId) return
    getBestComboMutation.mutate({
      laboId: selectedLaboId,
      importId: selectedImportId,
    })
  }

  const handleDownloadPDF = async () => {
    if (!selectedImportId || !selectedLaboId) return
    try {
      const blob = await reportsApi.downloadSimulationPDF(
        selectedImportId,
        selectedLaboId,
        'Ma Pharmacie'
      )
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `rapport_simulation_${selectedLaboId}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Erreur telechargement PDF:', error)
    }
  }

  // Handlers pour lignes ignorees
  const handleToggleIgnoredSelection = (venteId: number) => {
    setSelectedIgnoredIds((prev) =>
      prev.includes(venteId) ? prev.filter((id) => id !== venteId) : [...prev, venteId]
    )
  }

  const handleSelectAllIgnored = () => {
    if (selectedIgnoredIds.length === ignoredLines.length) {
      setSelectedIgnoredIds([])
    } else {
      setSelectedIgnoredIds(ignoredLines.map((l) => l.vente_id))
    }
  }

  const handleDeleteIgnored = () => {
    if (selectedIgnoredIds.length === 0) return
    deleteIgnoredMutation.mutate(selectedIgnoredIds)
  }

  const handleDeleteAllIgnored = () => {
    if (ignoredLines.length === 0) return
    deleteIgnoredMutation.mutate(ignoredLines.map((l) => l.vente_id))
  }

  // Filter only ventes imports
  const ventesImports = imports?.filter((i) => i.type_import === 'ventes') || []

  // Filter active labs (5 target labs)
  const targetLabs = labos?.filter((l) => l.actif) || []

  // Initialiser tous les labos comme selectionnes par defaut
  useEffect(() => {
    if (targetLabs.length > 0 && selectedLaboIds.length === 0) {
      setSelectedLaboIds(targetLabs.map((l) => l.id))
    }
  }, [targetLabs, selectedLaboIds.length])

  // Toggle selection d'un labo
  const toggleLaboSelection = (laboId: number) => {
    setSelectedLaboIds((prev) =>
      prev.includes(laboId) ? prev.filter((id) => id !== laboId) : [...prev, laboId]
    )
  }

  // Tout selectionner / deselectionner
  const toggleAllLabos = () => {
    if (selectedLaboIds.length === targetLabs.length) {
      setSelectedLaboIds([])
    } else {
      setSelectedLaboIds(targetLabs.map((l) => l.id))
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">Simulations Scenarios</h1>
          <p className="text-muted-foreground">
            Matching automatique + Simulation + Meilleure combo
          </p>
        </div>
        {simulationResult && (
          <Button onClick={handleDownloadPDF} variant="outline">
            Telecharger PDF
          </Button>
        )}
      </div>

      {/* Step 1: Selection */}
      <Card>
        <CardHeader>
          <CardTitle>1. Selection</CardTitle>
          <CardDescription>
            Choisissez l'import de ventes et le laboratoire principal
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Import de ventes</label>
              <Select
                value={selectedImportId?.toString() || ''}
                onValueChange={(v) => setSelectedImportId(parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selectionnez un import" />
                </SelectTrigger>
                <SelectContent>
                  {ventesImports.map((imp) => (
                    <SelectItem key={imp.id} value={imp.id.toString()}>
                      {imp.nom_fichier} ({imp.nb_lignes_importees} lignes)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Laboratoire principal</label>
              <Select
                value={selectedLaboId?.toString() || ''}
                onValueChange={(v) => setSelectedLaboId(parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selectionnez un labo" />
                </SelectTrigger>
                <SelectContent>
                  {targetLabs.map((labo) => (
                    <SelectItem key={labo.id} value={labo.id.toString()}>
                      {labo.nom} ({labo.remise_negociee || 0}%)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs for workflow steps */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="matching">2. Matching</TabsTrigger>
          <TabsTrigger value="simulation" disabled={!matchingStats?.matching_done}>
            3. Simulation
          </TabsTrigger>
          <TabsTrigger value="combo" disabled={!simulationResult}>
            4. Best Combo
          </TabsTrigger>
        </TabsList>

        {/* Tab: Matching */}
        <TabsContent value="matching" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Matching Intelligent</CardTitle>
              <CardDescription>
                Matcher les ventes avec les catalogues des 5 labos cibles via RapidFuzz
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Overlay de chargement pendant le matching */}
              {processMatchingMutation.isPending && (
                <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center">
                  <Card className="p-8 flex flex-col items-center gap-4 shadow-lg max-w-md">
                    <Loader2 className="h-12 w-12 animate-spin text-primary" />
                    <div className="text-center">
                      <p className="text-lg font-medium">Matching en cours...</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Import #{selectedImportId} - Analyse des {ventesImports.find(i => i.id === selectedImportId)?.nb_lignes_importees || '?'} ventes
                      </p>
                      <p className="text-xs text-muted-foreground mt-3 bg-muted p-2 rounded">
                        ⏱️ Première exécution : ~1-2 min (cache froid)<br/>
                        Exécutions suivantes : ~15-30 sec
                      </p>
                    </div>
                  </Card>
                </div>
              )}

              {/* Selection des labos a matcher */}
              <div className="p-4 border rounded-lg bg-muted/30">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-medium">Labos a matcher :</span>
                    <span className="text-xs text-muted-foreground">
                      (<span className="text-green-600 font-medium">■</span> CSV importé,
                      <span className="text-muted-foreground"> ■</span> BDPM)
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={toggleAllLabos}>
                    {selectedLaboIds.length === targetLabs.length ? 'Tout decocher' : 'Tout cocher'}
                  </Button>
                </div>
                <div className="flex flex-wrap gap-4">
                  {targetLabs.map((labo) => (
                    <label
                      key={labo.id}
                      className={`flex items-center gap-2 cursor-pointer p-2 rounded border transition-colors ${
                        labo.source === 'csv'
                          ? 'bg-green-50 border-green-200 hover:bg-green-100'
                          : 'bg-background border-border hover:bg-muted'
                      }`}
                    >
                      <Checkbox
                        checked={selectedLaboIds.includes(labo.id)}
                        onCheckedChange={() => toggleLaboSelection(labo.id)}
                      />
                      <span className={`text-sm ${labo.source === 'csv' ? 'text-green-700 font-medium' : ''}`}>
                        {labo.nom}
                      </span>
                    </label>
                  ))}
                </div>
                {selectedLaboIds.length === 0 && (
                  <p className="text-sm text-destructive mt-2">Selectionnez au moins un labo</p>
                )}
              </div>

              {matchingStats?.matching_done ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Badge variant="default">Matching effectue</Badge>
                    <span className="text-sm text-muted-foreground">
                      {matchingStats.matched_ventes} / {matchingStats.total_ventes} ventes matchees
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                    {matchingStats.by_lab?.map((lab) => (
                      <Link
                        key={lab.lab_id}
                        to={`/matching-details/${selectedImportId}/${lab.lab_id}`}
                        className="block"
                      >
                        <Card className="p-4 hover:border-primary hover:shadow-md transition-all cursor-pointer">
                          <div className="font-medium">{lab.lab_nom}</div>
                          <div className="text-2xl font-bold text-primary">
                            {formatPct(lab.couverture_count_pct)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {lab.matched_count} produits matchés
                          </div>
                          <Progress value={lab.couverture_count_pct} className="mt-2 h-2" />
                          <div className="text-xs text-primary mt-2 opacity-0 group-hover:opacity-100">
                            Voir details →
                          </div>
                        </Card>
                      </Link>
                    ))}
                  </div>

                  <Button
                    variant="outline"
                    onClick={handleProcessMatching}
                    disabled={processMatchingMutation.isPending}
                  >
                    <Loader2 className={`mr-2 h-4 w-4 ${processMatchingMutation.isPending ? 'animate-spin' : 'hidden'}`} />
                    Relancer le matching
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-muted-foreground">
                    Le matching n'a pas encore ete effectue pour cet import.
                  </p>
                  <Button
                    onClick={handleProcessMatching}
                    disabled={!selectedImportId || processMatchingMutation.isPending}
                    size="lg"
                  >
                    <Loader2 className={`mr-2 h-4 w-4 ${processMatchingMutation.isPending ? 'animate-spin' : 'hidden'}`} />
                    Lancer le matching
                  </Button>
                </div>
              )}

              {matchingResult && (
                <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-6 w-6 rounded-full bg-green-500 flex items-center justify-center">
                      <span className="text-white text-sm">✓</span>
                    </div>
                    <h4 className="font-medium text-green-700">Matching terminé avec succès</h4>
                    <Badge variant="outline" className="ml-auto">Import #{selectedImportId}</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Total ventes:</span>{' '}
                      {matchingResult.total_ventes}
                    </div>
                    <div>
                      <span className="text-muted-foreground">Matchées:</span>{' '}
                      <span className="text-green-600 font-medium">{matchingResult.matching_results.matched}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Non matchées:</span>{' '}
                      <span className="text-red-600">{matchingResult.matching_results.unmatched}</span>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    Temps d'exécution: {matchingResult.processing_time_s}s
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Simulation */}
        <TabsContent value="simulation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Simulation avec {selectedLaboId && targetLabs.find((l) => l.id === selectedLaboId)?.nom}</CardTitle>
              <CardDescription>
                Calcul des remises facture + remontee avec le matching intelligent
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!simulationResult ? (
                <div className="space-y-4">
                  <Button
                    onClick={handleRunSimulation}
                    disabled={!selectedLaboId || runSimulationMutation.isPending}
                  >
                    {runSimulationMutation.isPending ? 'Calcul en cours...' : 'Lancer la simulation'}
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* KPI Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Chiffre Total</div>
                      <div className="text-xl font-bold">
                        {formatEuro(Number(simulationResult.totaux.chiffre_total_ht))}
                      </div>
                    </Card>
                    <Card className="p-4 border-green-200 bg-green-50">
                      <div className="text-sm text-green-700">Chiffre Realisable</div>
                      <div className="text-xl font-bold text-green-700">
                        {formatEuro(Number(simulationResult.totaux.chiffre_realisable_ht))}
                      </div>
                      <div className="text-xs text-green-600">
                        {formatPct(Number(simulationResult.totaux.taux_couverture))} couverture
                      </div>
                    </Card>
                    <Card className="p-4 border-red-200 bg-red-50">
                      <div className="text-sm text-red-700">Chiffre Perdu</div>
                      <div className="text-xl font-bold text-red-700">
                        {formatEuro(Number(simulationResult.totaux.chiffre_perdu_ht))}
                      </div>
                      <div className="text-xs text-red-600">
                        {simulationResult.totaux.nb_produits_manquants} produits
                      </div>
                    </Card>
                    <Card className="p-4 border-blue-200 bg-blue-50">
                      <div className="text-sm text-blue-700">Total Remises</div>
                      <div className="text-xl font-bold text-blue-700">
                        {formatEuro(Number(simulationResult.totaux.total_remise_globale))}
                      </div>
                      <div className="text-xs text-blue-600">
                        {formatPct(Number(simulationResult.totaux.remise_totale_ponderee))} moyenne
                      </div>
                    </Card>
                  </div>

                  {/* Alerte lignes ignorees */}
                  {ignoredLines.length > 0 && (
                    <Card className="p-4 border-orange-300 bg-orange-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <AlertTriangle className="h-5 w-5 text-orange-600" />
                          <div>
                            <div className="font-medium text-orange-700">
                              {ignoredLines.length} ligne{ignoredLines.length > 1 ? 's' : ''} ignoree{ignoredLines.length > 1 ? 's' : ''} (sans prix)
                            </div>
                            <div className="text-sm text-orange-600">
                              Ces produits n'ont ni prix BDPM ni prix labo et sont exclus des calculs
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          className="border-orange-300 text-orange-700 hover:bg-orange-100"
                          onClick={() => setShowIgnoredDialog(true)}
                        >
                          Voir et gerer
                        </Button>
                      </div>
                    </Card>
                  )}

                  {/* Remise breakdown */}
                  <div className="grid grid-cols-2 gap-4">
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Remise Facture</div>
                      <div className="text-lg font-bold">
                        {formatEuro(Number(simulationResult.totaux.total_remise_ligne))}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatPct(Number(simulationResult.totaux.remise_ligne_moyenne))} moyenne
                      </div>
                    </Card>
                    <Card className="p-4">
                      <div className="text-sm text-muted-foreground">Remontee</div>
                      <div className="text-lg font-bold">
                        {formatEuro(Number(simulationResult.totaux.total_remontee))}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {simulationResult.totaux.nb_produits_exclus} produits exclus
                      </div>
                    </Card>
                  </div>

                  {/* Matching stats */}
                  <div className="p-4 bg-muted rounded-lg">
                    <h4 className="font-medium mb-2">Stats Matching</h4>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">
                        CIP exact: {simulationResult.matching_stats.exact_cip}
                      </Badge>
                      <Badge variant="outline">
                        Groupe gen: {simulationResult.matching_stats.groupe_generique}
                      </Badge>
                      <Badge variant="outline">
                        Fuzzy mol: {simulationResult.matching_stats.fuzzy_molecule}
                      </Badge>
                      <Badge variant="outline">
                        Fuzzy nom: {simulationResult.matching_stats.fuzzy_commercial}
                      </Badge>
                      <Badge variant="destructive">
                        No match: {simulationResult.matching_stats.no_match}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-2">
                      Score moyen: {simulationResult.matching_stats.avg_score}%
                    </div>
                  </div>

                  {/* Details table */}
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Designation</TableHead>
                          <TableHead className="text-right">Prix BDPM</TableHead>
                          <TableHead className="text-right">Prix Labo</TableHead>
                          <TableHead>Match</TableHead>
                          <TableHead className="text-right">Remise</TableHead>
                          <TableHead className="text-right">Total</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {simulationResult.details.slice(0, 50).map((line) => (
                          <TableRow key={line.vente_id}>
                            <TableCell className="max-w-[200px] truncate">
                              {line.designation}
                            </TableCell>
                            <TableCell className="text-right text-sm">
                              {line.prix_bdpm ? formatEuro(Number(line.prix_bdpm)) : '-'}
                            </TableCell>
                            <TableCell className="text-right text-sm">
                              {line.disponible && line.prix_labo ? (
                                <div className="flex items-center justify-end gap-1">
                                  <span>{formatEuro(Number(line.prix_labo))}</span>
                                  {line.price_diff && Math.abs(Number(line.price_diff)) > 0.01 && (
                                    <span
                                      className={`text-xs ${
                                        Number(line.price_diff) > 0
                                          ? 'text-red-600'
                                          : 'text-green-600'
                                      }`}
                                      title={`Ecart: ${Number(line.price_diff) > 0 ? '+' : ''}${formatEuro(Number(line.price_diff))} (${line.price_diff_pct?.toFixed(1)}%)`}
                                    >
                                      {Number(line.price_diff) > 0 ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                '-'
                              )}
                            </TableCell>
                            <TableCell>
                              {line.disponible ? (
                                <Badge variant="default" className="text-xs">
                                  {line.match_type} ({line.match_score?.toFixed(0)}%)
                                </Badge>
                              ) : (
                                <Badge variant="destructive" className="text-xs">
                                  Non trouve
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {line.disponible
                                ? formatPct(Number(line.remise_totale_pct))
                                : '-'}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {line.disponible
                                ? formatEuro(Number(line.montant_total_remise))
                                : '-'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {simulationResult.details.length > 50 && (
                      <div className="p-2 text-center text-sm text-muted-foreground border-t">
                        ... et {simulationResult.details.length - 50} autres lignes
                      </div>
                    )}
                  </div>

                  <Button onClick={handleGetBestCombo} disabled={getBestComboMutation.isPending}>
                    {getBestComboMutation.isPending
                      ? 'Calcul...'
                      : 'Voir les labos complementaires'}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Best Combo */}
        <TabsContent value="combo" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Labos Complementaires</CardTitle>
              <CardDescription>
                Pour le chiffre perdu, voici les meilleures options classees par montant de remise
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {comboResult && (
                <div className="space-y-6">
                  {/* Summary */}
                  <div className="p-4 border rounded-lg bg-red-50 border-red-200">
                    <div className="text-sm text-red-700">Chiffre perdu chez {comboResult.labo_principal.nom}</div>
                    <div className="text-2xl font-bold text-red-700">
                      {formatEuro(Number(comboResult.chiffre_perdu_ht))}
                    </div>
                    <div className="text-sm text-red-600">
                      {comboResult.nb_produits_perdus} produits non couverts
                    </div>
                  </div>

                  {/* Best Combo */}
                  {comboResult.best_combo && (
                    <div className="p-4 border rounded-lg bg-green-50 border-green-200">
                      <div className="text-sm text-green-700 font-medium">Recommandation</div>
                      <div className="text-lg font-bold text-green-700">
                        {comboResult.best_combo.labs.map((l) => l.nom).join(' + ')}
                      </div>
                      <div className="grid grid-cols-3 gap-4 mt-2 text-sm">
                        <div>
                          <span className="text-green-600">Couverture:</span>{' '}
                          {formatPct(comboResult.best_combo.couverture_totale_pct)}
                        </div>
                        <div>
                          <span className="text-green-600">Chiffre:</span>{' '}
                          {formatEuro(Number(comboResult.best_combo.chiffre_total_realisable_ht))}
                        </div>
                        <div>
                          <span className="text-green-600">Remises:</span>{' '}
                          <span className="font-bold">
                            {formatEuro(Number(comboResult.best_combo.montant_remise_total))}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Recommendations table */}
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Labo</TableHead>
                          <TableHead className="text-right">Chiffre Recupere</TableHead>
                          <TableHead className="text-right">Remise Estimee</TableHead>
                          <TableHead className="text-right">Couverture Add.</TableHead>
                          <TableHead className="text-right">Nb Produits</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {comboResult.recommendations.map((reco, idx) => (
                          <TableRow key={reco.lab_id}>
                            <TableCell className="font-medium">
                              {idx === 0 && '★ '}
                              {reco.lab_nom}
                            </TableCell>
                            <TableCell className="text-right">
                              {formatEuro(Number(reco.chiffre_recupere_ht))}
                            </TableCell>
                            <TableCell className="text-right font-bold text-green-600">
                              {formatEuro(Number(reco.montant_remise_estime))}
                            </TableCell>
                            <TableCell className="text-right">
                              {formatPct(reco.couverture_additionnelle_pct)}
                            </TableCell>
                            <TableCell className="text-right">{reco.nb_produits_recuperes}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  <div className="flex gap-2">
                    <Button onClick={handleDownloadPDF}>
                      Telecharger le rapport PDF
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialog pour lignes ignorees */}
      <Dialog open={showIgnoredDialog} onOpenChange={setShowIgnoredDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              Lignes ignorees ({ignoredLines.length})
            </DialogTitle>
            <DialogDescription>
              Ces produits n'ont ni prix BDPM ni prix labo. Ils sont exclus des calculs de simulation.
              Vous pouvez les supprimer pour nettoyer vos donnees.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-auto border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={selectedIgnoredIds.length === ignoredLines.length && ignoredLines.length > 0}
                      onCheckedChange={handleSelectAllIgnored}
                    />
                  </TableHead>
                  <TableHead>Designation</TableHead>
                  <TableHead className="text-right">Quantite</TableHead>
                  <TableHead>Code CIP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ignoredLines.map((line) => (
                  <TableRow key={line.vente_id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIgnoredIds.includes(line.vente_id)}
                        onCheckedChange={() => handleToggleIgnoredSelection(line.vente_id)}
                      />
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">{line.designation}</TableCell>
                    <TableCell className="text-right">{line.quantite}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">-</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <div className="flex-1 text-sm text-muted-foreground">
              {selectedIgnoredIds.length > 0
                ? `${selectedIgnoredIds.length} ligne${selectedIgnoredIds.length > 1 ? 's' : ''} selectionnee${selectedIgnoredIds.length > 1 ? 's' : ''}`
                : 'Aucune selection'}
            </div>
            <Button
              variant="outline"
              onClick={() => setShowIgnoredDialog(false)}
            >
              Fermer
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteIgnored}
              disabled={selectedIgnoredIds.length === 0 || deleteIgnoredMutation.isPending}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Supprimer selection ({selectedIgnoredIds.length})
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAllIgnored}
              disabled={deleteIgnoredMutation.isPending}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Supprimer tout ({ignoredLines.length})
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
