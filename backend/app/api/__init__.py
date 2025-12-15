from .laboratoires import router as laboratoires_router
from .presentations import router as presentations_router
from .catalogues import router as catalogues_router
from .ventes import router as ventes_router
from .simulations import router as simulations_router
from .import_data import router as import_router
from .import_rapprochement import router as import_rapprochement_router
from .parametres import router as parametres_router
from .matching import router as matching_router
from .coverage import router as coverage_router
from .reports import router as reports_router
from .optimization import router as optimization_router

__all__ = [
    "laboratoires_router",
    "presentations_router",
    "catalogues_router",
    "ventes_router",
    "simulations_router",
    "import_router",
    "import_rapprochement_router",
    "parametres_router",
    "matching_router",
    "coverage_router",
    "reports_router",
    "optimization_router",
]
