import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Building2,
  Package,
  ShoppingCart,
  Calculator,
  GitCompare,
  Settings,
  FileSpreadsheet,
  Sparkles,
  Target,
  Database,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Laboratoires', href: '/laboratoires', icon: Building2 },
  { name: 'Catalogues', href: '/catalogues', icon: Package },
  { name: 'Mes Ventes', href: '/ventes', icon: ShoppingCart },
  { name: 'Repertoire Generique', href: '/repertoire', icon: Database },
  { name: 'Simulations', href: '/simulations', icon: Calculator },
  { name: 'Simulations Scenarios', href: '/simulation-intelligente', icon: Sparkles },
  { name: 'Comparaison', href: '/comparaison', icon: GitCompare },
  { name: 'Optimisation', href: '/optimization', icon: Target },
  { name: 'Import', href: '/import', icon: FileSpreadsheet },
  { name: 'Parametres', href: '/parametres', icon: Settings },
]

export function Sidebar() {
  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card">
      <div className="flex h-16 items-center border-b px-6">
        <h1 className="text-xl font-bold text-primary">Pharma Remises</h1>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </NavLink>
        ))}
      </nav>
      <div className="border-t p-4">
        <p className="text-xs text-muted-foreground">
          Simulation remises labos
        </p>
      </div>
    </div>
  )
}
