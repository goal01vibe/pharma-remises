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
  CatalogueComparison,
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

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/catalogue/${id}`)
  },

  clearCatalogue: async (laboId: number): Promise<{ count: number }> => {
    const { data } = await api.delete(`/api/catalogue/laboratoire/${laboId}/clear`)
    return data
  },

  compare: async (labo1Id: number, labo2Id: number): Promise<CatalogueComparison> => {
    const { data } = await api.get(`/api/catalogue/compare/${labo1Id}/${labo2Id}`)
    return data
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
// MATCHING (Legacy)
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

// ===================
// MATCHING INTELLIGENT
// ===================
export interface ProcessSalesRequest {
  import_id: number
  min_score?: number
}

export interface ProcessSalesResponse {
  import_id: number
  total_ventes: number
  matching_results: {
    matched: number
    unmatched: number
    by_lab: Array<{
      lab_id: number
      lab_nom: string
      matched_count: number
      total_montant_matched: number
      couverture_pct: number
    }>
  }
  unmatched_products: Array<{
    vente_id: number
    designation: string
    montant: number
    candidates?: Array<{ lab: string; produit: string; score: number }>
  }>
  processing_time_s: number
}

export interface AnalyzeMatchRequest {
  designation: string
  code_cip?: string
}

export interface AnalyzeMatchResponse {
  extracted: {
    molecule?: string
    dosage?: string
    forme?: string
    conditionnement?: string
  }
  matches_by_lab: Array<{
    produit_id: number
    labo_id: number
    labo_nom: string
    nom_commercial: string
    code_cip?: string
    score: number
    match_type: string
    matched_on?: string
    prix_ht?: number
    remise_pct?: number
  }>
}

export interface MatchingStatsResponse {
  import_id: number
  total_ventes: number
  total_montant_ht: number
  matching_done: boolean
  matched_ventes?: number
  unmatched_ventes?: number
  by_lab?: Array<{
    lab_id: number
    lab_nom: string
    matched_count: number
    total_montant_matched: number
    couverture_count_pct: number
    couverture_montant_pct: number
    avg_match_score: number
  }>
}

export const intelligentMatchingApi = {
  processSales: async (request: ProcessSalesRequest): Promise<ProcessSalesResponse> => {
    const { data } = await api.post('/api/matching/process-sales', request)
    return data
  },

  analyze: async (request: AnalyzeMatchRequest): Promise<AnalyzeMatchResponse> => {
    const { data } = await api.post('/api/matching/analyze', request)
    return data
  },

  getStats: async (importId: number): Promise<MatchingStatsResponse> => {
    const { data } = await api.get(`/api/matching/stats/${importId}`)
    return data
  },

  clear: async (importId: number): Promise<{ deleted: number }> => {
    const { data } = await api.delete(`/api/matching/clear/${importId}`)
    return data
  },
}

// ===================
// SIMULATION WITH MATCHING
// ===================
export interface SimulationWithMatchingRequest {
  import_id: number
  labo_principal_id: number
  remise_negociee?: number
}

export interface SimulationLineResult {
  vente_id: number
  designation: string
  quantite: number
  montant_ht: number
  produit_id?: number
  produit_nom?: string
  disponible: boolean
  match_score?: number
  match_type?: string
  remise_ligne_pct?: number
  montant_remise_ligne?: number
  statut_remontee?: string
  remontee_cible?: number
  montant_remontee?: number
  remise_totale_pct?: number
  montant_total_remise?: number
}

export interface SimulationWithMatchingResponse {
  labo: Laboratoire
  totaux: TotauxSimulation
  details: SimulationLineResult[]
  matching_stats: {
    exact_cip: number
    groupe_generique: number
    fuzzy_molecule: number
    fuzzy_commercial: number
    no_match: number
    avg_score: number
  }
}

export const simulationWithMatchingApi = {
  run: async (request: SimulationWithMatchingRequest): Promise<SimulationWithMatchingResponse> => {
    const { data } = await api.post('/api/scenarios/run-with-matching', request)
    return data
  },
}

// ===================
// COVERAGE & BEST COMBO
// ===================
export interface LabRecoveryInfo {
  lab_id: number
  lab_nom: string
  chiffre_recupere_ht: number
  montant_remise_estime: number
  couverture_additionnelle_pct: number
  nb_produits_recuperes: number
  remise_negociee?: number
}

export interface BestComboResult {
  labs: Laboratoire[]
  couverture_totale_pct: number
  chiffre_total_realisable_ht: number
  montant_remise_total: number
}

export interface BestComboResponse {
  labo_principal: Laboratoire
  chiffre_perdu_ht: number
  nb_produits_perdus: number
  recommendations: LabRecoveryInfo[]
  best_combo?: BestComboResult
}

export interface CoverageGap {
  vente_id: number
  designation: string
  code_cip?: string
  montant_annuel: number
  quantite_annuelle?: number
  alternatives: Array<{
    labo_id: number
    labo_nom: string
    produit_id: number
    produit_nom: string
    match_score: number
    remise_negociee: number
  }>
}

export interface CoverageGapsResponse {
  labo_id: number
  labo_nom: string
  nb_produits_manquants: number
  total_montant_manquant_ht: number
  produits_avec_alternative: number
  produits_sans_alternative: number
  gaps: CoverageGap[]
}

export interface CoverageMatrixResponse {
  import_id: number
  total_ventes: number
  total_montant_ht: number
  individual_stats: Array<{
    labo_id: number
    labo_nom: string
    nb_matches: number
    couverture_count_pct: number
    montant_couvert_ht: number
    couverture_montant_pct: number
  }>
  combo_matrix: Array<{
    labo1_id: number
    labo1_nom: string
    labo2_id: number
    labo2_nom: string
    couverture_combo_pct: number
    overlap_count: number
    unique_labo1: number
    unique_labo2: number
    total_combo: number
  }>
}

export const coverageApi = {
  getBestCombo: async (laboPrincipalId: number, importId: number): Promise<BestComboResponse> => {
    const { data } = await api.get(`/api/coverage/best-combo/${laboPrincipalId}`, {
      params: { import_id: importId },
    })
    return data
  },

  getGaps: async (laboId: number, importId: number, limit?: number): Promise<CoverageGapsResponse> => {
    const { data } = await api.get(`/api/coverage/gaps/${laboId}`, {
      params: { import_id: importId, limit: limit || 50 },
    })
    return data
  },

  getMatrix: async (importId: number): Promise<CoverageMatrixResponse> => {
    const { data } = await api.get('/api/coverage/matrix', {
      params: { import_id: importId },
    })
    return data
  },
}

// ===================
// REPORTS
// ===================
export const reportsApi = {
  downloadSimulationPDF: async (
    importId: number,
    laboPrincipalId: number,
    pharmacieNom?: string
  ): Promise<Blob> => {
    const { data } = await api.get('/api/reports/simulation/pdf', {
      params: {
        import_id: importId,
        labo_principal_id: laboPrincipalId,
        pharmacie_nom: pharmacieNom || 'Ma Pharmacie',
      },
      responseType: 'blob',
    })
    return data
  },
}

export default api
