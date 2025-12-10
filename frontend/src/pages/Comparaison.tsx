import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { GitCompare, Trophy } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { scenariosApi, comparaisonApi } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import type { ComparaisonScenarios } from '@/types'

export function Comparaison() {
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [comparaison, setComparaison] = useState<ComparaisonScenarios | null>(null)

  const { data: scenarios = [], isLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: scenariosApi.list,
  })

  const compareMutation = useMutation({
    mutationFn: comparaisonApi.compare,
    onSuccess: (data) => {
      setComparaison(data)
    },
  })

  const handleToggle = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const handleCompare = () => {
    if (selectedIds.length >= 2) {
      compareMutation.mutate(selectedIds)
    }
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Comparaison"
        description="Comparez les scenarios pour trouver le meilleur labo"
      />

      <div className="flex-1 space-y-6 p-6">
        <Card>
          <CardHeader>
            <CardTitle>Selectionnez les scenarios a comparer</CardTitle>
            <CardDescription>
              Choisissez au moins 2 scenarios pour les comparer
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-4 text-muted-foreground">
                Chargement...
              </div>
            ) : scenarios.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                Aucun scenario disponible. Creez d'abord des simulations.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  {scenarios.map((scenario) => (
                    <div
                      key={scenario.id}
                      className="flex items-center space-x-3 rounded-lg border p-3"
                    >
                      <Checkbox
                        checked={selectedIds.includes(scenario.id)}
                        onCheckedChange={() => handleToggle(scenario.id)}
                      />
                      <div className="flex-1">
                        <p className="font-medium">{scenario.nom}</p>
                        <p className="text-sm text-muted-foreground">
                          {scenario.laboratoire?.nom} - {formatPercent(scenario.remise_simulee || 0)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <Button
                  onClick={handleCompare}
                  disabled={selectedIds.length < 2 || compareMutation.isPending}
                  className="w-full"
                >
                  <GitCompare className="mr-2 h-4 w-4" />
                  Comparer ({selectedIds.length} selectionnes)
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {comparaison && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-yellow-500" />
                Resultats de la comparaison
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead></TableHead>
                    {comparaison.scenarios.map(({ scenario }) => (
                      <TableHead key={scenario.id} className="text-center">
                        {scenario.nom}
                        {scenario.id === comparaison.gagnant_id && (
                          <span className="ml-2 text-green-600">★</span>
                        )}
                      </TableHead>
                    ))}
                    <TableHead className="text-center">Ecart</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium">Chiffre realisable</TableCell>
                    {comparaison.scenarios.map(({ scenario, totaux }) => (
                      <TableCell key={scenario.id} className="text-center">
                        {formatCurrency(totaux.chiffre_realisable_ht)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center">-</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Chiffre perdu</TableCell>
                    {comparaison.scenarios.map(({ scenario, totaux }) => (
                      <TableCell key={scenario.id} className="text-center text-destructive">
                        {formatCurrency(totaux.chiffre_perdu_ht)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center">-</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Remise totale</TableCell>
                    {comparaison.scenarios.map(({ scenario, totaux }) => (
                      <TableCell
                        key={scenario.id}
                        className={`text-center font-bold ${
                          scenario.id === comparaison.gagnant_id ? 'text-green-600' : ''
                        }`}
                      >
                        {formatCurrency(totaux.total_remise_globale)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center font-bold text-green-600">
                      +{formatCurrency(comparaison.ecart_gain)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Remise ponderee</TableCell>
                    {comparaison.scenarios.map(({ scenario, totaux }) => (
                      <TableCell key={scenario.id} className="text-center">
                        {formatPercent(totaux.remise_totale_ponderee)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center">-</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">Couverture</TableCell>
                    {comparaison.scenarios.map(({ scenario, totaux }) => (
                      <TableCell key={scenario.id} className="text-center">
                        {formatPercent(totaux.taux_couverture)}
                      </TableCell>
                    ))}
                    <TableCell className="text-center">-</TableCell>
                  </TableRow>
                </TableBody>
              </Table>

              <div className="mt-6 rounded-lg bg-green-50 p-4">
                <div className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-green-600" />
                  <span className="font-medium text-green-600">
                    Gagnant:{' '}
                    {comparaison.scenarios.find(
                      ({ scenario }) => scenario.id === comparaison.gagnant_id
                    )?.scenario.nom}
                  </span>
                </div>
                <p className="mt-1 text-sm text-green-700">
                  Gain supplementaire de {formatCurrency(comparaison.ecart_gain)} par rapport au
                  deuxieme choix
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
