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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { GitCompare, Trophy, FlaskConical, Search } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { scenariosApi, comparaisonApi, laboratoiresApi, catalogueApi } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { GroupeDrawer } from '@/components/GroupeDrawer'
import type { ComparaisonScenarios, CatalogueComparisonDetail, CatalogueProduitDetail } from '@/types'

export function Comparaison() {
  // Scenarios comparison state
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [comparaison, setComparaison] = useState<ComparaisonScenarios | null>(null)

  // Catalogue comparison state
  const [labo1Id, setLabo1Id] = useState<number | null>(null)
  const [labo2Id, setLabo2Id] = useState<number | null>(null)
  const [catalogueComparison, setCatalogueComparison] = useState<CatalogueComparisonDetail | null>(null)
  const [searchFilter, setSearchFilter] = useState('')
  const [activeSection, setActiveSection] = useState<'communes' | 'only1' | 'only2'>('communes')

  // GroupeDrawer state
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()

  const { data: scenarios = [], isLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: scenariosApi.list,
  })

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const compareMutation = useMutation({
    mutationFn: comparaisonApi.compare,
    onSuccess: (data) => {
      setComparaison(data)
    },
  })

  const catalogueCompareMutation = useMutation({
    mutationFn: ({ labo1, labo2 }: { labo1: number; labo2: number }) =>
      catalogueApi.compareDetail(labo1, labo2),
    onSuccess: (data) => {
      setCatalogueComparison(data)
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

  const handleCompareCatalogues = () => {
    if (labo1Id && labo2Id && labo1Id !== labo2Id) {
      catalogueCompareMutation.mutate({ labo1: labo1Id, labo2: labo2Id })
    }
  }

  // Get current products list based on active section
  const getCurrentProducts = (): CatalogueProduitDetail[] => {
    if (!catalogueComparison) return []

    if (activeSection === 'communes') {
      // Pour les communs, on peut afficher labo1 ou labo2
      return catalogueComparison.communes.produits_labo1
    } else if (activeSection === 'only1') {
      return catalogueComparison.only_labo1.produits
    } else {
      return catalogueComparison.only_labo2.produits
    }
  }

  // Filter products by search
  const filterProducts = (products: CatalogueProduitDetail[]) => {
    if (!searchFilter) return products
    const search = searchFilter.toLowerCase()
    return products.filter((p) =>
      (p.nom_commercial?.toLowerCase().includes(search)) ||
      (p.code_cip?.includes(search)) ||
      (p.libelle_groupe?.toLowerCase().includes(search))
    )
  }

  const handleRowClick = (product: CatalogueProduitDetail) => {
    if (product.groupe_generique_id) {
      setSelectedGroupe(product.groupe_generique_id)
      setSelectedCip(product.code_cip || undefined)
    }
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Comparaison"
        description="Comparez les scenarios ou les catalogues"
      />

      <div className="flex-1 space-y-6 p-6">
        <Tabs defaultValue="scenarios">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="scenarios">
              <Trophy className="mr-2 h-4 w-4" />
              Scenarios
            </TabsTrigger>
            <TabsTrigger value="catalogues">
              <FlaskConical className="mr-2 h-4 w-4" />
              Catalogues Labos
            </TabsTrigger>
          </TabsList>

          {/* SCENARIOS TAB */}
          <TabsContent value="scenarios" className="space-y-6 mt-6">
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
          </TabsContent>

          {/* CATALOGUES TAB */}
          <TabsContent value="catalogues" className="space-y-6 mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Comparer les catalogues</CardTitle>
                <CardDescription>
                  Selectionnez deux laboratoires pour comparer leurs references produits
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Laboratoire 1</label>
                    <Select
                      value={labo1Id?.toString() || ''}
                      onValueChange={(v) => setLabo1Id(parseInt(v))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selectionnez un labo..." />
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
                  <div>
                    <label className="text-sm font-medium mb-2 block">Laboratoire 2</label>
                    <Select
                      value={labo2Id?.toString() || ''}
                      onValueChange={(v) => setLabo2Id(parseInt(v))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selectionnez un labo..." />
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
                </div>
                <Button
                  onClick={handleCompareCatalogues}
                  disabled={!labo1Id || !labo2Id || labo1Id === labo2Id || catalogueCompareMutation.isPending}
                  className="w-full"
                >
                  <FlaskConical className="mr-2 h-4 w-4" />
                  {catalogueCompareMutation.isPending ? 'Comparaison en cours...' : 'Comparer les catalogues'}
                </Button>
              </CardContent>
            </Card>

            {catalogueComparison && (
              <>
                {/* Summary Cards */}
                <div className="grid grid-cols-3 gap-4">
                  <Card
                    className={`cursor-pointer transition-all ${activeSection === 'communes' ? 'ring-2 ring-green-500' : ''}`}
                    onClick={() => setActiveSection('communes')}
                  >
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg text-green-600">Communs</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold">{catalogueComparison.communes.count}</div>
                      <p className="text-sm text-muted-foreground">groupes partages</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {catalogueComparison.communes.produits_labo1.length} ref. {catalogueComparison.labo1.nom}
                      </p>
                    </CardContent>
                  </Card>

                  <Card
                    className={`cursor-pointer transition-all ${activeSection === 'only1' ? 'ring-2 ring-blue-500' : ''}`}
                    onClick={() => setActiveSection('only1')}
                  >
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg text-blue-600">
                        Seulement {catalogueComparison.labo1.nom}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold">{catalogueComparison.only_labo1.count}</div>
                      <p className="text-sm text-muted-foreground">groupes exclusifs</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {catalogueComparison.only_labo1.produits.length} references
                      </p>
                    </CardContent>
                  </Card>

                  <Card
                    className={`cursor-pointer transition-all ${activeSection === 'only2' ? 'ring-2 ring-orange-500' : ''}`}
                    onClick={() => setActiveSection('only2')}
                  >
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg text-orange-600">
                        Seulement {catalogueComparison.labo2.nom}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold">{catalogueComparison.only_labo2.count}</div>
                      <p className="text-sm text-muted-foreground">groupes exclusifs</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {catalogueComparison.only_labo2.produits.length} references
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Stats Banner */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg bg-blue-50 p-4">
                    <p className="font-medium text-blue-700">{catalogueComparison.labo1.nom}</p>
                    <p className="text-sm text-blue-600">
                      {catalogueComparison.labo1.total_groupes} groupes | {catalogueComparison.labo1.total_produits} produits
                    </p>
                  </div>
                  <div className="rounded-lg bg-orange-50 p-4">
                    <p className="font-medium text-orange-700">{catalogueComparison.labo2.nom}</p>
                    <p className="text-sm text-orange-600">
                      {catalogueComparison.labo2.total_groupes} groupes | {catalogueComparison.labo2.total_produits} produits
                    </p>
                  </div>
                </div>

                {/* Products Table */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>
                        {activeSection === 'communes' && (
                          <span className="text-green-600">
                            References {catalogueComparison.labo1.nom} (groupes communs)
                          </span>
                        )}
                        {activeSection === 'only1' && (
                          <span className="text-blue-600">
                            References exclusives {catalogueComparison.labo1.nom}
                          </span>
                        )}
                        {activeSection === 'only2' && (
                          <span className="text-orange-600">
                            References exclusives {catalogueComparison.labo2.nom}
                          </span>
                        )}
                      </CardTitle>
                      <div className="relative w-64">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Rechercher..."
                          value={searchFilter}
                          onChange={(e) => setSearchFilter(e.target.value)}
                          className="pl-8"
                        />
                      </div>
                    </div>
                    <CardDescription>
                      Cliquez sur une reference pour voir les equivalents generiques
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-[500px] overflow-y-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Code CIP</TableHead>
                            <TableHead>Reference</TableHead>
                            <TableHead className="text-right">Prix BDPM</TableHead>
                            <TableHead className="text-right">Prix Catalogue</TableHead>
                            <TableHead className="text-right">Remise</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filterProducts(getCurrentProducts()).slice(0, 200).map((product) => (
                            <TableRow
                              key={product.id}
                              className={`${product.groupe_generique_id ? 'cursor-pointer hover:bg-muted/50' : ''}`}
                              onClick={() => handleRowClick(product)}
                            >
                              <TableCell className="font-mono text-sm">
                                {product.code_cip || '-'}
                              </TableCell>
                              <TableCell>
                                <div>
                                  <p className="font-medium">{product.nom_commercial || '-'}</p>
                                  {product.libelle_groupe && (
                                    <p className="text-xs text-muted-foreground truncate max-w-[300px]">
                                      {product.libelle_groupe}
                                    </p>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="text-right">
                                {product.prix_bdpm ? formatCurrency(product.prix_bdpm) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                {product.prix_catalogue ? (
                                  <span className={product.prix_bdpm && product.prix_catalogue !== product.prix_bdpm ? 'text-amber-600' : ''}>
                                    {formatCurrency(product.prix_catalogue)}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                {product.remise_pct ? (
                                  <Badge variant="outline" className="bg-green-50 text-green-700">
                                    {formatPercent(product.remise_pct)}
                                  </Badge>
                                ) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                          {filterProducts(getCurrentProducts()).length === 0 && (
                            <TableRow>
                              <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                                {searchFilter ? 'Aucune reference trouvee' : 'Aucune reference dans cette categorie'}
                              </TableCell>
                            </TableRow>
                          )}
                        </TableBody>
                      </Table>
                      {filterProducts(getCurrentProducts()).length > 200 && (
                        <p className="text-center text-sm text-muted-foreground mt-4">
                          Affichage des 200 premiers resultats sur {filterProducts(getCurrentProducts()).length}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* GroupeDrawer */}
      <GroupeDrawer
        groupeId={selectedGroupe}
        currentCip={selectedCip}
        open={!!selectedGroupe}
        onClose={() => setSelectedGroupe(null)}
      />
    </div>
  )
}
