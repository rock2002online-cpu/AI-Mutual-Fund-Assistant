"""Tests for portfolio tax-lot application service."""

from unittest.mock import Mock
import pytest
from datetime import date
from repositories.transaction_repository import TransactionRepository
from services.portfolio_tax_lot_service import PortfolioTaxLotService
from services.tax_lot_service import (
    TaxLotAnalysis,
    TaxLotService,
)


def test_analyze_portfolio_uses_portfolio_transactions() -> None:
    """Portfolio analysis should use its repository transactions."""

    transactions = [Mock(), Mock()]

    expected_analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )

    transaction_repository = Mock(
        spec=TransactionRepository,
    )
    transaction_repository.get_for_portfolio.return_value = (
        transactions
    )

    tax_lot_service = Mock(
        spec=TaxLotService,
    )
    tax_lot_service.analyze.return_value = expected_analysis

    service = PortfolioTaxLotService(
        transaction_repository=transaction_repository,
        tax_lot_service=tax_lot_service,
    )

    result = service.analyze_portfolio(
        portfolio_id=10,
    )

    assert result is expected_analysis

    transaction_repository.get_for_portfolio.assert_called_once_with(
        10
    )
    tax_lot_service.analyze.assert_called_once_with(
        transactions=transactions,
    )
def test_analyze_portfolio_rejects_non_positive_id() -> None:
    """Portfolio identifiers must be positive integers."""

    transaction_repository = Mock(
        spec=TransactionRepository,
    )
    tax_lot_service = Mock(
        spec=TaxLotService,
    )

    service = PortfolioTaxLotService(
        transaction_repository=transaction_repository,
        tax_lot_service=tax_lot_service,
    )

    with pytest.raises(
        ValueError,
        match="portfolio_id must be positive",
    ):
        service.analyze_portfolio(
            portfolio_id=0,
        )

    transaction_repository.get_for_portfolio.assert_not_called()
    tax_lot_service.analyze.assert_not_called()
def test_analyze_portfolio_supports_as_of_date() -> None:
    """Historical analysis should exclude later transactions."""

    transactions = [Mock(), Mock()]

    expected_analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )

    transaction_repository = Mock(
        spec=TransactionRepository,
    )
    (
        transaction_repository
        .get_for_portfolio_through_date
        .return_value
    ) = transactions

    tax_lot_service = Mock(
        spec=TaxLotService,
    )
    tax_lot_service.analyze.return_value = expected_analysis

    service = PortfolioTaxLotService(
        transaction_repository=transaction_repository,
        tax_lot_service=tax_lot_service,
    )

    result = service.analyze_portfolio(
        portfolio_id=10,
        as_of_date=date(2026, 6, 30),
    )

    assert result is expected_analysis

    (
        transaction_repository
        .get_for_portfolio_through_date
        .assert_called_once_with(
            portfolio_id=10,
            end_date=date(2026, 6, 30),
        )
    )
    transaction_repository.get_for_portfolio.assert_not_called()
    tax_lot_service.analyze.assert_called_once_with(
        transactions=transactions,
    )