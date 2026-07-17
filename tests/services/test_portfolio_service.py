"""
Tests for PortfolioService repository-backed portfolio loading.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from services.portfolio_service import PortfolioService


class FakeUnitOfWork:
    """Minimal UnitOfWork-compatible test double."""

    def __init__(
        self,
        *,
        portfolios: list[object],
        transactions_by_portfolio: dict[int, list[object]],
    ) -> None:
        self.portfolios = Mock()
        self.transactions = Mock()

        self.portfolios.get_active.return_value = portfolios

        self.transactions.get_for_portfolio.side_effect = (
            lambda portfolio_id: transactions_by_portfolio.get(
                portfolio_id,
                [],
            )
        )

        self.entered = False
        self.exited = False

    def __enter__(self) -> "FakeUnitOfWork":
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.exited = True


def make_transaction(
    *,
    transaction_id: int,
    portfolio_id: int,
    fund_id: int,
    scheme_code: str,
    fund_name: str,
    units: str,
    nav: str,
    amount: str,
    transaction_type: str = "OPENING_BALANCE",
) -> object:
    """Create a transaction-like object for service tests."""

    fund = SimpleNamespace(
        id=fund_id,
        scheme_code=scheme_code,
        name=fund_name,
    )

    return SimpleNamespace(
        id=transaction_id,
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        fund=fund,
        transaction_type=transaction_type,
        units=Decimal(units),
        nav=Decimal(nav),
        amount=Decimal(amount),
    )


def test_create_unit_of_work_requires_factory() -> None:
    service = PortfolioService()

    with pytest.raises(
        RuntimeError,
        match="No UnitOfWork factory has been configured",
    ):
        service._create_unit_of_work()


def test_create_unit_of_work_uses_configured_factory() -> None:
    expected = object()
    factory = Mock(return_value=expected)

    service = PortfolioService(
        unit_of_work_factory=factory,
    )

    result = service._create_unit_of_work()

    assert result is expected
    factory.assert_called_once_with()


def test_load_portfolio_from_repository_matches_loader_schema() -> None:
    portfolio = SimpleNamespace(
        id=1,
        name="Primary Portfolio",
        is_active=True,
    )

    transactions = [
        make_transaction(
            transaction_id=1,
            portfolio_id=1,
            fund_id=1,
            scheme_code="122639",
            fund_name=(
                "Parag Parikh Flexi Cap Fund "
                "- Direct Plan - Growth"
            ),
            units="120.000000",
            nav="82.5000",
            amount="9900.00",
        ),
        make_transaction(
            transaction_id=2,
            portfolio_id=1,
            fund_id=2,
            scheme_code="120503",
            fund_name=(
                "Motilal Oswal Midcap Fund "
                "- Direct Growth"
            ),
            units="75.000000",
            nav="64.2000",
            amount="4815.00",
        ),
    ]

    unit_of_work = FakeUnitOfWork(
        portfolios=[portfolio],
        transactions_by_portfolio={
            1: transactions,
        },
    )

    service = PortfolioService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    result = service._load_portfolio_from_repository()

    assert list(result.columns) == [
        "Scheme Code",
        "Fund",
        "Units",
        "Avg NAV",
    ]

    assert result.to_dict("records") == [
        {
            "Scheme Code": "122639",
            "Fund": (
                "Parag Parikh Flexi Cap Fund "
                "- Direct Plan - Growth"
            ),
            "Units": 120.0,
            "Avg NAV": 82.5,
        },
        {
            "Scheme Code": "120503",
            "Fund": (
                "Motilal Oswal Midcap Fund "
                "- Direct Growth"
            ),
            "Units": 75.0,
            "Avg NAV": 64.2,
        },
    ]

    assert unit_of_work.entered is True
    assert unit_of_work.exited is True

    unit_of_work.portfolios.get_active.assert_called_once_with()
    unit_of_work.transactions.get_for_portfolio.assert_called_once_with(
        1
    )


def test_load_portfolio_from_repository_returns_empty_schema_when_no_portfolio(
) -> None:
    unit_of_work = FakeUnitOfWork(
        portfolios=[],
        transactions_by_portfolio={},
    )

    service = PortfolioService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    result = service._load_portfolio_from_repository()

    assert result.empty
    assert list(result.columns) == [
        "Scheme Code",
        "Fund",
        "Units",
        "Avg NAV",
    ]


def test_load_portfolio_from_repository_aggregates_same_fund() -> None:
    portfolio = SimpleNamespace(
        id=1,
        name="Primary Portfolio",
        is_active=True,
    )

    transactions = [
        make_transaction(
            transaction_id=1,
            portfolio_id=1,
            fund_id=1,
            scheme_code="122639",
            fund_name="Example Fund",
            units="10.000000",
            nav="80.0000",
            amount="800.00",
            transaction_type="PURCHASE",
        ),
        make_transaction(
            transaction_id=2,
            portfolio_id=1,
            fund_id=1,
            scheme_code="122639",
            fund_name="Example Fund",
            units="5.000000",
            nav="100.0000",
            amount="500.00",
            transaction_type="PURCHASE",
        ),
    ]

    unit_of_work = FakeUnitOfWork(
        portfolios=[portfolio],
        transactions_by_portfolio={
            1: transactions,
        },
    )

    service = PortfolioService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    result = service._load_portfolio_from_repository()

    assert len(result) == 1

    row = result.iloc[0]

    assert row["Scheme Code"] == "122639"
    assert row["Fund"] == "Example Fund"
    assert row["Units"] == pytest.approx(15.0)
    assert row["Avg NAV"] == pytest.approx(
        1300.0 / 15.0
    )


def test_load_portfolio_from_repository_ignores_zero_unit_holding() -> None:
    portfolio = SimpleNamespace(
        id=1,
        name="Primary Portfolio",
        is_active=True,
    )

    transactions = [
        make_transaction(
            transaction_id=1,
            portfolio_id=1,
            fund_id=1,
            scheme_code="122639",
            fund_name="Example Fund",
            units="10.000000",
            nav="80.0000",
            amount="800.00",
            transaction_type="PURCHASE",
        ),
        make_transaction(
            transaction_id=2,
            portfolio_id=1,
            fund_id=1,
            scheme_code="122639",
            fund_name="Example Fund",
            units="-10.000000",
            nav="90.0000",
            amount="-900.00",
            transaction_type="REDEMPTION",
        ),
    ]

    unit_of_work = FakeUnitOfWork(
        portfolios=[portfolio],
        transactions_by_portfolio={
            1: transactions,
        },
    )

    service = PortfolioService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    result = service._load_portfolio_from_repository()

    assert result.empty
    assert list(result.columns) == [
        "Scheme Code",
        "Fund",
        "Units",
        "Avg NAV",
    ]