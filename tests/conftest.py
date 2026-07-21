
"""Shared pytest fixtures for repository and persistence tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.base import Base


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create an in-memory SQLite database for the test session."""

    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(
        bind=test_engine,
    )

    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(
            bind=test_engine,
        )
        test_engine.dispose()


@pytest.fixture
def session(
    engine: Engine,
) -> Generator[Session, None, None]:
    """Provide a fresh SQLAlchemy session for each test."""

    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )

    test_session = session_factory()

    try:
        yield test_session
    finally:
        test_session.rollback()
        test_session.close()
