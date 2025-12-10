import { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
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
import { Upload, FileSpreadsheet, FileText, X, Check, AlertCircle } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { laboratoiresApi, importApi } from '@/lib/api'
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

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
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
    mutationFn: importApi.importVentes,
    onSuccess: () => {
      setFile(null)
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0])
      setExtractedData([])
      setProgress(0)
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
      importVentesMutation.mutate(file)
    }
  }

  const isPDF = file?.name.endsWith('.pdf')

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

                {file && isPDF && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Options d'extraction PDF</CardTitle>
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
                        <p className="text-xs text-muted-foreground">
                          Auto: essaie gpt-4o-mini puis gpt-4o si echec
                        </p>
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
                      {extractedData.length > 50 && (
                        <p className="text-center text-sm text-muted-foreground mt-2">
                          Affichage des 50 premieres lignes sur {extractedData.length}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}

                <Button
                  onClick={handleImportCatalogue}
                  disabled={!file || !selectedLaboId || importCatalogueMutation.isPending}
                  className="w-full"
                >
                  Valider l'import
                </Button>
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
                      Le fichier doit contenir les colonnes suivantes:
                    </p>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      <li>• <strong>code_cip</strong> - Code CIP du produit</li>
                      <li>• <strong>designation</strong> - Nom du produit</li>
                      <li>• <strong>quantite</strong> - Quantite annuelle</li>
                      <li>• <strong>prix_unitaire</strong> - Prix d'achat unitaire HT</li>
                      <li>• <strong>labo</strong> (optionnel) - Laboratoire actuel</li>
                    </ul>
                  </CardContent>
                </Card>

                <Button
                  onClick={handleImportVentes}
                  disabled={!file || importVentesMutation.isPending}
                  className="w-full"
                >
                  Importer mes ventes
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
