from .simulation import run_simulation, calculate_totaux
from .pdf_extraction import extract_catalogue_from_pdf
from .matching import auto_match_product, find_presentation_candidates

# Nouveaux services Phase 2
from .pharma_preprocessing import preprocess_pharma, extract_labo_from_denomination
from .batch_matching import batch_match_products
from .matching_service import MatchingService
from .audit_logger import AuditLogger
from .auto_validation import should_auto_validate, get_validation_threshold, get_validation_config
from .materialized_views import MaterializedViewService

__all__ = [
    # Services existants
    "run_simulation",
    "calculate_totaux",
    "extract_catalogue_from_pdf",
    "auto_match_product",
    "find_presentation_candidates",
    # Nouveaux services Phase 2
    "preprocess_pharma",
    "extract_labo_from_denomination",
    "batch_match_products",
    "MatchingService",
    "AuditLogger",
    "should_auto_validate",
    "get_validation_threshold",
    "get_validation_config",
    "MaterializedViewService",
]
