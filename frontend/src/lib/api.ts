import axios from 'axios'
import type {
  Laboratoire,
  LaboratoireCreate,
  Presentation,
  PresentationCreate,
  CatalogueProduit,
  CatalogueProduitCreate,
  Scenario,
  ScenarioCreate,
  ResultatSimulation,
  TotauxSimulation,
  ComparaisonScenarios,
  MesVentes,
  Import,
  ExtractionPDFResponse,
  Parametre,
  MatchingResult,
  PaginatedResponse,
  RegleRemontee,
  RegleRemonteeCreate,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8003'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ===================
// LABORATOIRES
// ===================
export const laboratoiresApi = {
  list: async (): Promise<Laboratoire[]> => {
    const { data } = await api.get('/api/laboratoires')
    return data
  },

  get: async (id: number): Promise<Laboratoire> => {
    const { data } = await api.get(`/api/laboratoires/${id}`)
    return data
  },

  create: async (labo: LaboratoireCreate): Promise<Laboratoire> => {
    const { data } = await api.post('/api/laboratoires', labo)
    return data
  },

  update: async (id: number, labo: Partial<LaboratoireCreate>): Promise<Laboratoire> => {
    const { data } = await api.put(`/api/laboratoires/${id}`, labo)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/laboratoires/${id}`)
  },

  getCatalogue: async (id: number): Promise<CatalogueProduit[]> => {
    const { data } = await api.get(`/api/laboratoires/${id}/catalogue`)
    return data
  },
}

// ===================
// PRESENTATIONS
// ===================
export const presentationsApi = {
  list: async (search?: string): Promise<Presentation[]> => {
    const params = search ? { search } : {}
    const { data } = await api.get('/api/presentations', { params })
    return data
  },

  get: async (id: number): Promise<Presentation> => {
    const { data } = await api.get(`/api/presentations/${id}`)
    return data
  },

  create: async (presentation: PresentationCreate): Promise<Presentation> => {
    const { data } = await api.post('/api/presentations', presentation)
    return data
  },

  search: async (query: string): Promise<MatchingResult[]> => {
    const { data } = await api.get('/api/presentations/search', { params: { q: query } })
    return data
  },
}

// ===================
// CATALOGUE PRODUITS
// ===================
export const catalogueApi = {
  list: async (laboId?: number): Promise<CatalogueProduit[]> => {
    const params = laboId ? { laboratoire_id: laboId } : {}
    const { data } = await api.get('/api/catalogue', { params })
    return data
  },

  get: async (id: number): Promise<CatalogueProduit> => {
    const { data } = await api.get(`/api/catalogue/${id}`)
    return data
  },

  create: async (produit: CatalogueProduitCreate): Promise<CatalogueProduit> => {
    const { data } = await api.post('/api/catalogue', produit)
    return data
  },

  update: async (id: number, produit: Partial<CatalogueProduitCreate>): Promise<CatalogueProduit> => {
    const { data } = await api.put(`/api/catalogue/${id}`, produit)
    return data
  },

  updateRemontee: async (id: number, remontee_pct: number | null): Promise<CatalogueProduit> => {
    const { data } = await api.patch(`/api/catalogue/${id}/remontee`, { remontee_pct })
    return data
  },

  bulkUpdateRemontee: async (ids: number[], remontee_pct: number | null): Promise<void> => {
    await api.patch('/api/catalogue/bulk/remontee', { ids, remontee_pct })
  },
}

// ===================
// REGLES REMONTEE
// ===================
export const reglesRemonteeApi = {
  list: async (laboId: number): Promise<RegleRemontee[]> => {
    const { data } = await api.get(`/api/laboratoires/${laboId}/regles-remontee`)
    return data
  },

  create: async (regle: RegleRemonteeCreate): Promise<RegleRemontee> => {
    const { data } = await api.post('/api/regles-remontee', regle)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/regles-remontee/${id}`)
  },

  addProduits: async (regleId: number, produitIds: number[]): Promise<void> => {
    await api.post(`/api/regles-remontee/${regleId}/produits`, { produit_ids: produitIds })
  },

  removeProduits: async (regleId: number, produitIds: number[]): Promise<void> => {
    await api.delete(`/api/regles-remontee/${regleId}/produits`, { data: { produit_ids: produitIds } })
  },
}

