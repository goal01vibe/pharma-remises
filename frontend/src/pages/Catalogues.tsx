import { useState, useMemo } from 'react'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Search, Package, AlertCircle, CheckCircle2, Trash2, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { laboratoiresApi, catalogueApi } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { GroupeDrawer } from '@/components/GroupeDrawer'

type SortKey = 'code_cip' | 'nom_commercial' | 'molecule' | 'prix_ht' | 'remise_pct' | 'remontee_pct'
type SortOrder = 'asc' | 'desc'

const DISPLAY_LIMIT = 2000

export function Catalogues() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearConfirmText, setClearConfirmText] = useState('')
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [selectedGroupe, setSelectedGroupe] = useState<number | null>(null)
  const [selectedCip, setSelectedCip] = useState<string>()
  const selectedLaboId = searchParams.get('labo')
  const queryClient = useQueryClient()

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const { data: catalogue = [], isLoading } = useQuery({
    queryKey: ['catalogue', selectedLaboId],
    queryFn: () => catalogueApi.list(selectedLaboId ? parseInt(selectedLaboId) : undefined),
    enabled: !!selectedLaboId,
  })

  const deleteProduitMutation = useMutation({
    mutationFn: catalogueApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalogue', selectedLaboId] })
    },
  })

  const clearCatalogueMutation = useMutation({
    mutationFn: () => catalogueApi.clearCatalogue(parseInt(selectedLaboId!)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalogue', selectedLaboId] })
      setClearDialogOpen(false)
      setClearConfirmText('')
    },
  })

  const filteredAndSortedCatalogue = useMemo(() => {
    // Filter
    let result = catalogue.filter((produit) => {
      if (!search) return true
      const searchLower = search.toLowerCase()
      return (
        produit.nom_commercial?.toLowerCase().includes(searchLower) ||
        produit.code_cip?.includes(search) ||
        produit.presentation?.molecule?.toLowerCase().includes(searchLower)
      )
    })

    // Sort
    if (sortKey) {
      result = [...result].sort((a, b) => {
        let aVal: string | number | null = null
        let bVal: string | number | null = null

        switch (sortKey) {
          case 'code_cip':
            aVal = a.code_cip || ''
            bVal = b.code_cip || ''
            break
          case 'nom_commercial':
            aVal = a.nom_commercial || ''
            bVal = b.nom_commercial || ''
            break
          case 'molecule':
            aVal = a.presentation?.molecule || ''
            bVal = b.presentation?.molecule || ''
            break
          case 'prix_ht':
            aVal = a.prix_ht ?? a.prix_fabricant ?? 0
            bVal = b.prix_ht ?? b.prix_fabricant ?? 0
            break
          case 'remise_pct':
            aVal = a.remise_pct ?? 0
            bVal = b.remise_pct ?? 0
            break
          case 'remontee_pct':
            // null = 999 (normal at end), 0 = 0 (exclu first), others by value
            aVal = a.remontee_pct === null ? 999 : a.remontee_pct
            bVal = b.remontee_pct === null ? 999 : b.remontee_pct
            break
        }

        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return sortOrder === 'asc'
            ? aVal.localeCompare(bVal, 'fr')
            : bVal.localeCompare(aVal, 'fr')
        }

        return sortOrder === 'asc'
          ? (aVal as number) - (bVal as number)
          : (bVal as number) - (aVal as number)
      })
    }

    return result
  }, [catalogue, search, sortKey, sortOrder])

  const handleLaboChange = (value: string) => {
    setSearchParams({ labo: value })
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortOrder('asc')
    }
  }

  const SortIcon = ({ columnKey }: { columnKey: SortKey }) => {
    if (sortKey !== columnKey) {
      return <ArrowUpDown className="ml-1 h-3 w-3 opacity-50" />
    }
    return sortOrder === 'asc'
      ? <ArrowUp className="ml-1 h-3 w-3" />
      : <ArrowDown className="ml-1 h-3 w-3" />
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

  // Couleur du prix selon l'origine: noir=catalogue, bleu=bdpm, vert=bdm_it
  const getPriceSourceStyle = (prix_source: string | null | undefined) => {
    switch (prix_source) {
      case 'catalogue':
        return { color: '', title: 'Prix catalogue' }
      case 'bdpm':
        return { color: 'text-blue-600', title: 'Prix BDPM' }
      case 'bdm_it':
        return { color: 'text-emerald-600', title: 'Prix BDM-IT (CNAM)' }
      default:
        return { color: 'text-muted-foreground', title: 'Source inconnue' }
    }
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
            <>
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Rechercher un produit..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-10"
                />
              </div>
              {catalogue.length > 0 && (
                <Button
                  variant="destructive"
                  onClick={() => setClearDialogOpen(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Vider le catalogue
                </Button>
              )}
            </>
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
                Catalogue ({filteredAndSortedCatalogue.length} produits)
              </CardTitle>
              <CardDescription>
                Liste des produits du laboratoire
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px] text-muted-foreground">#</TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('code_cip')}
                    >
                      <span className="flex items-center">
                        Code CIP
                        <SortIcon columnKey="code_cip" />
                      </span>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('nom_commercial')}
                    >
                      <span className="flex items-center">
                        Designation
                        <SortIcon columnKey="nom_commercial" />
                      </span>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('molecule')}
                    >
                      <span className="flex items-center">
                        Molecule
                        <SortIcon columnKey="molecule" />
                      </span>
                    </TableHead>
                    <TableHead
                      className="text-right cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('prix_ht')}
                    >
                      <span className="flex items-center justify-end">
                        Prix HT
                        <SortIcon columnKey="prix_ht" />
                      </span>
                    </TableHead>
                    <TableHead
                      className="text-right cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('remise_pct')}
                    >
                      <span className="flex items-center justify-end">
                        Remise Ligne
                        <SortIcon columnKey="remise_pct" />
                      </span>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer hover:bg-muted/50 select-none"
                      onClick={() => handleSort('remontee_pct')}
                    >
                      <span className="flex items-center">
                        Remontee
                        <SortIcon columnKey="remontee_pct" />
                      </span>
                    </TableHead>
                    <TableHead>Matching</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAndSortedCatalogue.slice(0, DISPLAY_LIMIT).map((produit, index) => {
                    const status = getRemonteeStatus(produit.remontee_pct)
                    const priceStyle = getPriceSourceStyle(produit.prix_source)
                    const displayPrice = produit.prix_ht ?? produit.prix_fabricant
                    const groupeId = (produit as { groupe_generique_id?: number }).groupe_generique_id ||
                      (produit.presentation as { groupe_generique_id?: number } | null)?.groupe_generique_id
                    return (
                      <TableRow
                        key={produit.id}
                        className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'} ${groupeId ? 'cursor-pointer hover:bg-muted/50' : ''}`}
                        onClick={() => {
                          if (groupeId) {
                            setSelectedGroupe(groupeId)
                            setSelectedCip(produit.code_cip || undefined)
                          }
                        }}
                      >
                        <TableCell className="text-muted-foreground text-sm">{index + 1}</TableCell>
                        <TableCell className="font-mono text-sm">
                          <span className="flex items-center gap-2">
                            {produit.code_cip || '-'}
                            {produit.source === 'manuel' && (
                              <span className="px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded font-normal">
                                Manuel
                              </span>
                            )}
                          </span>
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
                          {displayPrice ? (
                            <span className={priceStyle.color} title={priceStyle.title}>
                              {formatCurrency(displayPrice)}
                            </span>
                          ) : '-'}
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
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteProduitMutation.mutate(produit.id)}
                            disabled={deleteProduitMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {filteredAndSortedCatalogue.length > DISPLAY_LIMIT && (
                <p className="text-center text-sm text-muted-foreground mt-4">
                  Affichage des {DISPLAY_LIMIT} premiers resultats sur {filteredAndSortedCatalogue.length}
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Dialog de confirmation pour vider le catalogue */}
        <Dialog open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Vider le catalogue</DialogTitle>
              <DialogDescription>
                Cette action va supprimer <strong>{catalogue.length} produits</strong> du catalogue.
                Cette action est irreversible.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <p className="text-sm text-muted-foreground mb-2">
                Pour confirmer, ecrivez <strong>oui</strong> ci-dessous:
              </p>
              <Input
                value={clearConfirmText}
                onChange={(e) => setClearConfirmText(e.target.value)}
                placeholder="Ecrivez oui pour confirmer"
              />
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setClearDialogOpen(false)
                  setClearConfirmText('')
                }}
              >
                Annuler
              </Button>
              <Button
                variant="destructive"
                onClick={() => clearCatalogueMutation.mutate()}
                disabled={clearConfirmText.toLowerCase() !== 'oui' || clearCatalogueMutation.isPending}
              >
                {clearCatalogueMutation.isPending ? 'Suppression...' : 'Vider le catalogue'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

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
