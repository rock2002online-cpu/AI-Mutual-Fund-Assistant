"""Tests for reconciliation alert generation."""

from decimal import Decimal

from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
    PortfolioReconciliationResult,
)
from services.reconciliation_alert_service import (
    ReconciliationAlertService,
)
import pytest

def test_build_alerts_creates_critical_unit_mismatch_alert() -> None:
    """Unit mismatches should produce actionable critical alerts."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=20,
                fund_name="Example Equity Fund",
                position_units=Decimal("100.000000"),
                transaction_units=Decimal("95.000000"),
                unit_variance=Decimal("5.000000"),
                position_cost_basis=Decimal("1000.00"),
                transaction_cost_basis=Decimal("950.00"),
                cost_basis_variance=Decimal("50.00"),
                status="unit_mismatch",
            )
        ],
        is_reconciled=False,
    )

    alerts = ReconciliationAlertService().build_alerts(
        result
    )

    assert len(alerts) == 1

    alert = alerts[0]

    assert alert.portfolio_id == 10
    assert alert.fund_id == 20
    assert alert.fund_name == "Example Equity Fund"
    assert alert.code == "unit_mismatch"
    assert alert.severity == "critical"
    assert alert.message == (
        "Position units differ from transaction units "
        "by 5.000000."
    )
def test_build_alerts_creates_critical_missing_position_alert() -> None:
    """Tax-lot balances without positions require investigation."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=21,
                fund_name=None,
                position_units=Decimal("0.000000"),
                transaction_units=Decimal("25.000000"),
                unit_variance=Decimal("-25.000000"),
                position_cost_basis=Decimal("0.00"),
                transaction_cost_basis=Decimal("250.00"),
                cost_basis_variance=Decimal("-250.00"),
                status="missing_position",
            )
        ],
        is_reconciled=False,
    )

    alerts = ReconciliationAlertService().build_alerts(
        result
    )

    assert len(alerts) == 1

    alert = alerts[0]

    assert alert.portfolio_id == 10
    assert alert.fund_id == 21
    assert alert.fund_name is None
    assert alert.code == "missing_position"
    assert alert.severity == "critical"
    assert alert.message == (
        "Transaction tax lots contain 25.000000 units "
        "without a portfolio position."
    )
def test_build_alerts_creates_critical_missing_tax_lots_alert() -> None:
    """Positions without transaction tax lots require investigation."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=22,
                fund_name="Missing Lots Fund",
                position_units=Decimal("30.000000"),
                transaction_units=Decimal("0.000000"),
                unit_variance=Decimal("30.000000"),
                position_cost_basis=Decimal("300.00"),
                transaction_cost_basis=Decimal("0.00"),
                cost_basis_variance=Decimal("300.00"),
                status="missing_tax_lots",
            )
        ],
        is_reconciled=False,
    )

    alerts = ReconciliationAlertService().build_alerts(
        result
    )

    assert len(alerts) == 1

    alert = alerts[0]

    assert alert.portfolio_id == 10
    assert alert.fund_id == 22
    assert alert.fund_name == "Missing Lots Fund"
    assert alert.code == "missing_tax_lots"
    assert alert.severity == "critical"
    assert alert.message == (
        "Portfolio position contains 30.000000 units "
        "without transaction tax lots."
    )
def test_build_alerts_marks_cost_basis_variance_as_informational() -> None:
    """Matched units with cost-basis variance must not become critical."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=23,
                fund_name="Matched Fund",
                position_units=Decimal("100.000000"),
                transaction_units=Decimal("100.000000"),
                unit_variance=Decimal("0.000000"),
                position_cost_basis=Decimal("1000.00"),
                transaction_cost_basis=Decimal("950.00"),
                cost_basis_variance=Decimal("50.00"),
                status="matched",
            )
        ],
        is_reconciled=True,
    )

    alerts = ReconciliationAlertService().build_alerts(
        result
    )

    assert len(alerts) == 1

    alert = alerts[0]

    assert alert.code == "cost_basis_variance"
    assert alert.severity == "info"
    assert alert.message == (
        "Moving-average and FIFO cost bases differ "
        "by ₹50.00; units remain reconciled."
    )
def test_build_alerts_rejects_invalid_result() -> None:
    """Alert generation should require a reconciliation result."""

    with pytest.raises(
        TypeError,
        match=(
            "result must be a "
            "PortfolioReconciliationResult"
        ),
    ):
        ReconciliationAlertService().build_alerts(
            object(),  # type: ignore[arg-type]
        )