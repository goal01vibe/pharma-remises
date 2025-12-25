from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from typing import Generator
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/pharma_remises"
)

# Configuration du pool de connexions pour de meilleures performances
engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=10,           # Nombre de connexions maintenues
    max_overflow=20,        # Connexions supplémentaires si besoin
    pool_pre_ping=True,     # Vérifie la connexion avant utilisation
    pool_recycle=3600,      # Recycle les connexions après 1h
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
