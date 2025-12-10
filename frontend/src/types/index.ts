// Types pour l'application Pharma Remises

// ===================
// LABORATOIRES
// ===================
export interface Laboratoire {
  id: number
  nom: string
  remise_negociee: number | null
  remise_ligne_defaut: number | null
  actif: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface LaboratoireCreate {
  nom: string
  remise_negociee?: number
  remise_ligne_defaut?: number
  actif?: boolean
  notes?: string
}

// ===================
// PRESENTATIONS (CODE INTERNE)
// ===================
export interface Presentation {
  id: number
  code_interne: string
  molecule: string
  dosage: string | null
  forme: string | null
  conditionnement: number | null
  type_conditionnement: 'petit' | 'grand' | null
  classe_therapeutique: string | null
  created_at: string
}

export interface PresentationCreate {
  code_interne: string
  molecule: string
  dosage?: string
  forme?: string
  conditionnement?: number
  type_conditionnement?: 'petit' | 'grand'
  classe_therapeutique?: string
}

// ===================
// CATALOGUE PRODUITS
// ===================
export interface CatalogueProduit {
  id: number
  laboratoire_id: number
  presentation_id: number | null
  code_cip: string | null
  code_acl: string | null
  nom_commercial: string | null
  prix_ht: number | null
  remise_pct: number | null
  remontee_pct: number | null  // null = normal, 0 = exclu, X = partiel
  actif: boolean
  created_at: string
  updated_at: string
  // Relations
  presentation?: Presentation
  laboratoire?: Laboratoire
}

export interface CatalogueProduitCreate {
  laboratoire_id: number
  presentation_id?: number
  code_cip?: string
  code_acl?: string
  nom_commercial?: string
  prix_ht?: number
  remise_pct?: number
  remontee_pct?: number
  actif?: boolean
}

// ===================
// REGLES REMONTEE
// ===================
export interface RegleRemontee {
  id: number
  laboratoire_id: number
  nom_regle: string
  type_regle: 'exclusion' | 'partielle'
  remontee_pct: number
  created_at: string
  produits_count?: number
}

export interface RegleRemonteeCreate {
  laboratoire_id: number
  nom_regle: string
  type_regle: 'exclusion' | 'partielle'
  remontee_pct: number
  produit_ids?: number[]
}

// ===================
// MES VENTES
// ===================
export interface MesVentes {
  id: number
  import_id: number
  presentation_id: number | null
  code_cip_achete: string | null
  labo_actuel: string | null
  designation: string | null
  quantite_annuelle: number | null
  prix_achat_unitaire: number | null
  montant_annuel: number | null
  created_at: string
  // Relations
  presentation?: Presentation
}

// ===================
// IMPORTS
// ===================
export interface Import {
  id: number
  type_import: 'catalogue' | 'ventes'
  nom_fichier: string
  laboratoire_id: number | null
  nb_lignes_importees: number | null
  nb_lignes_erreur: number | null
  statut: 'en_cours' | 'termine' | 'erreur'
  created_at: string
}

// ===================
// SCENARIOS & SIMULATIONS
// ===================
export interface Scenario {
  id: number
  nom: string
  description: string | null
  laboratoire_id: number
  remise_simulee: number | null
  import_ventes_id: number | null
  created_at: string
  // Relations
  laboratoire?: Laboratoire
}

export interface ScenarioCreate {
  nom: string
  description?: string
  laboratoire_id: number
  remise_simulee?: number
  import_ventes_id?: number
}

export interface ResultatSimulation {
  id: number
  scenario_id: number
  presentation_id: number
  quantite: number | null
  montant_ht: number | null
  disponible: boolean
  produit_id: number | null
  remise_ligne: number | null
  montant_remise_ligne: number | null
  statut_remontee: 'normal' | 'partiel' | 'exclu' | 'indisponible'
  remontee_cible: number | null
  montant_remontee: number | null
  remise_totale: number | null
  montant_total_remise: number | null
  created_at: string
  // Relations
  presentation?: Presentation
  produit?: CatalogueProduit
}

// ===================
// TOTAUX SIMULATION
// ===================
export interface TotauxSimulation {
  // Montants HT
  chiffre_total_ht: number
  chiffre_realisable_ht: number
  chiffre_perdu_ht: number
  chiffre_eligible_remontee_ht: number
  chiffre_exclu_remontee_ht: number
  // Remises
  total_remise_ligne: number
  total_remontee: number
  total_remise_globale: number
  // Pourcentages
  taux_couverture: number
  remise_ligne_moyenne: number
  remise_totale_ponderee: number
  // Comptages
  nb_produits_total: number
  nb_produits_disponibles: number
  nb_produits_manquants: number
  nb_produits_exclus: number
  nb_produits_eligibles: number
}

// ===================
// COMPARAISON
// ===================
export interface ComparaisonScenarios {
  scenarios: {
    scenario: Scenario
    totaux: TotauxSimulation
  }[]
  gagnant_id: number
  ecart_gain: number
}

// ===================
// IMPORT PDF / EXTRACTION IA
// ===================
export interface ExtractionPDFRequest {
  fichier: File
  page_debut?: number
  page_fin?: number
  modele_ia: 'auto' | 'gpt-4o-mini' | 'gpt-4o'
}

export interface LigneExtraite {
  code_cip: string | null
  designation: string | null
  prix_ht: number | null
  remise_pct: number | null
  confiance: number  // 0-1
}

export interface ExtractionPDFResponse {
  lignes: LigneExtraite[]
  nb_pages_traitees: number
  modele_utilise: string
  temps_extraction_s: number
}

// ===================
// PARAMETRES
// ===================
export interface Parametre {
  cle: string
  valeur: string
  description: string | null
  updated_at: string
}

// ===================
// MATCHING
// ===================
export interface MatchCandidat {
  presentation: Presentation
  score: number
  source: 'auto' | 'manuel'
}

export interface MatchingResult {
  produit_id: number
  designation: string
  candidats: MatchCandidat[]
  statut: 'unique' | 'ambiguous' | 'new'
}

// ===================
// API RESPONSES
// ===================
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ApiError {
  detail: string
  status_code: number
}
