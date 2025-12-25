import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Plus, Pencil, Trash2, Package } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { laboratoiresApi } from '@/lib/api'
import type { Laboratoire, LaboratoireCreate } from '@/types'
import { formatPercent } from '@/lib/utils'
import { Link } from 'react-router-dom'

export function Laboratoires() {
  const [isOpen, setIsOpen] = useState(false)
  const [editingLabo, setEditingLabo] = useState<Laboratoire | null>(null)
  const [formData, setFormData] = useState<LaboratoireCreate>({
    nom: '',
    remise_negociee: 50,
    remise_ligne_defaut: 35,
    actif: true,
    notes: '',
  })

  const queryClient = useQueryClient()

  const { data: laboratoires = [], isLoading } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const createMutation = useMutation({
    mutationFn: laboratoiresApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['laboratoires'] })
      setIsOpen(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<LaboratoireCreate> }) =>
      laboratoiresApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['laboratoires'] })
      setIsOpen(false)
      setEditingLabo(null)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: laboratoiresApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['laboratoires'] })
    },
  })

  const resetForm = () => {
    setFormData({
      nom: '',
      remise_negociee: 50,
      remise_ligne_defaut: 35,
      actif: true,
      notes: '',
    })
  }

  const handleEdit = (labo: Laboratoire) => {
    setEditingLabo(labo)
    setFormData({
      nom: labo.nom,
      remise_negociee: labo.remise_negociee ?? 50,
      remise_ligne_defaut: labo.remise_ligne_defaut ?? 35,
      actif: labo.actif,
      notes: labo.notes || '',
    })
    setIsOpen(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingLabo) {
      updateMutation.mutate({ id: editingLabo.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleClose = () => {
    setIsOpen(false)
    setEditingLabo(null)
    resetForm()
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Laboratoires"
        description="Gerez vos laboratoires generiques"
      />

      <div className="flex-1 space-y-6 p-6">
        <div className="flex justify-between">
          <div>
            <p className="text-sm text-muted-foreground">
              {laboratoires.length} laboratoire{laboratoires.length > 1 ? 's' : ''} configure{laboratoires.length > 1 ? 's' : ''}
            </p>
          </div>
          <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => { setEditingLabo(null); resetForm(); }}>
                <Plus className="mr-2 h-4 w-4" />
                Ajouter un laboratoire
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingLabo ? 'Modifier le laboratoire' : 'Nouveau laboratoire'}
                  </DialogTitle>
                  <DialogDescription>
                    {editingLabo
                      ? 'Modifiez les informations du laboratoire'
                      : 'Ajoutez un nouveau laboratoire a comparer'}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="nom">Nom du laboratoire</Label>
                    <Input
                      id="nom"
                      value={formData.nom}
                      onChange={(e) => setFormData({ ...formData, nom: e.target.value })}
                      placeholder="Ex: Viatris, Zentiva, Biogaran..."
                      required
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label>
                      Remise negociee: {formData.remise_negociee}%
                    </Label>
                    <Slider
                      value={[formData.remise_negociee ?? 50]}
                      onValueChange={([value]) =>
                        setFormData({ ...formData, remise_negociee: value })
                      }
                      min={0}
                      max={70}
                      step={0.5}
                    />
                    <p className="text-xs text-muted-foreground">
                      Pourcentage de remontee negocie avec le laboratoire
                    </p>
                  </div>

                  <div className="grid gap-2">
                    <Label>
                      Remise ligne par defaut: {formData.remise_ligne_defaut}%
                    </Label>
                    <Slider
                      value={[formData.remise_ligne_defaut ?? 35]}
                      onValueChange={([value]) =>
                        setFormData({ ...formData, remise_ligne_defaut: value })
                      }
                      min={0}
                      max={60}
                      step={0.5}
                    />
                    <p className="text-xs text-muted-foreground">
                      Remise catalogue par defaut si non specifiee
                    </p>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="notes">Notes</Label>
                    <Input
                      id="notes"
                      value={formData.notes}
                      onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                      placeholder="Notes optionnelles..."
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={handleClose}>
                    Annuler
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                    {editingLabo ? 'Modifier' : 'Creer'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">
            Chargement...
          </div>
        ) : laboratoires.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Package className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Aucun laboratoire</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Commencez par ajouter un laboratoire a comparer
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Liste des laboratoires</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Remise Negociee</TableHead>
                    <TableHead>Remise Ligne Defaut</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {laboratoires.map((labo) => (
                    <TableRow key={labo.id}>
                      <TableCell className="font-medium">{labo.nom}</TableCell>
                      <TableCell>{formatPercent(labo.remise_negociee || 0)}</TableCell>
                      <TableCell>{formatPercent(labo.remise_ligne_defaut || 0)}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            labo.actif
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {labo.actif ? 'Actif' : 'Inactif'}
                        </span>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {labo.notes || '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            asChild
                            variant="outline"
                            size="sm"
                          >
                            <Link to={`/catalogues?labo=${labo.id}`}>
                              <Package className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEdit(labo)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => deleteMutation.mutate(labo.id)}
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
      </div>
    </div>
  )
}
