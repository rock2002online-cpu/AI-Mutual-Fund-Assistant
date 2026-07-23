"""Tests for the portfolio reconciliation dashboard component."""

from decimal import Decimal

from dashboard.components.portfolio_reconciliation import (
    _build_reconciliation_dataframe,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
)
from dashboard.components.portfolio_reconciliation import (
    _build_reconciliation_dataframe,
    render_portfolio_reconciliation,
)
from unittest.mock import MagicMock, patch

from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
    PortfolioReconciliationResult,
)

def test_build_reconciliation_dataframe_creates_display_rows() -> None:
    """Convert reconciliation items into dashboard-ready rows."""

    item = PortfolioReconciliationItem(
        portfolio_id=10,
        fund_id=20,
        fund_name="Example Equity Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("100.000000"),
        unit_variance=Decimal("0.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("950.00"),
        cost_basis_variance=Decimal("50.00"),
        status="matched",
    )

    result = _build_reconciliation_dataframe(
        [item]
    )

    assert result.to_dict("records") == [
        {
            "Portfolio ID": 10,
            "Fund ID": 20,
            "Fund Name": "Example Equity Fund",
            "Position Units": 100.0,
            "Transaction Units": 100.0,
            "Unit Variance": 0.0,
            "Position Cost Basis": 1000.0,
            "Transaction Cost Basis": 950.0,
            "Cost Basis Variance": 50.0,
            "Status": "Matched",
        }
    ]
@patch(
    "dashboard.components.portfolio_reconciliation.st.columns"
)
@patch(
    "dashboard.components.portfolio_reconciliation.st.subheader"
)
def test_render_portfolio_reconciliation_displays_summary_metrics(
    mock_subheader,
    mock_columns,
) -> None:
    """Display unit reconciliation and informational variance totals."""

    result = PortfolioReconciliationResult(
        items=[
            PortfolioReconciliationItem(
                portfolio_id=10,
                fund_id=20,
                fund_name="Example Equity Fund",
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

    status_column = MagicMock()
    total_column = MagicMock()
    exception_column = MagicMock()
    variance_column = MagicMock()

    mock_columns.return_value = (
        status_column,
        total_column,
        exception_column,
        variance_column,
    )

    render_portfolio_reconciliation(
        result
    )

    mock_subheader.assert_called_once_with(
        "🔍 Portfolio Reconciliation"
    )
    mock_columns.assert_called_once_with(4)

    status_column.metric.assert_called_once_with(
        "Overall Status",
        "Reconciled",
    )
    total_column.metric.assert_called_once_with(
        "Total Funds",
        1,
    )
    exception_column.metric.assert_called_once_with(
        "Unit Exceptions",
        0,
    )
    variance_column.metric.assert_called_once_with(
        "Cost-Basis Variances",
        1,
        help=(
            "Informational only; unit balances determine "
            "reconciliation status."
        ),
    )
@patch(
    "dashboard.components.portfolio_reconciliation.st.dataframe"
)
@patch(
    "dashboard.components.portfolio_reconciliation.st.columns"
)
def test_render_portfolio_reconciliation_displays_detail_table(
    mock_columns,
    mock_dataframe,
) -> None:
    """Display every fund-level reconciliation result."""

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

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

    render_portfolio_reconciliation(
        result
    )

    mock_dataframe.assert_called_once()

    dataframe = mock_dataframe.call_args.args[0]

    assert dataframe.to_dict("records") == [
        {
            "Portfolio ID": 10,
            "Fund ID": 20,
            "Fund Name": "Example Equity Fund",
            "Position Units": 100.0,
            "Transaction Units": 95.0,
            "Unit Variance": 5.0,
            "Position Cost Basis": 1000.0,
            "Transaction Cost Basis": 950.0,
            "Cost Basis Variance": 50.0,
            "Status": "Unit Mismatch",
        }
    ]

    assert mock_dataframe.call_args.kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
@patch(
    "dashboard.components.portfolio_reconciliation.st.download_button"
)
@patch(
    "dashboard.components.portfolio_reconciliation."
    "ReconciliationExcelReportService",
    create=True,
)
@patch(
    "dashboard.components.portfolio_reconciliation.st.dataframe"
)
@patch(
    "dashboard.components.portfolio_reconciliation.st.columns"
)
def test_render_portfolio_reconciliation_provides_excel_download(
    mock_columns,
    mock_dataframe,
    mock_excel_service_class,
    mock_download_button,
) -> None:
    """Provide the complete reconciliation workbook for download."""

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    result = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    excel_service = (
        mock_excel_service_class.return_value
    )
    excel_service.prepare_download.return_value = (
        b"PK-reconciliation-workbook",
        "portfolio_reconciliation.xlsx",
        (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    render_portfolio_reconciliation(
        result
    )

    excel_service.prepare_download.assert_called_once_with(
        result
    )

    mock_download_button.assert_called_once_with(
        "Download Reconciliation Workbook",
        data=b"PK-reconciliation-workbook",
        file_name="portfolio_reconciliation.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_reconciliation_workbook",
    )