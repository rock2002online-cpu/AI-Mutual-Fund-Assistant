"""Tests for the reconciliation alerts dashboard component."""

from unittest.mock import patch

from dashboard.components.reconciliation_alerts import (
    render_reconciliation_alerts,
)
from services.reconciliation_alert_service import (
    ReconciliationAlert,
)


@patch(
    "dashboard.components.reconciliation_alerts.st.error"
)
def test_render_reconciliation_alerts_displays_critical_alert(
    mock_error,
) -> None:
    """Critical reconciliation alerts should render as errors."""

    alert = ReconciliationAlert(
        portfolio_id=10,
        fund_id=20,
        fund_name="Example Equity Fund",
        code="unit_mismatch",
        severity="critical",
        message=(
            "Position units differ from transaction units "
            "by 5.000000."
        ),
    )

    render_reconciliation_alerts(
        [alert]
    )

    mock_error.assert_called_once_with(
        (
            "Example Equity Fund — "
            "Position units differ from transaction units "
            "by 5.000000."
        )
    )
@patch(
    "dashboard.components.reconciliation_alerts.st.info"
)
def test_render_reconciliation_alerts_displays_informational_alert(
    mock_info,
) -> None:
    """Cost-basis variance should render as informational."""

    alert = ReconciliationAlert(
        portfolio_id=10,
        fund_id=21,
        fund_name="Matched Fund",
        code="cost_basis_variance",
        severity="info",
        message=(
            "Moving-average and FIFO cost bases differ "
            "by ₹50.00; units remain reconciled."
        ),
    )

    render_reconciliation_alerts(
        [alert]
    )

    mock_info.assert_called_once_with(
        (
            "Matched Fund — "
            "Moving-average and FIFO cost bases differ "
            "by ₹50.00; units remain reconciled."
        )
    )
@patch(
    "dashboard.components.reconciliation_alerts.st.success"
)
def test_render_reconciliation_alerts_displays_success_when_empty(
    mock_success,
) -> None:
    """No alerts should confirm that reconciliation is healthy."""

    render_reconciliation_alerts(
        []
    )

    mock_success.assert_called_once_with(
        "No reconciliation alerts detected."
    )