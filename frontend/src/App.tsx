import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Laboratoires } from '@/pages/Laboratoires'
import { Catalogues } from '@/pages/Catalogues'
import { MesVentes } from '@/pages/MesVentes'
import { Simulations } from '@/pages/Simulations'
import { SimulationIntelligente } from '@/pages/SimulationIntelligente'
import { MatchingDetails } from '@/pages/MatchingDetails'
import { Optimization } from '@/pages/Optimization'
import { Comparaison } from '@/pages/Comparaison'
import { Import } from '@/pages/Import'
import { Parametres } from '@/pages/Parametres'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/laboratoires" element={<Laboratoires />} />
            <Route path="/catalogues" element={<Catalogues />} />
            <Route path="/ventes" element={<MesVentes />} />
            <Route path="/simulations" element={<Simulations />} />
            <Route path="/simulation-intelligente" element={<SimulationIntelligente />} />
            <Route path="/matching-details/:importId/:laboId" element={<MatchingDetails />} />
            <Route path="/comparaison" element={<Comparaison />} />
            <Route path="/optimization" element={<Optimization />} />
            <Route path="/import" element={<Import />} />
            <Route path="/parametres" element={<Parametres />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
