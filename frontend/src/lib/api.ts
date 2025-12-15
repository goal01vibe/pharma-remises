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
  RegleRemontee,
  RegleRemonteeCreate,
  CatalogueComparison,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8847'

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

  importVentes: async (file: File, nom?: string): Promise<Import> => {
    const formData = new FormData()
    formData.append('file', file)
    if (nom) {
      formData.append('nom', nom)
    }
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
export interface IncompleteCountResponse {
  total: number
  complete: number
  incomplete: number
  completion_rate: number
}

export const ventesApi = {
  list: async (importId?: number): Promise<MesVentes[]> => {
    const params = importId ? { import_id: importId } : {}
    const { data } = await api.get('/api/ventes', { params })
    return data
  },

  getImports: async (): Promise<Import[]> => {
    const { data } = await api.get('/api/ventes/imports')
    return data
  },

  deleteImport: async (importId: number): Promise<void> => {
    await api.delete(`/api/import/ventes/${importId}`)
  },

  deleteVente: async (venteId: number): Promise<void> => {
    await api.delete(`/api/ventes/${venteId}`)
  },

  // Gestion des ventes incompletes (sans prix BDPM)
  getIncomplete: async (importId: number): Promise<MesVentes[]> => {
    const { data } = await api.get('/api/ventes/incomplete', { params: { import_id: importId } })
    return data
  },

  getIncompleteCount: async (importId: number): Promise<IncompleteCountResponse> => {
    const { data } = await api.get('/api/ventes/incomplete/count', { params: { import_id: importId } })
    return data
  },

  deleteIncomplete: async (importId: number): Promise<{ success: boolean; deleted: number }> => {
    const { data } = await api.delete('/api/ventes/incomplete/bulk', { params: { import_id: importId } })
    return data
  },

  reEnrich: async (importId: number): Promise<{ success: boolean; stats: Record<string, number> }> => {
    const { data } = await api.post(`/api/ventes/re-enrich/${importId}`)
    return data
  },

  deleteByIds: async (venteIds: number[]): Promise<{ success: boolean; deleted: number }> => {
    const { data } = await api.delete('/api/ventes/bulk/by-ids', { data: venteIds })
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
  labo_ids?: number[]  // Liste des labos a matcher (si vide = tous)
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

// Types pour les details de matching
export interface MatchingDetailItem {
  vente_id: number
  matched: boolean
  // Infos vente
  vente_designation: string | null
  vente_code_cip: string | null
  vente_quantite: number | null
  vente_labo_actuel: string | null
  // Infos produit matche
  produit_id: number | null
  produit_nom: string | null
  produit_code_cip: string | null
  produit_prix_ht: number | null
  produit_remise_pct: number | null
  produit_groupe_generique_id: number | null
  produit_libelle_groupe: string | null
  // Infos matching
  match_score: number | null
  match_type: string | null
  matched_on: string | null
}

export interface MatchingDetailsResponse {
  import_id: number
  labo_id: number
  labo_nom: string
  total_ventes: number
  matched_count: number
  unmatched_count: number
  couverture_pct: number
  details: MatchingDetailItem[]
}

export interface SearchProductResult {
  id: number
  nom_commercial: string | null
  code_cip: string | null
  prix_ht: number | null
  remise_pct: number | null
  groupe_generique_id: number | null
  libelle_groupe: string | null
}

export interface SearchProductsResponse {
  labo_id: number
  labo_nom: string
  query: string
  results: SearchProductResult[]
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

  // Details du matching pour un import et un labo
  getDetails: async (importId: number, laboId: number): Promise<MatchingDetailsResponse> => {
    const { data } = await api.get(`/api/matching/details/${importId}/${laboId}`)
    return data
  },

  // Recherche de produits dans un labo
  searchProducts: async (laboId: number, query: string): Promise<SearchProductsResponse> => {
    const { data } = await api.get(`/api/matching/search-products/${laboId}`, {
      params: { q: query },
    })
    return data
  },

  // Correction manuelle d'un matching
  setManualMatch: async (venteId: number, laboId: number, produitId: number): Promise<{ success: boolean; message: string }> => {
    const { data } = await api.put(`/api/matching/manual/${venteId}/${laboId}`, null, {
      params: { produit_id: produitId },
    })
    return data
  },

  // Supprimer un matching
  deleteMatch: async (venteId: number, laboId: number): Promise<{ success: boolean; deleted: number }> => {
    const { data } = await api.delete(`/api/matching/manual/${venteId}/${laboId}`)
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
  // Prix pour indicateurs visuels
  prix_bdpm?: number
  prix_labo?: number
  price_diff?: number  // Ecart BDPM - labo (positif = BDPM plus cher)
  price_diff_pct?: number  // Ecart en % du prix BDPM
  // Remises
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

// ===================
// IMPORT AVEC RAPPROCHEMENT
// ===================
export interface ImportPreviewChange {
  champ: string
  ancien: number | null
  nouveau: number | null
}

export interface ImportPreviewItem {
  ligne: number
  code_cip: string | null
  designation: string | null
  prix_ht_import: number | null
  remise_pct_import: number | null
  match_type: string
  match_score: number
  produit_id?: number
  nom_existant?: string
  code_cip_existant?: string
  prix_ht_existant?: number | null
  remise_pct_existant?: number | null
  changes?: ImportPreviewChange[]
}

export interface ImportPreviewResponse {
  preview_id: string
  laboratoire: {
    id: number
    nom: string
  }
  colonnes_detectees: Record<string, string>
  total_lignes_fichier: number
  total_produits_existants: number
  resume: {
    nouveaux: number
    mis_a_jour: number
    inchanges: number
    erreurs: number
  }
  nouveaux: ImportPreviewItem[]
  mis_a_jour: ImportPreviewItem[]
  inchanges: ImportPreviewItem[]
  erreurs: Array<{ ligne: number; erreur: string }>
}

export interface ImportConfirmRequest {
  apply_nouveaux?: boolean
  apply_updates?: boolean
  update_ids?: number[]
}

export interface ImportConfirmResponse {
  success: boolean
  laboratoire_id: number
  produits_crees: number
  produits_maj: number
  message: string
}

export const importRapprochementApi = {
  preview: async (file: File, laboId: number): Promise<ImportPreviewResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('laboratoire_id', laboId.toString())
    const { data } = await api.post('/api/import/catalogue/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  confirm: async (previewId: string, actions?: ImportConfirmRequest): Promise<ImportConfirmResponse> => {
    const { data } = await api.post(`/api/import/catalogue/confirm/${previewId}`, actions || {})
    return data
  },

  cancel: async (previewId: string): Promise<void> => {
    await api.delete(`/api/import/catalogue/preview/${previewId}`)
  },
}

// ===================
// OPTIMIZATION MULTI-LABOS
// ===================
export interface LaboObjectiveInput {
  labo_id: number
  objectif_pct?: number  // Ex: 60 = 60% du potentiel
  objectif_montant?: number  // Ex: 30000 euros min
  exclusions?: number[]  // Liste de produit_ids a exclure
}

export interface OptimizeRequest {
  import_id: number
  objectives: LaboObjectiveInput[]
  max_time_seconds?: number
}

export interface LaboDisponible {
  labo_id: number
  labo_nom: string
  remise_negociee: number
  nb_matchings: number
  potentiel_ht: number
}

export interface LaboRepartition {
  labo_id: number
  labo_nom: string
  chiffre_ht: number
  remise_totale: number
  nb_produits: number
  objectif_atteint: boolean
  objectif_minimum: number
  potentiel_ht: number
  ventes?: Array<{
    vente_id: number
    designation: string
    produit_id: number
    produit_nom: string
    quantite: number
    prix_unitaire: number
    montant_ht: number
    remise_pct: number
    gain_remise: number
  }>
}

export interface OptimizeResponse {
  success: boolean
  message: string
  repartition: LaboRepartition[]
  chiffre_total_ht: number
  remise_totale: number
  couverture_pct: number
  solver_time_ms: number
  status: string
}

export interface ProduitLabo {
  id: number
  nom_commercial: string
  code_cip?: string
  prix_ht: number
  remise_pct: number
}

export interface PreviewLaboInfo {
  labo_id: number
  labo_nom: string
  remise_negociee: number
  potentiel_ht: number
  nb_produits_matches: number
  nb_exclusions: number
  objectif_pct?: number
  objectif_montant?: number
  objectif_minimum_calcule: number
  realisable: boolean
}

export interface PreviewResponse {
  import_id: number
  nb_ventes: number
  labos: PreviewLaboInfo[]
  total_potentiel_ht: number
  total_objectifs_ht: number
  tous_realisables: boolean
  message: string
}

export const optimizationApi = {
  getLabosDisponibles: async (importId: number): Promise<{ import_id: number; nb_ventes: number; labos: LaboDisponible[] }> => {
    const { data } = await api.get('/api/optimization/labos-disponibles', { params: { import_id: importId } })
    return data
  },

  getProduitsLabo: async (importId: number, laboId: number, search?: string): Promise<{ labo_id: number; labo_nom: string; produits: ProduitLabo[] }> => {
    const params: Record<string, unknown> = { import_id: importId, labo_id: laboId }
    if (search) params.search = search
    const { data } = await api.get('/api/optimization/produits-labo', { params })
    return data
  },

  preview: async (request: OptimizeRequest): Promise<PreviewResponse> => {
    const { data } = await api.post('/api/optimization/preview', request)
    return data
  },

  run: async (request: OptimizeRequest, includeVentes?: boolean): Promise<OptimizeResponse> => {
    const { data } = await api.post('/api/optimization/run', request, {
      params: { include_ventes: includeVentes || false },
    })
    return data
  },
}
