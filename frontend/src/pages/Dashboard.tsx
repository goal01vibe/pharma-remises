import { Header } from '@/components/layout/Header'
import { KPICards } from '@/components/dashboard/KPICards'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'
import { Plus, FileSpreadsheet, Calculator } from 'lucide-react'

export function Dashboard() {
  // TODO: Charger depuis l'API
  const mockKPIs = {
    remiseTotale: 47700,
    tauxMoyen: 53,
    couverture: 90,
    chiffrePerdu: 10000,
  }

  return (
    <div className="flex flex-col">
      <Header
        title="Dashboard"
        description="Vue d'ensemble de vos simulations de remises"
      />

      <div className="flex-1 space-y-6 p-6">
        <KPICards {...mockKPIs} />

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Actions Rapides</CardTitle>
              <CardDescription>
                Demarrer une nouvelle simulation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button asChild className="w-full justify-start">
                <Link to="/laboratoires">
                  <Plus className="mr-2 h-4 w-4" />
                  Ajouter un laboratoire
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/import">
                  <FileSpreadsheet className="mr-2 h-4 w-4" />
                  Importer un catalogue
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/simulations">
                  <Calculator className="mr-2 h-4 w-4" />
                  Nouvelle simulation
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Laboratoires</CardTitle>
              <CardDescription>
                Laboratoires configures
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">0</div>
              <p className="text-sm text-muted-foreground">
                Aucun laboratoire configure
              </p>
              <Button asChild variant="link" className="mt-2 px-0">
                <Link to="/laboratoires">Gerer les laboratoires</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Simulations</CardTitle>
              <CardDescription>
                Scenarios enregistres
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">0</div>
              <p className="text-sm text-muted-foreground">
                Aucune simulation
              </p>
              <Button asChild variant="link" className="mt-2 px-0">
                <Link to="/simulations">Voir les simulations</Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Guide de demarrage</CardTitle>
            <CardDescription>
              Suivez ces etapes pour configurer votre premiere simulation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="list-inside list-decimal space-y-2 text-sm">
              <li className="text-muted-foreground">
                <span className="font-medium text-foreground">Ajouter un laboratoire</span>
                {' - '} Creez une fiche pour chaque labo que vous souhaitez comparer
              </li>
              <li className="text-muted-foreground">
                <span className="font-medium text-foreground">Importer le catalogue</span>
                {' - '} Importez le catalogue de chaque labo (Excel, CSV ou PDF)
              </li>
              <li className="text-muted-foreground">
                <span className="font-medium text-foreground">Importer vos ventes</span>
                {' - '} Chargez votre historique de ventes annuel
              </li>
              <li className="text-muted-foreground">
                <span className="font-medium text-foreground">Lancer une simulation</span>
                {' - '} Calculez les remises pour chaque scenario
              </li>
              <li className="text-muted-foreground">
                <span className="font-medium text-foreground">Comparer les resultats</span>
                {' - '} Visualisez quel labo vous rapporte le plus
              </li>
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
