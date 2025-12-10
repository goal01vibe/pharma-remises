import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TrendingUp, TrendingDown, Package, AlertTriangle } from 'lucide-react'
import { formatCurrency, formatPercent } from '@/lib/utils'

interface KPICardsProps {
  remiseTotale: number
  tauxMoyen: number
  couverture: number
  chiffrePerdu: number
}

export function KPICards({ remiseTotale, tauxMoyen, couverture, chiffrePerdu }: KPICardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Remise Totale</CardTitle>
          <TrendingUp className="h-4 w-4 text-green-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-green-600">
            {formatCurrency(remiseTotale)}
          </div>
          <p className="text-xs text-muted-foreground">
            Gain annuel estime
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Taux Moyen</CardTitle>
          <TrendingUp className="h-4 w-4 text-blue-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-blue-600">
            {formatPercent(tauxMoyen)}
          </div>
          <p className="text-xs text-muted-foreground">
            Remise ponderee
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Couverture</CardTitle>
          <Package className="h-4 w-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {formatPercent(couverture)}
          </div>
          <p className="text-xs text-muted-foreground">
            Produits disponibles
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Chiffre Perdu</CardTitle>
          <AlertTriangle className="h-4 w-4 text-destructive" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-destructive">
            {formatCurrency(chiffrePerdu)}
          </div>
          <p className="text-xs text-muted-foreground">
            Produits manquants
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
