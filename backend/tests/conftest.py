"""Pytest configuration and fixtures for tests."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
