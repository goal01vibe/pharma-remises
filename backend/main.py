from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env (racine du projet)
load_dotenv(dotenv_path="../.env")

from app.db import engine, Base
from app.api import (
    laboratoires_router,
    presentations_router,
    catalogues_router,
    ventes_router,
    simulations_router,
    import_router,
    import_rapprochement_router,
    parametres_router,
    matching_router,
    coverage_router,
    reports_router,
    optimization_router,
    repertoire_router,
)
from app.api.groupe import router as groupe_router
from app.api.validations import router as validations_router
from app.api.prix import router as prix_router
from app.api.admin import router as admin_router
from app.db import get_db


# =============================================================================
# MIDDLEWARE : Blocage si validations en attente (avec cache)
# =============================================================================
import time

class PendingValidationsMiddleware(BaseHTTPMiddleware):
    """
    Middleware qui bloque certains endpoints si des validations sont en attente.
    Utilise un cache de 30 secondes pour éviter de requêter la DB à chaque appel.
    """

    BLOCKED_PATHS = [
        "/api/simulations/",
        "/api/rapprochement/",
        "/api/simulation-intelligent",
    ]

    # Cache simple pour éviter les requêtes répétées
    _cache = {"count": 0, "timestamp": 0}
    _cache_ttl = 30  # 30 secondes

    async def dispatch(self, request: Request, call_next):
        # Ne bloquer que les POST (pas les GET)
        if request.method != "POST":
            return await call_next(request)

        # Vérifier si le path est bloqué
        path = request.url.path
        is_blocked_path = any(path.startswith(bp) for bp in self.BLOCKED_PATHS)

        if not is_blocked_path:
            return await call_next(request)

        # Vérifier le cache
        now = time.time()
        if now - self._cache["timestamp"] < self._cache_ttl:
            pending_count = self._cache["count"]
        else:
            # Requête DB et mise en cache
            try:
                db = next(get_db())
                from sqlalchemy import text
                pending_count = db.execute(
                    text("SELECT COUNT(*) FROM pending_validations WHERE validated_at IS NULL")
                ).scalar() or 0
                db.close()
                self._cache = {"count": pending_count, "timestamp": now}
            except Exception:
                pending_count = 0

        if pending_count > 0:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "pending_validations",
                    "message": f"{pending_count} validation(s) en attente. Veuillez les traiter avant de continuer.",
                    "pending_count": pending_count
                }
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hooks for startup/shutdown."""
    # Startup - Warm up la connexion DB pour le premier appel rapide
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))  # Premier ping rapide
    yield
    # Shutdown - Fermer proprement le pool
    engine.dispose()


app = FastAPI(
    title="Pharma Remises API",
    description="API pour la simulation et comparaison des remises laboratoires",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de blocage si validations en attente
app.add_middleware(PendingValidationsMiddleware)

# Routers
app.include_router(laboratoires_router)
app.include_router(presentations_router)
app.include_router(catalogues_router)
app.include_router(ventes_router)
app.include_router(simulations_router)
app.include_router(import_router)
app.include_router(import_rapprochement_router)
app.include_router(parametres_router)
app.include_router(matching_router)
app.include_router(coverage_router)
app.include_router(reports_router)
app.include_router(optimization_router)
app.include_router(repertoire_router)
app.include_router(groupe_router)
app.include_router(validations_router)
app.include_router(prix_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {"message": "Pharma Remises API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
