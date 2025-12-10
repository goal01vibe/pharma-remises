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
    notes: Optional[str] = None


class LaboratoireCreate(LaboratoireBase):
    pass


class LaboratoireUpdate(BaseModel):
    nom: Optional[str] = None
    remise_negociee: Optional[Decimal] = None
    remise_ligne_defaut: Optional[Decimal] = None
    actif: Optional[bool] = None
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
# MATCHING
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
