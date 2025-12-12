import { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
import { Upload, FileSpreadsheet, FileText, X, Check, AlertCircle, Plus, RefreshCw, ArrowRight, Trash2, Eye } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { laboratoiresApi, importApi, importRapprochementApi, ventesApi, type ImportPreviewResponse } from '@/lib/api'
import type { LigneExtraite } from '@/types'
import { formatCurrency, formatPercent } from '@/lib/utils'

export function Import() {
  const [searchParams] = useSearchParams()
  const defaultTab = searchParams.get('type') === 'ventes' ? 'ventes' : 'catalogue'

  const [selectedLaboId, setSelectedLaboId] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [pageDebut, setPageDebut] = useState<number>(1)
  const [pageFin, setPageFin] = useState<number>(100)
  const [modeleIA, setModeleIA] = useState<string>('auto')
  const [extractedData, setExtractedData] = useState<LigneExtraite[]>([])
  const [progress, setProgress] = useState<number>(0)

  // Rapprochement state
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null)
  const [applyNouveaux, setApplyNouveaux] = useState(true)
  const [applyUpdates, setApplyUpdates] = useState(true)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [importSuccess, setImportSuccess] = useState<string | null>(null)

  // Ventes state
  const [ventesNom, setVentesNom] = useState<string>('')
  const [ventesSuccess, setVentesSuccess] = useState<{ nb_lignes: number; nom: string } | null>(null)

  const queryClient = useQueryClient()

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const { data: ventesImports = [] } = useQuery({
    queryKey: ['ventes-imports'],
    queryFn: ventesApi.getImports,
  })

  const extractPDFMutation = useMutation({
    mutationFn: (formFile: File) =>
      importApi.extractPDF(formFile, {
        page_debut: pageDebut,
        page_fin: pageFin,
        modele_ia: modeleIA,
      }),
    onSuccess: (data) => {
      setExtractedData(data.lignes)
      setProgress(100)
    },
    onError: () => {
      setProgress(0)
    },
  })

  const importCatalogueMutation = useMutation({
    mutationFn: (formFile: File) =>
      importApi.importCatalogue(formFile, parseInt(selectedLaboId)),
    onSuccess: () => {
      setFile(null)
      setExtractedData([])
    },
  })

  const importVentesMutation = useMutation({
    mutationFn: ({ file, nom }: { file: File; nom?: string }) => importApi.importVentes(file, nom),
    onSuccess: (data) => {
      setFile(null)
      setVentesNom('')
      setVentesSuccess({ nb_lignes: data.nb_lignes_importees || 0, nom: data.nom || 'Import' })
      queryClient.invalidateQueries({ queryKey: ['ventes-imports'] })
    },
  })

  const deleteVentesImportMutation = useMutation({
    mutationFn: ventesApi.deleteImport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ventes-imports'] })
    },
  })

  // Rapprochement mutations
  const previewMutation = useMutation({
    mutationFn: ({ formFile, laboId }: { formFile: File; laboId: number }) =>
      importRapprochementApi.preview(formFile, laboId),
    onSuccess: (data) => {
      setPreviewData(data)
      setImportSuccess(null)
    },
  })

  const confirmMutation = useMutation({
    mutationFn: ({ previewId, applyNouveaux, applyUpdates }: { previewId: string; applyNouveaux: boolean; applyUpdates: boolean }) =>
      importRapprochementApi.confirm(previewId, { apply_nouveaux: applyNouveaux, apply_updates: applyUpdates }),
    onSuccess: (data) => {
      setPreviewData(null)
      setFile(null)
      setShowConfirmDialog(false)
      setImportSuccess(data.message)
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0])
      setExtractedData([])
      setProgress(0)
      setPreviewData(null)
      setImportSuccess(null)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
  })

  const handleExtractPDF = () => {
    if (file && file.name.endsWith('.pdf')) {
      setProgress(10)
      extractPDFMutation.mutate(file)
    }
  }

  const handleImportCatalogue = () => {
    if (file && selectedLaboId) {
      importCatalogueMutation.mutate(file)
    }
  }

  const handleImportVentes = () => {
    if (file) {
      setVentesSuccess(null)
      importVentesMutation.mutate({ file, nom: ventesNom || undefined })
    }
  }

  const handlePreviewRapprochement = () => {
    if (file && selectedLaboId) {
      previewMutation.mutate({ formFile: file, laboId: parseInt(selectedLaboId) })
    }
  }

  const handleConfirmImport = () => {
    if (previewData) {
      confirmMutation.mutate({
        previewId: previewData.preview_id,
        applyNouveaux,
        applyUpdates,
      })
    }
  }

  const isPDF = file?.name.endsWith('.pdf')
  const isExcelOrCSV = file && !isPDF


  return (
    <div className="flex flex-col">
      <Header
        title="Import de donnees"
        description="Importez vos catalogues et ventes"
      />

      <div className="flex-1 space-y-6 p-6">
        <Tabs defaultValue={defaultTab}>
          <TabsList>
            <TabsTrigger value="catalogue">Import Catalogue</TabsTrigger>
            <TabsTrigger value="ventes">Import Ventes</TabsTrigger>
          </TabsList>

          <TabsContent value="catalogue" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Import de catalogue laboratoire</CardTitle>
                <CardDescription>
                  Importez un catalogue depuis un fichier PDF, Excel ou CSV
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>Laboratoire cible</Label>
                  <Select value={selectedLaboId} onValueChange={setSelectedLaboId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Selectionnez un laboratoire" />
                    </SelectTrigger>
                    <SelectContent>
                      {laboratoires.map((labo) => (
                        <SelectItem key={labo.id} value={labo.id.toString()}>
                          {labo.nom}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-muted-foreground/25 hover:border-primary'
                  }`}
                >
                  <input {...getInputProps()} />
                  {file ? (
                    <div className="flex items-center justify-center gap-2">
                      {isPDF ? (
                        <FileText className="h-8 w-8 text-red-500" />
                      ) : (
                        <FileSpreadsheet className="h-8 w-8 text-green-500" />
                      )}
                      <span className="font-medium">{file.name}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setFile(null)
                          setExtractedData([])
                          setPreviewData(null)
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                      <p className="text-muted-foreground">
                        Glissez un fichier ici ou cliquez pour selectionner
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Formats acceptes: PDF, Excel (.xlsx, .xls), CSV
                      </p>
                    </>
                  )}
                </div>

                {importSuccess && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-green-800">
                      <Check className="h-5 w-5" />
                      <span className="font-medium">{importSuccess}</span>
                    </div>
                  </div>
                )}

                {file && isPDF && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Options extraction PDF</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="grid gap-2">
                          <Label htmlFor="pageDebut">Page debut</Label>
                          <Input
                            id="pageDebut"
                            type="number"
                            value={pageDebut}
                            onChange={(e) => setPageDebut(parseInt(e.target.value) || 1)}
                            min={1}
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor="pageFin">Page fin</Label>
                          <Input
                            id="pageFin"
                            type="number"
                            value={pageFin}
                            onChange={(e) => setPageFin(parseInt(e.target.value) || 100)}
                            min={pageDebut}
                          />
                        </div>
                      </div>

                      <div className="grid gap-2">
                        <Label>Modele IA</Label>
                        <Select value={modeleIA} onValueChange={setModeleIA}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="auto">Auto (recommande)</SelectItem>
                            <SelectItem value="gpt-4o-mini">gpt-4o-mini (rapide)</SelectItem>
                            <SelectItem value="gpt-4o">gpt-4o (precis)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {progress > 0 && progress < 100 && (
                        <div className="space-y-2">
                          <Progress value={progress} />
                          <p className="text-sm text-muted-foreground text-center">
                            Extraction en cours...
                          </p>
                        </div>
                      )}

                      <Button
                        onClick={handleExtractPDF}
                        disabled={extractPDFMutation.isPending}
                        className="w-full"
                      >
                        Extraire le PDF
                      </Button>
                    </CardContent>
                  </Card>
                )}

                {extractedData.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">
                        Preview ({extractedData.length} lignes extraites)
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="max-h-[300px] overflow-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>CIP</TableHead>
                              <TableHead>Designation</TableHead>
                              <TableHead className="text-right">Prix HT</TableHead>
                              <TableHead className="text-right">Remise</TableHead>
                              <TableHead>Confiance</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {extractedData.slice(0, 50).map((ligne, idx) => (
                              <TableRow key={idx}>
                                <TableCell className="font-mono text-sm">
                                  {ligne.code_cip || '-'}
                                </TableCell>
                                <TableCell className="max-w-[200px] truncate">
                                  {ligne.designation || '-'}
                                </TableCell>
                                <TableCell className="text-right">
                                  {ligne.prix_ht ? formatCurrency(ligne.prix_ht) : '-'}
                                </TableCell>
                                <TableCell className="text-right">
                                  {ligne.remise_pct ? formatPercent(ligne.remise_pct) : '-'}
                                </TableCell>
                                <TableCell>
                                  {ligne.confiance >= 0.8 ? (
                                    <Check className="h-4 w-4 text-green-600" />
                                  ) : ligne.confiance >= 0.5 ? (
                                    <AlertCircle className="h-4 w-4 text-orange-500" />
                                  ) : (
                                    <AlertCircle className="h-4 w-4 text-red-500" />
                                  )}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {isExcelOrCSV && selectedLaboId && !previewData && (
                  <Button
                    onClick={handlePreviewRapprochement}
                    disabled={previewMutation.isPending}
                    variant="outline"
                    className="w-full"
                  >
                    <RefreshCw className={`h-4 w-4 mr-2 ${previewMutation.isPending ? 'animate-spin' : ''}`} />
                    {previewMutation.isPending ? 'Analyse en cours...' : 'Analyser avec rapprochement'}
                  </Button>
                )}

                {previewData && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center justify-between">
                        <span>Rapport de rapprochement - {previewData.laboratoire.nom}</span>
                        <Button variant="ghost" size="sm" onClick={() => setPreviewData(null)}>
                          <X className="h-4 w-4" />
                        </Button>
                      </CardTitle>
                      <CardDescription>
                        {previewData.total_lignes_fichier} lignes dans le fichier, {previewData.total_produits_existants} produits existants
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-4 gap-4">
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                          <div className="text-2xl font-bold text-green-700">{previewData.resume.nouveaux}</div>
                          <div className="text-xs text-green-600">Nouveaux</div>
                        </div>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
                          <div className="text-2xl font-bold text-blue-700">{previewData.resume.mis_a_jour}</div>
                          <div className="text-xs text-blue-600">Mis a jour</div>
                        </div>
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                          <div className="text-2xl font-bold text-gray-700">{previewData.resume.inchanges}</div>
                          <div className="text-xs text-gray-600">Inchanges</div>
                        </div>
                        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                          <div className="text-2xl font-bold text-red-700">{previewData.resume.erreurs}</div>
                          <div className="text-xs text-red-600">Erreurs</div>
                        </div>
                      </div>

                      <Accordion type="multiple" className="w-full">
                        {previewData.nouveaux.length > 0 && (
                          <AccordionItem value="nouveaux">
                            <AccordionTrigger>
                              <div className="flex items-center gap-2">
                                <Plus className="h-4 w-4 text-green-600" />
                                <span>Nouveaux produits ({previewData.nouveaux.length})</span>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <div className="max-h-[200px] overflow-auto">
                                <Table>
                                  <TableHeader>
                                    <TableRow>
                                      <TableHead>Ligne</TableHead>
                                      <TableHead>CIP</TableHead>
                                      <TableHead>Designation</TableHead>
                                      <TableHead className="text-right">Prix HT</TableHead>
                                      <TableHead className="text-right">Remise</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {previewData.nouveaux.slice(0, 50).map((item, idx) => (
                                      <TableRow key={idx}>
                                        <TableCell className="text-muted-foreground">{item.ligne}</TableCell>
                                        <TableCell className="font-mono text-sm">{item.code_cip || '-'}</TableCell>
                                        <TableCell className="max-w-[200px] truncate">{item.designation || '-'}</TableCell>
                                        <TableCell className="text-right">
                                          {item.prix_ht_import ? formatCurrency(item.prix_ht_import) : '-'}
                                        </TableCell>
                                        <TableCell className="text-right">
                                          {item.remise_pct_import ? formatPercent(item.remise_pct_import) : '-'}
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        )}

                        {previewData.mis_a_jour.length > 0 && (
                          <AccordionItem value="mis_a_jour">
                            <AccordionTrigger>
                              <div className="flex items-center gap-2">
                                <RefreshCw className="h-4 w-4 text-blue-600" />
                                <span>Produits mis a jour ({previewData.mis_a_jour.length})</span>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <div className="max-h-[200px] overflow-auto">
                                <Table>
                                  <TableHeader>
                                    <TableRow>
                                      <TableHead>Produit</TableHead>
                                      <TableHead>Match</TableHead>
                                      <TableHead>Modifications</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {previewData.mis_a_jour.slice(0, 50).map((item, idx) => (
                                      <TableRow key={idx}>
                                        <TableCell>
                                          <div className="font-medium">{item.nom_existant || item.designation}</div>
                                          <div className="text-xs text-muted-foreground font-mono">{item.code_cip_existant || item.code_cip}</div>
                                        </TableCell>
                                        <TableCell>
                                          <Badge variant={item.match_type === 'cip_exact' ? 'default' : 'secondary'}>
                                            {item.match_type === 'cip_exact' ? 'CIP exact' : `Fuzzy ${Math.round(item.match_score)}%`}
                                          </Badge>
                                        </TableCell>
                                        <TableCell>
                                          <div className="space-y-1">
                                            {item.changes?.map((change, cIdx) => (
                                              <div key={cIdx} className="flex items-center gap-2 text-sm">
                                                <span className="text-muted-foreground">{change.champ === 'prix_ht' ? 'Prix HT' : 'Remise'}:</span>
                                                <span className="text-red-500 line-through">
                                                  {change.champ === 'prix_ht'
                                                    ? (change.ancien !== null ? formatCurrency(change.ancien) : '-')
                                                    : (change.ancien !== null ? formatPercent(change.ancien) : '-')
                                                  }
                                                </span>
                                                <ArrowRight className="h-3 w-3" />
                                                <span className="text-green-600 font-medium">
                                                  {change.champ === 'prix_ht'
                                                    ? (change.nouveau !== null ? formatCurrency(change.nouveau) : '-')
                                                    : (change.nouveau !== null ? formatPercent(change.nouveau) : '-')
                                                  }
                                                </span>
                                              </div>
                                            ))}
                                          </div>
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        )}

                        {previewData.inchanges.length > 0 && (
                          <AccordionItem value="inchanges">
                            <AccordionTrigger>
                              <div className="flex items-center gap-2">
                                <Check className="h-4 w-4 text-gray-600" />
                                <span>Produits inchanges ({previewData.inchanges.length})</span>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <p className="text-sm text-muted-foreground">
                                {previewData.inchanges.length} produit(s) deja present(s) sans modification necessaire.
                              </p>
                            </AccordionContent>
                          </AccordionItem>
                        )}

                        {previewData.erreurs.length > 0 && (
                          <AccordionItem value="erreurs">
                            <AccordionTrigger>
                              <div className="flex items-center gap-2">
                                <AlertCircle className="h-4 w-4 text-red-600" />
                                <span>Erreurs ({previewData.erreurs.length})</span>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent>
                              <div className="space-y-2">
                                {previewData.erreurs.map((err, idx) => (
                                  <div key={idx} className="text-sm text-red-600">
                                    Ligne {err.ligne}: {err.erreur}
                                  </div>
                                ))}
                              </div>
                            </AccordionContent>
                          </AccordionItem>
                        )}
                      </Accordion>

                      <div className="border-t pt-4 space-y-3">
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="applyNouveaux"
                            checked={applyNouveaux}
                            onCheckedChange={(checked) => setApplyNouveaux(checked === true)}
                          />
                          <Label htmlFor="applyNouveaux" className="text-sm">
                            Creer les {previewData.resume.nouveaux} nouveaux produits
                          </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="applyUpdates"
                            checked={applyUpdates}
                            onCheckedChange={(checked) => setApplyUpdates(checked === true)}
                          />
                          <Label htmlFor="applyUpdates" className="text-sm">
                            Appliquer les {previewData.resume.mis_a_jour} mises a jour
                          </Label>
                        </div>
                      </div>

                      <Button
                        onClick={() => setShowConfirmDialog(true)}
                        disabled={(!applyNouveaux && !applyUpdates) || confirmMutation.isPending}
                        className="w-full"
                      >
                        Confirmer import
                      </Button>
                    </CardContent>
                  </Card>
                )}

                {!previewData && (
                  <Button
                    onClick={handleImportCatalogue}
                    disabled={!file || !selectedLaboId || importCatalogueMutation.isPending}
                    className="w-full"
                  >
                    Valider import (sans rapprochement)
                  </Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="ventes" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Import de vos ventes</CardTitle>
                <CardDescription>
                  Importez votre historique de ventes annuel (Excel ou CSV)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {ventesSuccess && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-green-800">
                      <Check className="h-5 w-5" />
                      <span className="font-medium">
                        Import "{ventesSuccess.nom}" reussi: {ventesSuccess.nb_lignes} lignes importees
                      </span>
                    </div>
                    <div className="mt-2 flex gap-2">
                      <Button asChild size="sm" variant="outline">
                        <Link to="/ventes">Voir mes ventes</Link>
                      </Button>
                      <Button asChild size="sm">
                        <Link to="/simulations">Lancer une simulation</Link>
                      </Button>
                    </div>
                  </div>
                )}

                <div className="grid gap-2">
                  <Label htmlFor="ventesNom">Nom de l'import (optionnel)</Label>
                  <Input
                    id="ventesNom"
                    value={ventesNom}
                    onChange={(e) => setVentesNom(e.target.value)}
                    placeholder="Ex: Ventes 2024, Export LGO Janvier..."
                  />
                  <p className="text-xs text-muted-foreground">
                    Donnez un nom pour identifier facilement cet import
                  </p>
                </div>

                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                    isDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-muted-foreground/25 hover:border-primary'
                  }`}
                >
                  <input {...getInputProps()} />
                  {file ? (
                    <div className="flex items-center justify-center gap-2">
                      <FileSpreadsheet className="h-8 w-8 text-green-500" />
                      <span className="font-medium">{file.name}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setFile(null)
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                      <p className="text-muted-foreground">
                        Glissez un fichier ici ou cliquez pour selectionner
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Formats acceptes: Excel (.xlsx, .xls), CSV
                      </p>
                    </>
                  )}
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Format attendu</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-2">
                      Le fichier doit contenir au minimum:
                    </p>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      <li>- <strong>Code CIP</strong> - Code CIP du produit</li>
                      <li>- <strong>Designation</strong> - Nom du produit</li>
                      <li>- <strong>Quantite</strong> - Quantite vendue</li>
                    </ul>
                    <p className="text-xs text-muted-foreground mt-2">
                      Les noms de colonnes sont detectes automatiquement (ex: "Qte Facturee", "Code CIP"...)
                    </p>
                  </CardContent>
                </Card>

                <Button
                  onClick={handleImportVentes}
                  disabled={!file || importVentesMutation.isPending}
                  className="w-full"
                >
                  {importVentesMutation.isPending ? 'Import en cours...' : 'Importer mes ventes'}
                </Button>
              </CardContent>
            </Card>

            {ventesImports.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Historique des imports</CardTitle>
                  <CardDescription>
                    {ventesImports.length} fichier{ventesImports.length > 1 ? 's' : ''} de ventes importe{ventesImports.length > 1 ? 's' : ''}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Nom</TableHead>
                        <TableHead>Fichier</TableHead>
                        <TableHead className="text-right">Lignes</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ventesImports.map((imp) => (
                        <TableRow key={imp.id}>
                          <TableCell className="font-medium">
                            {imp.nom || `Import #${imp.id}`}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                            {imp.nom_fichier}
                          </TableCell>
                          <TableCell className="text-right">
                            {imp.nb_lignes_importees || 0}
                          </TableCell>
                          <TableCell>
                            {new Date(imp.created_at).toLocaleDateString('fr-FR')}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-2">
                              <Button asChild variant="outline" size="sm">
                                <Link to={`/ventes?import_id=${imp.id}`}>
                                  <Eye className="h-4 w-4" />
                                </Link>
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => deleteVentesImportMutation.mutate(imp.id)}
                                disabled={deleteVentesImportMutation.isPending}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmer import</AlertDialogTitle>
            <AlertDialogDescription>
              Vous allez appliquer les modifications suivantes:
              {applyNouveaux && previewData && previewData.resume.nouveaux > 0 && (
                <span className="block mt-2">- Creer {previewData.resume.nouveaux} nouveaux produits</span>
              )}
              {applyUpdates && previewData && previewData.resume.mis_a_jour > 0 && (
                <span className="block">- Mettre a jour {previewData.resume.mis_a_jour} produits existants</span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmImport} disabled={confirmMutation.isPending}>
              {confirmMutation.isPending ? 'Import en cours...' : 'Confirmer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