// ===================
// IMPORT FICHIERS
// ===================
export const importApi = {
  importCatalogue: async (file: File, laboId: number): Promise<Import> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('laboratoire_id', laboId.toString())
    const { data } = await api.post('/api/import/catalogue', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  importVentes: async (file: File): Promise<Import> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/api/import/ventes', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  extractPDF: async (
    file: File,
    options: { page_debut?: number; page_fin?: number; modele_ia: string }
  ): Promise<ExtractionPDFResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    if (options.page_debut) formData.append('page_debut', options.page_debut.toString())
    if (options.page_fin) formData.append('page_fin', options.page_fin.toString())
    formData.append('modele_ia', options.modele_ia)
    const { data } = await api.post('/api/import/extract-pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  getImportStatus: async (id: number): Promise<Import> => {
    const { data } = await api.get(`/api/import/${id}`)
    return data
  },
}

// ===================
// MES VENTES
// ===================
export const ventesApi = {
  list: async (importId?: number): Promise<MesVentes[]> => {
    const params = importId ? { import_id: importId } : {}
    const { data } = await api.get('/api/ventes', { params })
    return data
  },

  getImports: async (): Promise<Import[]> => {
    const { data } = await api.get('/api/import/ventes')
    return data
  },
}

// ===================
// SCENARIOS & SIMULATIONS
// ===================
export const scenariosApi = {
  list: async (): Promise<Scenario[]> => {
    const { data } = await api.get('/api/scenarios')
    return data
  },

  get: async (id: number): Promise<Scenario> => {
    const { data } = await api.get(`/api/scenarios/${id}`)
    return data
  },

  create: async (scenario: ScenarioCreate): Promise<Scenario> => {
    const { data } = await api.post('/api/scenarios', scenario)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/scenarios/${id}`)
  },

  run: async (id: number): Promise<void> => {
    await api.post(`/api/scenarios/${id}/run`)
  },

  getResultats: async (id: number): Promise<ResultatSimulation[]> => {
    const { data } = await api.get(`/api/scenarios/${id}/resultats`)
    return data
  },

  getTotaux: async (id: number): Promise<TotauxSimulation> => {
    const { data } = await api.get(`/api/scenarios/${id}/totaux`)
    return data
  },
}

// ===================
// COMPARAISON
// ===================
export const comparaisonApi = {
  compare: async (scenarioIds: number[]): Promise<ComparaisonScenarios> => {
    const { data } = await api.post('/api/comparaison', { scenario_ids: scenarioIds })
    return data
  },
}

// ===================
// PARAMETRES
// ===================
export const parametresApi = {
  list: async (): Promise<Parametre[]> => {
    const { data } = await api.get('/api/parametres')
    return data
  },

  get: async (cle: string): Promise<Parametre> => {
    const { data } = await api.get(`/api/parametres/${cle}`)
    return data
  },

  update: async (cle: string, valeur: string): Promise<Parametre> => {
    const { data } = await api.put(`/api/parametres/${cle}`, { valeur })
    return data
  },
}

// ===================
// MATCHING
// ===================
export const matchingApi = {
  autoMatch: async (produitId: number): Promise<MatchingResult> => {
    const { data } = await api.post(`/api/matching/auto/${produitId}`)
    return data
  },

  manualMatch: async (produitId: number, presentationId: number): Promise<void> => {
    await api.post('/api/matching/manual', { produit_id: produitId, presentation_id: presentationId })
  },

  getUnmatched: async (laboId: number): Promise<CatalogueProduit[]> => {
    const { data } = await api.get(`/api/matching/unmatched/${laboId}`)
    return data
  },
}

export default api
