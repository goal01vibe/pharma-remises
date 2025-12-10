import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import {
  Card,
  CardContent,
  CardDescription,
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
import { Plus, Play, Trash2, Eye, Calculator } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scenariosApi, laboratoiresApi, ventesApi } from '@/lib/api'
import type { ScenarioCreate } from '@/types'
import { formatPercent } from '@/lib/utils'
import { Link } from 'react-router-dom'

export function Simulations() {
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState<ScenarioCreate>({
    nom: '',
    description: '',
    laboratoire_id: 0,
    remise_simulee: 50,
  })

  const queryClient = useQueryClient()

  const { data: scenarios = [], isLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: scenariosApi.list,
  })

  const { data: laboratoires = [] } = useQuery({
    queryKey: ['laboratoires'],
    queryFn: laboratoiresApi.list,
  })

  const { data: ventesImports = [] } = useQuery({
    queryKey: ['ventes-imports'],
    queryFn: ventesApi.getImports,
  })

  const createMutation = useMutation({
    mutationFn: scenariosApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenarios'] })
      setIsOpen(false)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: scenariosApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenarios'] })
    },
  })

  const runMutation = useMutation({
    mutationFn: scenariosApi.run,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenarios'] })
    },
  })

  const resetForm = () => {
    setFormData({
      nom: '',
      description: '',
      laboratoire_id: 0,
      remise_simulee: 50,
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleLaboSelect = (laboId: string) => {
    const labo = laboratoires.find((l) => l.id === parseInt(laboId))
    setFormData({
      ...formData,
      laboratoire_id: parseInt(laboId),
      remise_simulee: labo?.remise_negociee || 50,
      nom: formData.nom || `Simulation ${labo?.nom || ''} ${new Date().toLocaleDateString('fr-FR')}`,
    })
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Simulations"
        description="Calculez et comparez les remises"
      />

      <div className="flex-1 space-y-6 p-6">
        <div className="flex justify-between">
          <div>
            <p className="text-sm text-muted-foreground">
              {scenarios.length} scenario{scenarios.length > 1 ? 's' : ''} enregistre{scenarios.length > 1 ? 's' : ''}
            </p>
          </div>
          <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
              <Button onClick={resetForm}>
                <Plus className="mr-2 h-4 w-4" />
                Nouveau scenario
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>Nouveau scenario de simulation</DialogTitle>
                  <DialogDescription>
                    Creez un scenario pour calculer les remises d'un laboratoire
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="laboratoire">Laboratoire</Label>
                    <Select
                      value={formData.laboratoire_id ? formData.laboratoire_id.toString() : ''}
                      onValueChange={handleLaboSelect}
                    >
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

                  <div className="grid gap-2">
                    <Label htmlFor="nom">Nom du scenario</Label>
                    <Input
                      id="nom"
                      value={formData.nom}
                      onChange={(e) => setFormData({ ...formData, nom: e.target.value })}
                      placeholder="Ex: Simulation Viatris 2024"
                      required
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label>
                      Remise negociee a simuler: {formData.remise_simulee}%
                    </Label>
                    <Slider
                      value={[formData.remise_simulee || 50]}
                      onValueChange={([value]) =>
                        setFormData({ ...formData, remise_simulee: value })
                      }
                      max={70}
                      step={0.5}
                    />
                    <p className="text-xs text-muted-foreground">
                      Pourcentage de remontee a utiliser pour ce scenario
                    </p>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="description">Description</Label>
                    <Input
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Description optionnelle..."
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>
                    Annuler
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending || !formData.laboratoire_id}>
                    Creer
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
        ) : scenarios.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Calculator className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Aucun scenario</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Creez votre premier scenario de simulation
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Scenarios de simulation</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Laboratoire</TableHead>
                    <TableHead>Remise Simulee</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {scenarios.map((scenario) => (
                    <TableRow key={scenario.id}>
                      <TableCell className="font-medium">{scenario.nom}</TableCell>
                      <TableCell>{scenario.laboratoire?.nom || '-'}</TableCell>
                      <TableCell>{formatPercent(scenario.remise_simulee || 0)}</TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {scenario.description || '-'}
                      </TableCell>
                      <TableCell>
                        {new Date(scenario.created_at).toLocaleDateString('fr-FR')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => runMutation.mutate(scenario.id)}
                            disabled={runMutation.isPending}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                          <Button
                            asChild
                            variant="outline"
                            size="sm"
                          >
                            <Link to={`/simulations/${scenario.id}`}>
                              <Eye className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => deleteMutation.mutate(scenario.id)}
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
