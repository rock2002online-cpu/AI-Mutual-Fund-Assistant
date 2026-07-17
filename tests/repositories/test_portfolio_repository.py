"""
Tests for PortfolioRepository.
"""

from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.base import Base
from models.portfolio import Portfolio
from repositories.portfolio_repository import PortfolioRepository


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def repository(session: Session) -> PortfolioRepository:
    return PortfolioRepository(session)


def create_portfolio(
    name: str,
    owner: str = "rohit",
    active: bool = True,
) -> Portfolio:
    return Portfolio(
        name=name,
        description="Test Portfolio",
        owner_reference=owner,
        base_currency="INR",
        is_active=active,
    )


def test_repository_initializes(
    repository: PortfolioRepository,
) -> None:
    assert repository.model is Portfolio


def test_add_portfolio(
    repository: PortfolioRepository,
) -> None:
    portfolio = create_portfolio("Growth")

    repository.add(portfolio)

    assert portfolio.id is not None


def test_get_active(
    repository: PortfolioRepository,
) -> None:
    repository.add(create_portfolio("P1", active=True))
    repository.add(create_portfolio("P2", active=True))
    repository.add(create_portfolio("P3", active=False))

    results = repository.get_active()

    assert len(results) == 2


def test_get_by_owner(
    repository: PortfolioRepository,
) -> None:
    repository.add(create_portfolio("A", owner="rohit"))
    repository.add(create_portfolio("B", owner="rohit"))
    repository.add(create_portfolio("C", owner="alice"))

    results = repository.get_by_owner("rohit")

    assert len(results) == 2


def test_get_by_name(
    repository: PortfolioRepository,
) -> None:
    repository.add(create_portfolio("Retirement"))

    result = repository.get_by_name("Retirement")

    assert result is not None
    assert result.name == "Retirement"


def test_get_by_name_returns_none(
    repository: PortfolioRepository,
) -> None:
    assert repository.get_by_name("Unknown") is None


def test_inherited_count(
    repository: PortfolioRepository,
) -> None:
    repository.add(create_portfolio("A"))
    repository.add(create_portfolio("B"))

    assert repository.count() == 2


def test_inherited_exists(
    repository: PortfolioRepository,
) -> None:
    portfolio = create_portfolio("Growth")

    repository.add(portfolio)

    assert repository.exists(portfolio.id)


def test_inherited_get_all(
    repository: PortfolioRepository,
) -> None:
    repository.add(create_portfolio("One"))
    repository.add(create_portfolio("Two"))

    assert len(repository.get_all()) == 2