"""Tests for the tax-lot dashboard component."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from dashboard.components.tax_lot_analytics import (
    _build_open_lots_dataframe,
    _build_realized_gains_dataframe,
    render_tax_lot_analytics,
)
from services.tax_lot_service import (
    RealizedGain,
    TaxLot,
    TaxLotAnalysis,
)

@patch(
    "dashboard.components.tax_lot_analytics.st.columns"
)
@patch(
    "dashboard.components.tax_lot_analytics.st.subheader"
)
def test_render_tax_lot_analytics_displays_summary_metrics(
    mock_subheader,
    mock_columns,
) -> None:
    """Display open-lot, realized-match, and gain totals."""

    analysis = TaxLotAnalysis(
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
        realized_gains=[
            RealizedGain(
                portfolio_id=1,
                fund_id=20,
                sell_transaction_id=2,
                source_buy_transaction_id=1,
                acquisition_date=date(2026, 1, 10),
                disposal_date=date(2026, 2, 10),
                holding_period_days=31,
                units_sold=Decimal("40.000000"),
                sale_proceeds=Decimal("600.00"),
                cost_basis=Decimal("400.00"),
                realized_gain=Decimal("200.00"),
            )
        ],
    )

    open_lots_column = MagicMock()
    realized_matches_column = MagicMock()
    realized_gain_column = MagicMock()

    mock_columns.return_value = (
        open_lots_column,
        realized_matches_column,
        realized_gain_column,
    )

    render_tax_lot_analytics(
        analysis
    )

    mock_subheader.assert_called_once_with(
        "🧮 Tax-Lot & Realized Gain Analytics"
    )
    mock_columns.assert_called_once_with(3)

    open_lots_column.metric.assert_called_once_with(
        "Open Tax Lots",
        1,
    )
    realized_matches_column.metric.assert_called_once_with(
        "Realized Matches",
        1,
    )
    realized_gain_column.metric.assert_called_once_with(
        "Realized Gain / Loss",
        "₹200.00",
    )
def test_build_open_lots_dataframe_creates_display_rows() -> None:
    """Convert open tax lots into dashboard-ready rows."""

    analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=7,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("100.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[],
    )

    result = _build_open_lots_dataframe(
        analysis.open_lots
    )

    assert result.to_dict("records") == [
        {
            "Portfolio ID": 1,
            "Fund ID": 20,
            "Source Transaction ID": 7,
            "Acquisition Date": date(2026, 1, 10),
            "Original Units": 100.0,
            "Remaining Units": 60.0,
            "Cost Per Unit": 10.0,
            "Remaining Cost Basis": 600.0,
        }
    ]
def test_build_realized_gains_dataframe_creates_display_rows() -> None:
    """Convert realized FIFO matches into dashboard-ready rows."""

    realized_gain = RealizedGain(
        portfolio_id=1,
        fund_id=20,
        sell_transaction_id=8,
        source_buy_transaction_id=7,
        acquisition_date=date(2026, 1, 10),
        disposal_date=date(2026, 2, 10),
        holding_period_days=31,
        units_sold=Decimal("40.000000"),
        sale_proceeds=Decimal("600.00"),
        cost_basis=Decimal("400.00"),
        realized_gain=Decimal("200.00"),
    )

    result = _build_realized_gains_dataframe(
        [realized_gain]
    )

    assert result.to_dict("records") == [
        {
            "Portfolio ID": 1,
            "Fund ID": 20,
            "Sell Transaction ID": 8,
            "Source Buy Transaction ID": 7,
            "Acquisition Date": date(2026, 1, 10),
            "Disposal Date": date(2026, 2, 10),
            "Holding Period Days": 31,
            "Units Sold": 40.0,
            "Sale Proceeds": 600.0,
            "Cost Basis": 400.0,
            "Realized Gain": 200.0,
        }
    ]
@patch(
    "dashboard.components.tax_lot_analytics.st.dataframe"
)
@patch(
    "dashboard.components.tax_lot_analytics.st.columns"
)
def test_render_tax_lot_analytics_displays_both_tables(
    mock_columns,
    mock_dataframe,
) -> None:
    """Display open lots and realized FIFO matches."""

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    analysis = TaxLotAnalysis(
        open_lots=[
            TaxLot(
                portfolio_id=1,
                fund_id=20,
                source_transaction_id=7,
                acquisition_date=date(2026, 1, 10),
                original_units=Decimal("100.000000"),
                remaining_units=Decimal("60.000000"),
                cost_per_unit=Decimal("10.0000"),
                remaining_cost_basis=Decimal("600.00"),
            )
        ],
        realized_gains=[
            RealizedGain(
                portfolio_id=1,
                fund_id=20,
                sell_transaction_id=8,
                source_buy_transaction_id=7,
                acquisition_date=date(2026, 1, 10),
                disposal_date=date(2026, 2, 10),
                holding_period_days=31,
                units_sold=Decimal("40.000000"),
                sale_proceeds=Decimal("600.00"),
                cost_basis=Decimal("400.00"),
                realized_gain=Decimal("200.00"),
            )
        ],
    )

    render_tax_lot_analytics(
        analysis
    )

    assert mock_dataframe.call_count == 2

    open_lots_frame = (
        mock_dataframe.call_args_list[0].args[0]
    )
    realized_gains_frame = (
        mock_dataframe.call_args_list[1].args[0]
    )

    assert len(open_lots_frame) == 1
    assert len(realized_gains_frame) == 1

    assert mock_dataframe.call_args_list[0].kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
    assert mock_dataframe.call_args_list[1].kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
@patch(
    "dashboard.components.tax_lot_analytics.st.download_button"
)
@patch(
    "dashboard.components.tax_lot_analytics."
    "TaxLotExcelReportService",
    create=True,
)
@patch(
    "dashboard.components.tax_lot_analytics.st.dataframe"
)
@patch(
    "dashboard.components.tax_lot_analytics.st.columns"
)
def test_render_tax_lot_analytics_provides_excel_download(
    mock_columns,
    mock_dataframe,
    mock_excel_service_class,
    mock_download_button,
) -> None:
    """Provide the complete tax-lot workbook for download."""

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    analysis = TaxLotAnalysis(
        open_lots=[],
        realized_gains=[],
    )

    excel_service = (
        mock_excel_service_class.return_value
    )
    excel_service.prepare_download.return_value = (
        b"PK-tax-lot-workbook",
        "portfolio_tax_lots.xlsx",
        (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    render_tax_lot_analytics(
        analysis
    )

    excel_service.prepare_download.assert_called_once_with(
        analysis
    )

    mock_download_button.assert_called_once_with(
        "Download Tax-Lot Workbook",
        data=b"PK-tax-lot-workbook",
        file_name="portfolio_tax_lots.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        key="download_tax_lot_workbook",
    )