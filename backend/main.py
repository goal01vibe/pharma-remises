from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hooks for startup/shutdown."""
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


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


@app.get("/")
def root():
    return {"message": "Pharma Remises API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
