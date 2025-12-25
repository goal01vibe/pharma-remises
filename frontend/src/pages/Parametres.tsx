import { useState, useEffect } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Save } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { parametresApi } from '@/lib/api'

export function Parametres() {
  const queryClient = useQueryClient()

  const { data: parametres = [], isLoading } = useQuery({
    queryKey: ['parametres'],
    queryFn: parametresApi.list,
  })

  const [values, setValues] = useState<Record<string, string>>({})

  useEffect(() => {
    if (parametres.length > 0) {
      const initialValues: Record<string, string> = {}
      parametres.forEach((p) => {
        initialValues[p.cle] = p.valeur
      })
      setValues(initialValues)
    }
  }, [parametres])

  const updateMutation = useMutation({
    mutationFn: ({ cle, valeur }: { cle: string; valeur: string }) =>
      parametresApi.update(cle, valeur),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parametres'] })
    },
  })

  const handleSave = (cle: string) => {
    if (values[cle] !== undefined) {
      updateMutation.mutate({ cle, valeur: values[cle] })
    }
  }

  const handleChange = (cle: string, valeur: string) => {
    setValues((prev) => ({ ...prev, [cle]: valeur }))
  }

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <Header title="Parametres" description="Configuration de l'application" />
        <div className="p-6 text-center text-muted-foreground">Chargement...</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Parametres"
        description="Configuration de l'application"
      />

      <div className="flex-1 space-y-6 p-6">
        <Card>
          <CardHeader>
            <CardTitle>Conditionnements</CardTitle>
            <CardDescription>
              Configuration des equivalences de conditionnement
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="seuil_grand_conditionnement">
                Seuil grand conditionnement (unites)
              </Label>
              <div className="flex gap-2">
                <Input
                  id="seuil_grand_conditionnement"
                  type="number"
                  value={values['seuil_grand_conditionnement'] || '60'}
                  onChange={(e) => handleChange('seuil_grand_conditionnement', e.target.value)}
                  className="max-w-[200px]"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleSave('seuil_grand_conditionnement')}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Au-dela de ce nombre d'unites, un conditionnement est considere comme "grand"
              </p>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="equivalence_petit">
                Equivalences petits conditionnements
              </Label>
              <div className="flex gap-2">
                <Input
                  id="equivalence_petit"
                  value={values['equivalence_petit'] || '28,30'}
                  onChange={(e) => handleChange('equivalence_petit', e.target.value)}
                  placeholder="28,30,32"
                  className="max-w-[200px]"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleSave('equivalence_petit')}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Liste des conditionnements equivalents (separes par des virgules)
              </p>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="equivalence_grand">
                Equivalences grands conditionnements
              </Label>
              <div className="flex gap-2">
                <Input
                  id="equivalence_grand"
                  value={values['equivalence_grand'] || '84,90,100'}
                  onChange={(e) => handleChange('equivalence_grand', e.target.value)}
                  placeholder="84,90,100"
                  className="max-w-[200px]"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleSave('equivalence_grand')}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Liste des conditionnements equivalents (separes par des virgules)
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API OpenAI</CardTitle>
            <CardDescription>
              Configuration pour l'extraction PDF
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="openai_model_default">
                Modele par defaut
              </Label>
              <div className="flex gap-2">
                <Input
                  id="openai_model_default"
                  value={values['openai_model_default'] || 'gpt-4o-mini'}
                  onChange={(e) => handleChange('openai_model_default', e.target.value)}
                  className="max-w-[300px]"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleSave('openai_model_default')}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="openai_model_fallback">
                Modele de secours
              </Label>
              <div className="flex gap-2">
                <Input
                  id="openai_model_fallback"
                  value={values['openai_model_fallback'] || 'gpt-4o'}
                  onChange={(e) => handleChange('openai_model_fallback', e.target.value)}
                  className="max-w-[300px]"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleSave('openai_model_fallback')}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Utilise si le modele par defaut echoue ou a une confiance trop basse
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>A propos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              <strong>Pharma Remises</strong> - Simulation et comparaison de remises laboratoires
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              Version 1.0.0
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
