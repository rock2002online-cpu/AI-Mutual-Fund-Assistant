"""
Shared pytest fixtures for repository and persistence tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.base import Base


@pytest.fixture(scope="session")
def engine():
    """
    Create an in-memory SQLite database for the entire test session.
    """

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine) -> Session:
    """
    Provide a fresh SQLAlchemy Session for each test.

    Any uncommitted changes are rolled back automatically.
    """

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()