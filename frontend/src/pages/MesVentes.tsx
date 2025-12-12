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
import { ShoppingCart, Upload, Trash2, FileX } from 'lucide-react'
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
      // Selectionner le prochain import disponible
      setSelectedImportId('')
    },
  })

  const handleImportChange = (value: string) => {
    setSelectedImportId(value)
    setSearchParams({ import_id: value })
  }

  const totalMontant = ventes.reduce((sum, v) => sum + (v.montant_annuel || 0), 0)
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
                    <TableHead className="text-right">Prix Unitaire</TableHead>
                    <TableHead className="text-right">Montant Annuel</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ventes.slice(0, 100).map((vente) => (
                    <TableRow key={vente.id}>
                      <TableCell className="font-mono text-sm">
                        {vente.code_cip_achete || '-'}
                      </TableCell>
                      <TableCell className="max-w-[300px] truncate">
                        {vente.designation || '-'}
                      </TableCell>
                      <TableCell>{vente.labo_actuel || '-'}</TableCell>
                      <TableCell className="text-right">
                        {vente.quantite_annuelle ? formatNumber(vente.quantite_annuelle) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {vente.prix_achat_unitaire ? formatCurrency(vente.prix_achat_unitaire) : '-'}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {vente.montant_annuel ? formatCurrency(vente.montant_annuel) : '-'}
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
