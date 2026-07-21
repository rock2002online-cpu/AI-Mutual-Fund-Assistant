"""
Tests for FundRepository.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.base import Base
from models.fund import Fund
from repositories.fund_repository import FundRepository


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session."""

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
def repository(session: Session) -> FundRepository:
    """Provide a FundRepository."""

    return FundRepository(session)


def create_fund(
    scheme_code: str,
    name: str,
    amc: str = "HDFC",
    category: str = "Equity",
) -> Fund:
    """Create a Fund instance."""

    return Fund(
        scheme_code=scheme_code,
        name=name,
        amc=amc,
        category=category,
        plan="Direct",
        option="Growth",
    )


def test_repository_initializes(
    repository: FundRepository,
) -> None:
    """Repository should initialize correctly."""

    assert repository.model is Fund


def test_add_fund(
    repository: FundRepository,
) -> None:
    """A fund should be persisted."""

    fund = create_fund(
        "100001",
        "HDFC Flexi Cap Fund",
    )

    repository.add(fund)

    assert fund.id is not None


def test_get_by_scheme_code(
    repository: FundRepository,
) -> None:
    """Lookup by AMFI scheme code."""

    fund = create_fund(
        "100002",
        "ICICI Bluechip Fund",
    )

    repository.add(fund)

    result = repository.get_by_scheme_code(
        "100002",
    )

    assert result is not None
    assert result.scheme_code == "100002"


def test_get_by_scheme_code_returns_none(
    repository: FundRepository,
) -> None:
    """Unknown scheme code returns None."""

    assert (
        repository.get_by_scheme_code(
            "999999",
        )
        is None
    )


def test_search_by_name(
    repository: FundRepository,
) -> None:
    """Search by partial fund name."""

    repository.add(
        create_fund(
            "100010",
            "HDFC Flexi Cap Fund",
        )
    )

    repository.add(
        create_fund(
            "100011",
            "HDFC Balanced Advantage Fund",
        )
    )

    repository.add(
        create_fund(
            "100012",
            "ICICI Bluechip Fund",
        )
    )

    results = repository.search_by_name(
        "HDFC",
    )

    assert len(results) == 2


def test_get_by_amc(
    repository: FundRepository,
) -> None:
    """Retrieve funds by AMC."""

    repository.add(
        create_fund(
            "100020",
            "Fund A",
            amc="SBI",
        )
    )

    repository.add(
        create_fund(
            "100021",
            "Fund B",
            amc="SBI",
        )
    )

    repository.add(
        create_fund(
            "100022",
            "Fund C",
            amc="HDFC",
        )
    )

    results = repository.get_by_amc(
        "SBI",
    )

    assert len(results) == 2


def test_inherited_count(
    repository: FundRepository,
) -> None:
    """Inherited BaseRepository methods should work."""

    repository.add(
        create_fund(
            "100030",
            "Fund A",
        )
    )

    repository.add(
        create_fund(
            "100031",
            "Fund B",
        )
    )

    assert repository.count() == 2


def test_inherited_exists(
    repository: FundRepository,
) -> None:
    """Exists should work through inheritance."""

    fund = create_fund(
        "100040",
        "Fund",
    )

    repository.add(fund)

    assert repository.exists(fund.id) is True


def test_inherited_get_all(
    repository: FundRepository,
) -> None:
    """Inherited get_all should return all funds."""

    repository.add(
        create_fund(
            "100050",
            "Fund A",
        )
    )

    repository.add(
        create_fund(
            "100051",
            "Fund B",
        )
    )

    assert len(repository.get_all()) == 2