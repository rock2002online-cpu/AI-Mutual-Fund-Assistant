"""Tests for typed reporting models."""

from datetime import datetime
from unittest.mock import Mock

from services.analytics.performance import (
    PortfolioPerformanceMetrics,
)
from services.reporting.report_models import (
    PortfolioReport,
    ReportMetadata,
)
from services.tax_lot_service import TaxLotAnalysis
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)


def test_portfolio_report_carries_tax_lot_analysis() -> None:
    """Reports should expose precomputed tax-lot analytics."""

    metadata = ReportMetadata(
        title="Portfolio Tax-Lot Report",
        version="13.0",
        generated_at=datetime(2026, 7, 22, 12, 0),
    )
    performance = Mock(
        spec=PortfolioPerformanceMetrics,
    )
    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )

    report = PortfolioReport(
        metadata=metadata,
        performance=performance,
        tax_lot_analysis=tax_lot_analysis,
    )

    assert report.tax_lot_analysis is tax_lot_analysis
def test_portfolio_report_carries_reconciliation_result() -> None:
    """Reports should expose precomputed portfolio reconciliation."""

    metadata = ReportMetadata(
        title="Portfolio Reconciliation Report",
        version="15.0",
        generated_at=datetime(2026, 7, 23, 12, 0),
    )
    performance = Mock(
        spec=PortfolioPerformanceMetrics,
    )
    reconciliation = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    report = PortfolioReport(
        metadata=metadata,
        performance=performance,
        reconciliation=reconciliation,
    )

    assert report.reconciliation is reconciliation