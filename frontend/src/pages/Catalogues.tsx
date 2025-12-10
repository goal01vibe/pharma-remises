import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { Search, Package, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { laboratoiresApi, catalogueApi } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'

export function Catalogues() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const selectedLaboId = searchParams.get('labo')

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const { data: catalogue = [], isLoading } = useQuery({
    queryKey: ['catalogue', selectedLaboId],
    queryFn: () => catalogueApi.list(selectedLaboId ? parseInt(selectedLaboId) : undefined),
    enabled: !!selectedLaboId,
  })

  const filteredCatalogue = catalogue.filter((produit) => {
    if (!search) return true
    const searchLower = search.toLowerCase()
    return (
      produit.nom_commercial?.toLowerCase().includes(searchLower) ||
      produit.code_cip?.includes(search) ||
      produit.presentation?.molecule?.toLowerCase().includes(searchLower)
    )
  })

  const handleLaboChange = (value: string) => {
    setSearchParams({ labo: value })
  }

  const getRemonteeStatus = (remontee_pct: number | null) => {
    if (remontee_pct === null) {
      return { label: 'Normal', color: 'text-green-600', icon: CheckCircle2 }
    }
    if (remontee_pct === 0) {
      return { label: 'Exclu', color: 'text-red-600', icon: AlertCircle }
    }
    return { label: `${remontee_pct}%`, color: 'text-orange-600', icon: AlertCircle }
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Catalogues"
        description="Consultez les catalogues des laboratoires"
      />

      <div className="flex-1 space-y-6 p-6">
        <div className="flex gap-4">
          <Select value={selectedLaboId || ''} onValueChange={handleLaboChange}>
            <SelectTrigger className="w-[250px]">
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

          {selectedLaboId && (
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Rechercher un produit..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
          )}
        </div>

        {!selectedLaboId ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Package className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Selectionnez un laboratoire</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Choisissez un laboratoire pour voir son catalogue
              </p>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            Chargement du catalogue...
          </div>
        ) : catalogue.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Package className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Catalogue vide</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Importez un catalogue pour ce laboratoire
              </p>
              <Button className="mt-4" asChild>
                <a href="/import">Importer un catalogue</a>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>
                Catalogue ({filteredCatalogue.length} produits)
              </CardTitle>
              <CardDescription>
                Liste des produits du laboratoire
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code CIP</TableHead>
                    <TableHead>Designation</TableHead>
                    <TableHead>Molecule</TableHead>
                    <TableHead className="text-right">Prix HT</TableHead>
                    <TableHead className="text-right">Remise Ligne</TableHead>
                    <TableHead>Remontee</TableHead>
                    <TableHead>Matching</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCatalogue.slice(0, 100).map((produit) => {
                    const status = getRemonteeStatus(produit.remontee_pct)
                    return (
                      <TableRow key={produit.id}>
                        <TableCell className="font-mono text-sm">
                          {produit.code_cip || '-'}
                        </TableCell>
                        <TableCell className="max-w-[300px] truncate">
                          {produit.nom_commercial || '-'}
                        </TableCell>
                        <TableCell>
                          {produit.presentation?.molecule || (
                            <span className="text-orange-600">Non matche</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {produit.prix_ht ? formatCurrency(produit.prix_ht) : '-'}
                        </TableCell>
                        <TableCell className="text-right">
                          {produit.remise_pct ? formatPercent(produit.remise_pct) : '-'}
                        </TableCell>
                        <TableCell>
                          <span className={`flex items-center gap-1 ${status.color}`}>
                            <status.icon className="h-4 w-4" />
                            {status.label}
                          </span>
                        </TableCell>
                        <TableCell>
                          {produit.presentation_id ? (
                            <span className="text-green-600">
                              <CheckCircle2 className="h-4 w-4" />
                            </span>
                          ) : (
                            <span className="text-orange-600">
                              <AlertCircle className="h-4 w-4" />
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {filteredCatalogue.length > 100 && (
                <p className="text-center text-sm text-muted-foreground mt-4">
                  Affichage des 100 premiers resultats sur {filteredCatalogue.length}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
