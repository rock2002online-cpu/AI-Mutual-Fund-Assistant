"""Tests for portfolio reconciliation analytics."""

from datetime import date
from decimal import Decimal

from models.position import Position
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationService,
)
from services.tax_lot_service import (
    TaxLot,
    TaxLotAnalysis,
)


def test_reconcile_matching_position_and_tax_lot() -> None:
    """Matching position and transaction balances should reconcile."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=10.0,
        invested_amount=600.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=300.0,
        unrealized_return_pct=50.0,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("100.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is True
    assert len(result.items) == 1

    item = result.items[0]

    assert item.portfolio_id == 1
    assert item.fund_id == 20
    assert item.fund_name == "Test Equity Fund"
    assert item.position_units == Decimal("60.000000")
    assert item.transaction_units == Decimal("60.000000")
    assert item.unit_variance == Decimal("0.000000")
    assert item.position_cost_basis == Decimal("600.00")
    assert item.transaction_cost_basis == Decimal("600.00")
    assert item.cost_basis_variance == Decimal("0.00")
    assert item.status == "matched"
def test_reconcile_tax_lot_without_position() -> None:
    """An open tax lot without a position should be reported."""

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("60.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is False
    assert len(result.items) == 1

    item = result.items[0]

    assert item.portfolio_id == 1
    assert item.fund_id == 20
    assert item.fund_name is None
    assert item.position_units == Decimal("0.000000")
    assert item.transaction_units == Decimal("60.000000")
    assert item.unit_variance == Decimal("-60.000000")
    assert item.position_cost_basis == Decimal("0.00")
    assert item.transaction_cost_basis == Decimal("600.00")
    assert item.cost_basis_variance == Decimal("-600.00")
    assert item.status == "missing_position"
    assert result.missing_position_count == 1
def test_reconcile_position_without_tax_lot() -> None:
    """A position without open tax lots should be reported."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=10.0,
        invested_amount=600.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=300.0,
        unrealized_return_pct=50.0,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is False
    assert len(result.items) == 1

    item = result.items[0]

    assert item.portfolio_id == 1
    assert item.fund_id == 20
    assert item.fund_name == "Test Equity Fund"
    assert item.position_units == Decimal("60.000000")
    assert item.transaction_units == Decimal("0.000000")
    assert item.unit_variance == Decimal("60.000000")
    assert item.position_cost_basis == Decimal("600.00")
    assert item.transaction_cost_basis == Decimal("0.00")
    assert item.cost_basis_variance == Decimal("600.00")
    assert item.status == "missing_tax_lots"
    assert result.cost_basis_variance_count == 0
    assert result.missing_tax_lot_count == 1
def test_reconcile_detects_unit_mismatch() -> None:
    """Different position and transaction units should not reconcile."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=10.0,
        invested_amount=600.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=300.0,
        unrealized_return_pct=50.0,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("100.000000"),
                remaining_units=Decimal("55.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("550.00"),
            )
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is False
    assert len(result.items) == 1

    item = result.items[0]

    assert item.position_units == Decimal("60.000000")
    assert item.transaction_units == Decimal("55.000000")
    assert item.unit_variance == Decimal("5.000000")
    assert item.position_cost_basis == Decimal("600.00")
    assert item.transaction_cost_basis == Decimal("550.00")
    assert item.cost_basis_variance == Decimal("50.00")
    assert item.status == "unit_mismatch"
    assert result.unreconciled_count == 1
    assert result.unit_mismatch_count == 1
def test_cost_basis_variance_is_informational() -> None:
    """Cost-basis differences should not cause unit reconciliation failure."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=11.0,
        invested_amount=660.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=240.0,
        unrealized_return_pct=36.363636,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("100.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is True
    assert len(result.items) == 1

    item = result.items[0]

    assert item.position_units == Decimal("60.000000")
    assert item.transaction_units == Decimal("60.000000")
    assert item.unit_variance == Decimal("0.000000")
    assert item.position_cost_basis == Decimal("660.00")
    assert item.transaction_cost_basis == Decimal("600.00")
    assert item.cost_basis_variance == Decimal("60.00")
    assert item.status == "matched"
    assert result.cost_basis_variance_count == 1
def test_reconcile_aggregates_multiple_open_tax_lots() -> None:
    """Multiple open lots for one fund should be aggregated."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=11.0,
        invested_amount=660.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=240.0,
        unrealized_return_pct=36.363636,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("40.000000"),
                remaining_units=Decimal("40.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("400.00"),
            ),
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=2,
                acquisition_date=date(2026, 2, 10),
                original_units=Decimal("20.000000"),
                remaining_units=Decimal("20.000000"),
                cost_per_unit=Decimal("12.0000"),
                remaining_cost_basis=Decimal("240.00"),
            ),
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.is_reconciled is True
    assert len(result.items) == 1

    item = result.items[0]

    assert item.position_units == Decimal("60.000000")
    assert item.transaction_units == Decimal("60.000000")
    assert item.unit_variance == Decimal("0.000000")
    assert item.position_cost_basis == Decimal("660.00")
    assert item.transaction_cost_basis == Decimal("640.00")
    assert item.cost_basis_variance == Decimal("20.00")
    assert item.status == "matched"
def test_result_reports_matched_item_count() -> None:
    """The result should expose the number of matched fund items."""

    position = Position(
        portfolio_id=1,
        fund_id=20,
        fund_name="Test Equity Fund",
        units=60.0,
        average_nav=10.0,
        invested_amount=600.0,
        latest_nav=15.0,
        current_value=900.0,
        unrealized_gain=300.0,
        unrealized_return_pct=50.0,
    )

    tax_lot_analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("60.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[],
    )

    result = PortfolioReconciliationService().reconcile(
        positions=[position],
        tax_lot_analysis=tax_lot_analysis,
    )

    assert result.matched_count == 1
    assert result.total_count == 1