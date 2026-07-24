"""Tests for portfolio reconciliation reporting orchestration."""

from unittest.mock import Mock

from services.portfolio_reconciliation_reporting_service import (
    PortfolioReconciliationReportingService,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
    PortfolioReconciliationService,
)
from services.portfolio_tax_lot_service import (
    PortfolioTaxLotService,
)
from services.position_service import PositionService
from services.tax_lot_service import TaxLotAnalysis
import pytest


def test_reconcile_portfolio_coordinates_existing_services() -> None:
    """Build reconciliation from portfolio positions and tax lots."""

    positions = [
        Mock(),
        Mock(),
    ]
    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )
    expected_result = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    position_service = Mock(
        spec=PositionService,
    )
    position_service.get_positions.return_value = positions

    tax_lot_service = Mock(
        spec=PortfolioTaxLotService,
    )
    tax_lot_service.analyze_portfolio.return_value = (
        tax_lot_analysis
    )

    reconciliation_service = Mock(
        spec=PortfolioReconciliationService,
    )
    reconciliation_service.reconcile.return_value = (
        expected_result
    )

    service = PortfolioReconciliationReportingService(
        position_service=position_service,
        portfolio_tax_lot_service=tax_lot_service,
        reconciliation_service=reconciliation_service,
    )

    result = service.reconcile_portfolio(
        portfolio_id=10,
    )

    assert result is expected_result

    position_service.get_positions.assert_called_once_with(
        portfolio_id=10,
    )
    tax_lot_service.analyze_portfolio.assert_called_once_with(
        portfolio_id=10,
    )
    reconciliation_service.reconcile.assert_called_once_with(
        positions=positions,
        tax_lot_analysis=tax_lot_analysis,
    )
def test_reconcile_portfolio_rejects_non_positive_id() -> None:
    """Portfolio identifiers must be positive integers."""

    position_service = Mock(
        spec=PositionService,
    )
    tax_lot_service = Mock(
        spec=PortfolioTaxLotService,
    )
    reconciliation_service = Mock(
        spec=PortfolioReconciliationService,
    )

    service = PortfolioReconciliationReportingService(
        position_service=position_service,
        portfolio_tax_lot_service=tax_lot_service,
        reconciliation_service=reconciliation_service,
    )

    with pytest.raises(
        ValueError,
        match="portfolio_id must be positive",
    ):
        service.reconcile_portfolio(
            portfolio_id=0,
        )

    position_service.get_positions.assert_not_called()
    tax_lot_service.analyze_portfolio.assert_not_called()
    reconciliation_service.reconcile.assert_not_called()