import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Loader2,
  CheckSquare,
  Square,
  Trash2,
  Euro,
  Search,
  Ban,
  Link,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  X,
} from 'lucide-react'

import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { repertoireApi, ventesApi, type RattachementItem, type RattachementAlerte } from '@/lib/api'
import { toast } from 'sonner'
import { GroupeDrawer } from '@/components/GroupeDrawer'

export default function RapprochementVentes() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedImport, setSelectedImport] = useState<string>('all')
  const [step, setStep] = useState<'analyze' | 'loading' | 'results'>('analyze')
  const [loadingProgress, setLoadingProgress] = useState(0)

  // Selection pour suppression
  const [selectedToDelete, setSelectedToDelete] = useState<Set<number>>(new Set())

  // Propositions de rattachement
  const [expandedProposition, setExpandedProposition] = useState<number | null>(null)
  const [selectedToRattach, setSelectedToRattach] = useState<Set<number>>(new Set())

  // Dialog confirmation suppression
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  // Drawer groupe generique
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()

  // Alertes conditionnement
  const [alertesConditionnement, setAlertesConditionnement] = useState<RattachementAlerte[]>([])

  // Imports disponibles
  const { data: imports } = useQuery({
    queryKey: ['ventes-imports'],
    queryFn: ventesApi.getImports,
  })

  // Rapprochement
  const rapprochementMutation = useMutation({
    mutationFn: () => repertoireApi.rapprocher(selectedImport === 'all' ? undefined : parseInt(selectedImport)),
    onMutate: () => {
      setStep('loading')
      setLoadingProgress(0)
      // Simulate progress
      const interval = setInterval(() => {
        setLoadingProgress(prev => {
          if (prev >= 90) {
            clearInterval(interval)
            return 90
          }
          return prev + 10
        })
      }, 300)
      return { interval }
    },
    onSuccess: (_, __, context) => {
      if (context?.interval) clearInterval(context.interval)
      setLoadingProgress(100)
      setTimeout(() => {
        setStep('results')
        setSelectedToDelete(new Set())
      }, 500)
    },
    onError: (_, __, context) => {
      if (context?.interval) clearInterval(context.interval)
      setStep('analyze')
      toast.error('Erreur lors du rapprochement')
    },
  })

  // Suppression des ventes
  const deleteMutation = useMutation({
    mutationFn: (venteIds: number[]) => repertoireApi.validerRapprochement(venteIds, 'delete'),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ventes'] })
      toast.success(`${data.deleted} ventes supprimees`)
      setSelectedToDelete(new Set())
      setShowDeleteDialog(false)
      // Re-run rapprochement to update stats
      rapprochementMutation.mutate()
    },
    onError: () => {
      toast.error('Erreur lors de la suppression')
    },
  })

  // Rattachement fuzzy
  const rattachementMutation = useMutation({
    mutationFn: (rattachements: RattachementItem[]) => repertoireApi.rattacherFuzzy(rattachements),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['repertoire'] })

      // Gerer les alertes conditionnement
      if (data.alertes && data.alertes.length > 0) {
        setAlertesConditionnement(data.alertes)
        toast.warning(`${data.rattaches} rattache(s) - ${data.alertes.length} alerte(s) conditionnement`)
      } else {
        toast.success(data.message)
      }

      setSelectedToRattach(new Set())
      // Re-run rapprochement to update stats
      rapprochementMutation.mutate()
    },
    onError: () => {
      toast.error('Erreur lors du rattachement')
    },
  })

  const result = rapprochementMutation.data

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(value)
  }

  const toggleSelectToDelete = (id: number) => {
    const newSet = new Set(selectedToDelete)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedToDelete(newSet)
  }

  const selectAllToDelete = () => {
    if (result?.a_supprimer) {
      setSelectedToDelete(new Set(result.a_supprimer.map(v => v.vente_id)))
    }
  }

  const getRaisonBadge = (raison: string | null) => {
    switch (raison) {
      case 'princeps':
        return <Badge variant="secondary" className="bg-purple-100 text-purple-700">Princeps</Badge>
      case 'cip_non_trouve':
        return <Badge variant="secondary" className="bg-orange-100 text-orange-700">CIP non trouve</Badge>
      case 'sans_prix':
        return <Badge variant="secondary" className="bg-gray-100 text-gray-700">Sans prix PFHT</Badge>
      default:
        return <Badge variant="outline">-</Badge>
    }
  }

  const handleRattacher = () => {
    if (!result?.propositions_rattachement) return

    const rattachements: RattachementItem[] = result.propositions_rattachement
      .filter(p => selectedToRattach.has(p.vente_id) && p.cip13)
      .map(p => ({
        vente_id: p.vente_id,
        cip13: p.cip13!,
        groupe_generique_id: p.groupe_generique_id,
      }))

    if (rattachements.length === 0) {
      toast.error('Aucune proposition avec CIP selectionne')
      return
    }

    rattachementMutation.mutate(rattachements)
  }

  return (
    <div className="flex flex-col">
      <Header title="Rapprochement Ventes / Repertoire" description="Identifiez les ventes hors repertoire generique" />
      <div className="flex-1 space-y-6 p-6">
      {/* Back button */}
      <Button
        variant="ghost"
        className="mb-4 gap-2"
        onClick={() => navigate('/repertoire')}
      >
        <ArrowLeft className="h-4 w-4" />
        Retour au repertoire
      </Button>

      {step === 'analyze' && (
        <Card>
          <CardHeader>
            <CardTitle>Etape 1: Analyser les ventes</CardTitle>
            <CardDescription>
              Selectionnez un import de ventes a rapprocher avec le repertoire des generiques
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Select value={selectedImport} onValueChange={setSelectedImport}>
                <SelectTrigger className="w-[300px]">
                  <SelectValue placeholder="Selectionner un import" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes les ventes</SelectItem>
                  {imports?.map((imp) => (
                    <SelectItem key={imp.id} value={imp.id.toString()}>
                      {imp.nom_fichier || imp.nom} ({imp.nb_lignes_importees || 0} lignes)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                onClick={() => rapprochementMutation.mutate()}
                disabled={rapprochementMutation.isPending}
                className="gap-2"
              >
                {rapprochementMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                Rapprocher mes ventes
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {step === 'loading' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Analyse en cours...
            </CardTitle>
            <CardDescription>
              Rapprochement des ventes avec le repertoire BDPM
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={loadingProgress} className="w-full" />
            <p className="text-sm text-muted-foreground text-center">
              {loadingProgress < 30 && "Chargement des ventes..."}
              {loadingProgress >= 30 && loadingProgress < 60 && "Recherche des correspondances CIP..."}
              {loadingProgress >= 60 && loadingProgress < 90 && "Classification des resultats..."}
              {loadingProgress >= 90 && "Finalisation..."}
            </p>
          </CardContent>
        </Card>
      )}

      {step === 'results' && result && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-6 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total ventes</CardDescription>
                <CardTitle className="text-2xl">{result.stats.total_ventes}</CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-green-200 bg-green-50">
              <CardHeader className="pb-2">
                <CardDescription className="text-green-700">Valides</CardDescription>
                <CardTitle className="text-2xl text-green-700">
                  <CheckCircle className="h-5 w-5 inline mr-2" />
                  {result.stats.valides}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-blue-200 bg-blue-50">
              <CardHeader className="pb-2">
                <CardDescription className="text-blue-700">Propositions</CardDescription>
                <CardTitle className="text-2xl text-blue-700">
                  <Link className="h-5 w-5 inline mr-2" />
                  {result.stats.propositions || 0}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-red-200 bg-red-50">
              <CardHeader className="pb-2">
                <CardDescription className="text-red-700">A supprimer</CardDescription>
                <CardTitle className="text-2xl text-red-700">
                  <XCircle className="h-5 w-5 inline mr-2" />
                  {result.stats.a_supprimer}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-orange-200 bg-orange-50">
              <CardHeader className="pb-2">
                <CardDescription className="text-orange-700">CIP non trouve</CardDescription>
                <CardTitle className="text-2xl text-orange-700">
                  <Ban className="h-5 w-5 inline mr-2" />
                  {result.stats.cip_non_trouve}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-purple-200 bg-purple-50">
              <CardHeader className="pb-2">
                <CardDescription className="text-purple-700">Princeps</CardDescription>
                <CardTitle className="text-2xl text-purple-700">
                  <Euro className="h-5 w-5 inline mr-2" />
                  {result.stats.princeps}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Alertes conditionnement */}
          {alertesConditionnement.length > 0 && (
            <Card className="border-orange-300 bg-orange-50">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-orange-700 flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5" />
                    Alertes Conditionnement ({alertesConditionnement.length})
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setAlertesConditionnement([])}
                    className="gap-1 text-orange-600 hover:text-orange-800"
                  >
                    <X className="h-4 w-4" />
                    Fermer
                  </Button>
                </div>
                <CardDescription className="text-orange-600">
                  Ces CIP ont ete rattaches mais le conditionnement ne correspond pas - pas de prix attribue.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {alertesConditionnement.map((alerte, idx) => (
                    <div key={idx} className="flex items-start gap-3 p-2 bg-white rounded border border-orange-200">
                      <AlertTriangle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 text-sm">
                        <div className="font-medium">CIP: {alerte.cip13}</div>
                        <div className="text-muted-foreground">{alerte.message}</div>
                        {alerte.conditionnement_cip && (
                          <div className="text-xs mt-1">
                            <span className="text-orange-600">Conditionnement CIP: {alerte.conditionnement_cip} u.</span>
                            {alerte.conditionnements_groupe.length > 0 && (
                              <span className="ml-2">| Disponibles: {alerte.conditionnements_groupe.join(', ')} u.</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Propositions de rattachement */}
          {result.propositions_rattachement && result.propositions_rattachement.length > 0 && (
            <Card>
              <CardHeader className="bg-blue-50 border-b">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-blue-700 flex items-center gap-2">
                      <Link className="h-5 w-5" />
                      Propositions de rattachement ({result.propositions_rattachement.length})
                    </CardTitle>
                    <CardDescription>
                      Ces ventes peuvent etre rattachees a un groupe generique. Verifiez et validez.
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedToRattach(new Set())}
                      className="gap-1"
                    >
                      <Square className="h-4 w-4" />
                      Decocher tout
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedToRattach(new Set(result.propositions_rattachement.map(p => p.vente_id)))}
                      className="gap-1"
                    >
                      <CheckSquare className="h-4 w-4" />
                      Cocher tout
                    </Button>
                    <Button
                      className="gap-1 bg-blue-600 hover:bg-blue-700"
                      disabled={selectedToRattach.size === 0 || rattachementMutation.isPending}
                      onClick={handleRattacher}
                    >
                      {rattachementMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Link className="h-4 w-4" />
                      )}
                      Rattacher ({selectedToRattach.size})
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-96 overflow-y-auto">
                  {result.propositions_rattachement.map((prop) => (
                    <div key={prop.vente_id} className="border-b last:border-b-0">
                      {/* Ligne principale */}
                      <div
                        className={`flex items-center gap-4 p-4 cursor-pointer hover:bg-blue-50 ${selectedToRattach.has(prop.vente_id) ? 'bg-blue-100' : ''}`}
                        onClick={() => setExpandedProposition(expandedProposition === prop.vente_id ? null : prop.vente_id)}
                      >
                        <Checkbox
                          checked={selectedToRattach.has(prop.vente_id)}
                          onCheckedChange={(checked) => {
                            const newSet = new Set(selectedToRattach)
                            if (checked) {
                              newSet.add(prop.vente_id)
                            } else {
                              newSet.delete(prop.vente_id)
                            }
                            setSelectedToRattach(newSet)
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-muted-foreground">{prop.cip13 || '-'}</span>
                            <span className="font-medium truncate">{prop.designation}</span>
                          </div>
                          <div className="text-sm text-muted-foreground mt-1">
                            Qte: {prop.quantite} | Montant: {formatCurrency(prop.montant_ht)}
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                            Fuzzy {prop.fuzzy_score.toFixed(0)}%
                          </Badge>
                          <div className="text-sm font-medium text-green-700 mt-1">
                            PFHT: {prop.pfht_propose ? formatCurrency(prop.pfht_propose) : '-'}
                          </div>
                        </div>
                        {expandedProposition === prop.vente_id ? (
                          <ChevronUp className="h-5 w-5 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>

                      {/* Groupe generique (expanded) */}
                      {expandedProposition === prop.vente_id && (
                        <div className="bg-gray-50 p-4 border-t">
                          <div className="mb-3">
                            <span className="text-sm font-medium text-gray-700">Groupe generique propose:</span>
                            <p className="text-sm text-gray-900 mt-1">{prop.libelle_groupe}</p>
                          </div>
                          <div>
                            <span className="text-sm font-medium text-gray-700">
                              Membres du groupe ({prop.membres_groupe.length}):
                            </span>
                            <div className="mt-2 max-h-48 overflow-y-auto">
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead className="text-xs">CIP</TableHead>
                                    <TableHead className="text-xs">Denomination</TableHead>
                                    <TableHead className="text-xs">Type</TableHead>
                                    <TableHead className="text-xs text-right">PFHT</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {prop.membres_groupe.map((membre) => (
                                    <TableRow key={membre.cip13} className="text-xs">
                                      <TableCell className="font-mono">{membre.cip13}</TableCell>
                                      <TableCell className="truncate max-w-xs">{membre.denomination || '-'}</TableCell>
                                      <TableCell>
                                        {membre.type_generique === 0 ? (
                                          <Badge variant="outline" className="text-xs">Princeps</Badge>
                                        ) : membre.type_generique === 1 ? (
                                          <Badge variant="secondary" className="text-xs bg-green-100 text-green-700">Generique</Badge>
                                        ) : '-'}
                                      </TableCell>
                                      <TableCell className="text-right font-medium">
                                        {membre.pfht ? formatCurrency(membre.pfht) : '-'}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* A supprimer */}
          {result.a_supprimer.length > 0 && (
            <Card>
              <CardHeader className="bg-red-50 border-b">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-red-700 flex items-center gap-2">
                      <XCircle className="h-5 w-5" />
                      A supprimer ({result.a_supprimer.length})
                    </CardTitle>
                    <CardDescription>
                      Ces ventes ne sont PAS des generiques valides. Selectionnez celles a supprimer.
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedToDelete(new Set())}
                      className="gap-1"
                    >
                      <Square className="h-4 w-4" />
                      Decocher tout
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={selectAllToDelete}
                      className="gap-1"
                    >
                      <CheckSquare className="h-4 w-4" />
                      Cocher tout
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => setShowDeleteDialog(true)}
                      disabled={selectedToDelete.size === 0}
                      className="gap-1"
                    >
                      <Trash2 className="h-4 w-4" />
                      Supprimer ({selectedToDelete.size})
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-10"></TableHead>
                        <TableHead>CIP</TableHead>
                        <TableHead>Designation</TableHead>
                        <TableHead className="text-right">Qte</TableHead>
                        <TableHead className="text-right">Montant</TableHead>
                        <TableHead>Raison</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.a_supprimer.map((item) => (
                        <TableRow
                          key={item.vente_id}
                          className={selectedToDelete.has(item.vente_id) ? 'bg-red-100' : ''}
                        >
                          <TableCell>
                            <Checkbox
                              checked={selectedToDelete.has(item.vente_id)}
                              onCheckedChange={() => toggleSelectToDelete(item.vente_id)}
                            />
                          </TableCell>
                          <TableCell className="font-mono text-xs">{item.cip13 || '-'}</TableCell>
                          <TableCell className="max-w-xs truncate" title={item.designation}>
                            {item.designation}
                          </TableCell>
                          <TableCell className="text-right">{item.quantite}</TableCell>
                          <TableCell className="text-right">{formatCurrency(item.montant_ht)}</TableCell>
                          <TableCell>{getRaisonBadge(item.raison_suppression)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Valides */}
          {result.valides.length > 0 && (
            <Card>
              <CardHeader className="bg-green-50 border-b">
                <CardTitle className="text-green-700 flex items-center gap-2">
                  <CheckCircle className="h-5 w-5" />
                  Valides ({result.valides.length})
                </CardTitle>
                <CardDescription>
                  Ces ventes sont des generiques avec prix PFHT. Aucune action requise.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>CIP</TableHead>
                        <TableHead>Designation</TableHead>
                        <TableHead className="text-right">Qte</TableHead>
                        <TableHead className="text-right">PFHT unitaire</TableHead>
                        <TableHead className="text-right">Montant ligne</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.valides.slice(0, 100).map((item) => {
                        const montantLigne = item.pfht ? item.quantite * item.pfht : 0
                        return (
                          <TableRow
                            key={item.vente_id}
                            className={item.groupe_generique_id ? "cursor-pointer hover:bg-green-100" : ""}
                            onClick={() => {
                              if (item.groupe_generique_id) {
                                setSelectedGroupe(item.groupe_generique_id)
                                setSelectedCip(item.cip13 || undefined)
                              }
                            }}
                          >
                            <TableCell className="font-mono text-xs">{item.cip13 || '-'}</TableCell>
                            <TableCell className="max-w-xs truncate" title={item.designation}>
                              {item.designation}
                            </TableCell>
                            <TableCell className="text-right">{item.quantite}</TableCell>
                            <TableCell className="text-right font-medium text-green-700">
                              {item.pfht ? formatCurrency(item.pfht) : '-'}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {formatCurrency(montantLigne)}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
                {/* Total */}
                <div className="border-t bg-green-100 p-4 flex justify-between items-center">
                  <span className="font-medium text-green-800">
                    Total ({result.valides.length} lignes)
                  </span>
                  <span className="text-xl font-bold text-green-800">
                    {formatCurrency(
                      result.valides.reduce((sum, item) => sum + (item.pfht ? item.quantite * item.pfht : 0), 0)
                    )}
                  </span>
                </div>
                {result.valides.length > 100 && (
                  <p className="text-center text-sm text-muted-foreground py-2">
                    Affichage limite aux 100 premieres lignes
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          <div className="flex gap-4">
            <Button
              variant="outline"
              onClick={() => {
                setStep('analyze')
                rapprochementMutation.reset()
              }}
            >
              Nouvelle analyse
            </Button>
          </div>
        </div>
      )}

      {/* Dialog confirmation suppression */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmer la suppression</AlertDialogTitle>
            <AlertDialogDescription>
              Vous allez supprimer {selectedToDelete.size} ventes.
              Cette action est irreversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate(Array.from(selectedToDelete))}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
