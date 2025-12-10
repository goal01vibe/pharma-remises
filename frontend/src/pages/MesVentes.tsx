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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ShoppingCart, Upload } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { ventesApi } from '@/lib/api'
import { formatCurrency, formatNumber } from '@/lib/utils'
import { Link } from 'react-router-dom'

export function MesVentes() {
  const { data: ventes = [], isLoading } = useQuery({
    queryKey: ['ventes'],
    queryFn: () => ventesApi.list(),
  })

  const totalMontant = ventes.reduce((sum, v) => sum + (v.montant_annuel || 0), 0)
  const totalQuantite = ventes.reduce((sum, v) => sum + (v.quantite_annuelle || 0), 0)

  return (
    <div className="flex flex-col">
      <Header
        title="Mes Ventes"
        description="Historique de vos achats annuels"
      />

      <div className="flex-1 space-y-6 p-6">
        <div className="flex justify-between">
          <div className="space-y-1">
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

        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            Chargement...
          </div>
        ) : ventes.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <ShoppingCart className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Aucune vente importee</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Importez votre historique de ventes pour lancer des simulations
              </p>
              <Button className="mt-4" asChild>
                <Link to="/import?type=ventes">Importer mes ventes</Link>
              </Button>
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
