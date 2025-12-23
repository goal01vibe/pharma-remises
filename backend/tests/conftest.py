"""Pytest configuration and fixtures for tests."""
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use test database
DATABASE_URL_TEST = os.getenv(
    "DATABASE_URL_TEST",
    "postgresql://postgres:postgres@localhost:5433/pharma_remises_test"
)


@pytest.fixture(scope="session")
def engine():
    """Create database engine for test session."""
    return create_engine(DATABASE_URL_TEST)


@pytest.fixture(scope="function")
def db(engine) -> Session:
    """Create a new database session for each test with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
