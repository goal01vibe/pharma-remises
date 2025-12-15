from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from decimal import Decimal


# =====================
# LABORATOIRES
# =====================
class LaboratoireBase(BaseModel):
    nom: str
    remise_negociee: Optional[Decimal] = None
    remise_ligne_defaut: Optional[Decimal] = None
    actif: bool = True
    source: str = 'bdpm'  # 'csv' ou 'bdpm'
    notes: Optional[str] = None


class LaboratoireCreate(LaboratoireBase):
    pass


class LaboratoireUpdate(BaseModel):
    nom: Optional[str] = None
    remise_negociee: Optional[Decimal] = None
    remise_ligne_defaut: Optional[Decimal] = None
    actif: Optional[bool] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class LaboratoireResponse(LaboratoireBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# =====================
# PRESENTATIONS
# =====================
class PresentationBase(BaseModel):
    code_interne: str
    molecule: str
    dosage: Optional[str] = None
    forme: Optional[str] = None
    conditionnement: Optional[int] = None
    type_conditionnement: Optional[Literal["petit", "grand"]] = None
    classe_therapeutique: Optional[str] = None


class PresentationCreate(PresentationBase):
    pass


class PresentationResponse(PresentationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# =====================
# CATALOGUE PRODUITS
# =====================
class CatalogueProduitBase(BaseModel):
    laboratoire_id: int
    presentation_id: Optional[int] = None
    code_cip: Optional[str] = None
    code_acl: Optional[str] = None
    nom_commercial: Optional[str] = None
    prix_ht: Optional[Decimal] = None
    remise_pct: Optional[Decimal] = None
    remontee_pct: Optional[Decimal] = None
    actif: bool = True
    # Champs BDPM
    source: Optional[str] = 'bdpm'  # 'bdpm' ou 'manuel'
    groupe_generique_id: Optional[int] = None
    libelle_groupe: Optional[str] = None
    conditionnement: Optional[int] = None
    type_generique: Optional[str] = None  # 'princeps', 'generique', 'complementaire'
    prix_fabricant: Optional[Decimal] = None


class CatalogueProduitCreate(CatalogueProduitBase):
    pass


class CatalogueProduitUpdate(BaseModel):
    presentation_id: Optional[int] = None
    code_cip: Optional[str] = None
    code_acl: Optional[str] = None
    nom_commercial: Optional[str] = None
    prix_ht: Optional[Decimal] = None
    remise_pct: Optional[Decimal] = None
    remontee_pct: Optional[Decimal] = None
    actif: Optional[bool] = None


class CatalogueProduitResponse(CatalogueProduitBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    presentation: Optional[PresentationResponse] = None


# =====================
# REGLES REMONTEE
# =====================
class RegleRemonteeCreate(BaseModel):
    laboratoire_id: int
    nom_regle: str
    type_regle: Literal["exclusion", "partielle"]
    remontee_pct: Decimal
    produit_ids: Optional[List[int]] = None


class RegleRemonteeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    laboratoire_id: int
    nom_regle: str
    type_regle: str
    remontee_pct: Decimal
    created_at: datetime
    produits_count: Optional[int] = None


# =====================
# MES VENTES
# =====================
class MesVentesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_id: Optional[int] = None
    presentation_id: Optional[int] = None
    code_cip_achete: Optional[str] = None
    labo_actuel: Optional[str] = None
    designation: Optional[str] = None
    quantite_annuelle: Optional[int] = None
    prix_achat_unitaire: Optional[Decimal] = None
    montant_annuel: Optional[Decimal] = None
    created_at: datetime
    presentation: Optional[PresentationResponse] = None


# =====================
# IMPORTS
# =====================
class ImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_import: str
    nom: Optional[str] = None
    nom_fichier: Optional[str] = None
    laboratoire_id: Optional[int] = None
    nb_lignes_importees: Optional[int] = None
    nb_lignes_erreur: Optional[int] = None
    statut: str
    created_at: datetime


class LigneExtraite(BaseModel):
    code_cip: Optional[str] = None
    designation: Optional[str] = None
    prix_ht: Optional[float] = None
    remise_pct: Optional[float] = None
    confiance: float = 1.0


class ExtractionPDFRequest(BaseModel):
    page_debut: Optional[int] = 1
    page_fin: Optional[int] = None
    modele_ia: Literal["auto", "gpt-4o-mini", "gpt-4o"] = "auto"


class ExtractionPDFResponse(BaseModel):
    lignes: List[LigneExtraite]
    nb_pages_traitees: int
    modele_utilise: str
    temps_extraction_s: float
    raw_response: Optional[str] = None  # Réponse brute de l'IA pour debug


# =====================
# SCENARIOS & SIMULATIONS
# =====================
class ScenarioCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    laboratoire_id: int
    remise_simulee: Optional[Decimal] = None
    import_ventes_id: Optional[int] = None


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    description: Optional[str] = None
    laboratoire_id: int
    remise_simulee: Optional[Decimal] = None
    import_ventes_id: Optional[int] = None
    created_at: datetime
    laboratoire: Optional[LaboratoireResponse] = None


class ResultatSimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    presentation_id: Optional[int] = None
    quantite: Optional[int] = None
    montant_ht: Optional[Decimal] = None
    disponible: bool
    produit_id: Optional[int] = None
    remise_ligne: Optional[Decimal] = None
    montant_remise_ligne: Optional[Decimal] = None
    statut_remontee: Optional[str] = None
    remontee_cible: Optional[Decimal] = None
    montant_remontee: Optional[Decimal] = None
    remise_totale: Optional[Decimal] = None
    montant_total_remise: Optional[Decimal] = None
    created_at: datetime
    presentation: Optional[PresentationResponse] = None


class TotauxSimulation(BaseModel):
    # Montants HT
    chiffre_total_ht: Decimal
    chiffre_realisable_ht: Decimal
    chiffre_perdu_ht: Decimal
    chiffre_eligible_remontee_ht: Decimal
    chiffre_exclu_remontee_ht: Decimal
    # Remises
    total_remise_ligne: Decimal
    total_remontee: Decimal
    total_remise_globale: Decimal
    # Pourcentages
    taux_couverture: Decimal
    remise_ligne_moyenne: Decimal
    remise_totale_ponderee: Decimal
    # Comptages
    nb_produits_total: int
    nb_produits_disponibles: int
    nb_produits_manquants: int
    nb_produits_exclus: int
    nb_produits_eligibles: int
    nb_lignes_ignorees: int = 0  # Lignes sans prix BDPM ni prix labo


# =====================
# COMPARAISON
# =====================
class ScenarioTotaux(BaseModel):
    scenario: ScenarioResponse
    totaux: TotauxSimulation


class ComparaisonScenarios(BaseModel):
    scenarios: List[ScenarioTotaux]
    gagnant_id: int
    ecart_gain: Decimal


# =====================
# PARAMETRES
# =====================
class ParametreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cle: str
    valeur: Optional[str] = None
    description: Optional[str] = None
    updated_at: datetime


class ParametreUpdate(BaseModel):
    valeur: str


# =====================
# MATCHING (Legacy)
# =====================
class MatchCandidat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    presentation: PresentationResponse
    score: float
    source: Literal["auto", "manuel"]


class MatchingResult(BaseModel):
    produit_id: int
    designation: str
    candidats: List[MatchCandidat]
    statut: Literal["unique", "ambiguous", "new"]


# =====================
# MATCHING INTELLIGENT
# =====================
class MatchResultItem(BaseModel):
    """Resultat de matching pour un produit vers un labo."""
    produit_id: int
    labo_id: int
    labo_nom: str
    nom_commercial: str
    code_cip: Optional[str] = None
    score: float
    match_type: str  # 'exact_cip', 'groupe_generique', 'fuzzy_molecule', 'fuzzy_commercial'
    matched_on: Optional[str] = None  # Valeur qui a matche
    prix_ht: Optional[Decimal] = None
    remise_pct: Optional[Decimal] = None


class VenteMatchingItem(BaseModel):
    """Matching d'une vente vers plusieurs labos."""
    vente_id: int
    designation: str
    code_cip_achete: Optional[str] = None
    montant_annuel: Optional[Decimal] = None
    quantite_annuelle: Optional[int] = None
    matches: List[MatchResultItem]
    best_match: Optional[MatchResultItem] = None


class ProcessSalesRequest(BaseModel):
    """Request pour lancer le matching des ventes."""
    import_id: int
    min_score: float = 70.0  # Score minimum pour accepter un match
    labo_ids: list[int] | None = None  # Liste des labos a matcher (None = tous)


class LabMatchingSummary(BaseModel):
    """Resume matching pour un labo."""
    lab_id: int
    lab_nom: str
    matched_count: int
    total_montant_matched: Decimal
    couverture_pct: float


class ProcessSalesResponse(BaseModel):
    """Response du matching des ventes."""
    import_id: int
    total_ventes: int
    matching_results: dict  # matched, unmatched, by_lab, match_type_stats
    unmatched_products: List[dict]  # ventes sans match
    processing_time_s: float
    cached: bool = False  # True si resultat depuis le cache


class AnalyzeMatchRequest(BaseModel):
    """Request pour analyser le matching d'une designation."""
    designation: str
    code_cip: Optional[str] = None


class ExtractedComponents(BaseModel):
    """Composants extraits d'un nom de produit."""
    molecule: Optional[str] = None
    dosage: Optional[str] = None
    forme: Optional[str] = None
    conditionnement: Optional[str] = None


class AnalyzeMatchResponse(BaseModel):
    """Response de l'analyse de matching."""
    extracted: ExtractedComponents
    matches_by_lab: List[MatchResultItem]


# =====================
# SIMULATION WITH MATCHING
# =====================
class SimulationWithMatchingRequest(BaseModel):
    """Request pour simulation avec matching intelligent."""
    import_id: int
    labo_principal_id: int
    remise_negociee: Optional[Decimal] = None  # Override remise_negociee du labo


class SimulationLineResult(BaseModel):
    """Resultat simulation pour une ligne de vente."""
    vente_id: int
    designation: str
    quantite: int
    montant_ht: Decimal
    produit_id: Optional[int] = None
    produit_nom: Optional[str] = None
    disponible: bool
    match_score: Optional[float] = None
    match_type: Optional[str] = None
    # Prix pour indicateurs visuels
    prix_bdpm: Optional[Decimal] = None  # Prix BDPM de reference (marche)
    prix_labo: Optional[Decimal] = None  # Prix catalogue labo
    price_diff: Optional[Decimal] = None  # Ecart BDPM - labo (positif = BDPM plus cher)
    price_diff_pct: Optional[Decimal] = None  # Ecart en % du prix BDPM
    # Remises
    remise_ligne_pct: Optional[Decimal] = None
    montant_remise_ligne: Optional[Decimal] = None
    statut_remontee: Optional[str] = None  # 'normal', 'partiel', 'exclu', 'indisponible'
    remontee_cible: Optional[Decimal] = None
    montant_remontee: Optional[Decimal] = None
    remise_totale_pct: Optional[Decimal] = None
    montant_total_remise: Optional[Decimal] = None


class SimulationWithMatchingResponse(BaseModel):
    """Response simulation avec matching."""
    labo: LaboratoireResponse
    totaux: TotauxSimulation
    details: List[SimulationLineResult]
    matching_stats: dict  # Stats du matching utilise


# =====================
# COVERAGE & COMBO OPTIMIZER
# =====================
class LabRecoveryInfo(BaseModel):
    """Info de recuperation pour un labo complementaire."""
    lab_id: int
    lab_nom: str
    chiffre_recupere_ht: Decimal
    montant_remise_estime: Decimal
    couverture_additionnelle_pct: float
    nb_produits_recuperes: int
    remise_negociee: Optional[Decimal] = None


class BestComboResult(BaseModel):
    """Meilleure combinaison de labos."""
    labs: List[LaboratoireResponse]
    couverture_totale_pct: float
    chiffre_total_realisable_ht: Decimal
    montant_remise_total: Decimal


class BestComboResponse(BaseModel):
    """Response best combo pour le chiffre perdu."""
    labo_principal: LaboratoireResponse
    chiffre_perdu_ht: Decimal
    nb_produits_perdus: int
    recommendations: List[LabRecoveryInfo]
    best_combo: Optional[BestComboResult] = None


# =====================
# REPORTS
# =====================
class ReportRequest(BaseModel):
    """Request pour generer un rapport."""
    simulation_id: Optional[int] = None
    import_id: Optional[int] = None
    labo_principal_id: Optional[int] = None
    include_graphs: bool = True
    include_details: bool = True
