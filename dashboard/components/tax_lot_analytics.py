"""Tax-lot and realized-gain dashboard component."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import pandas as pd
import streamlit as st

from services.reporting.tax_lot_excel_report_service import (
    TaxLotExcelReportService,
)
from services.tax_lot_service import (
    RealizedGain,
    TaxLot,
    TaxLotAnalysis,
)

_OPEN_LOT_COLUMNS = [
    "Portfolio ID",
    "Fund ID",
    "Source Transaction ID",
    "Acquisition Date",
    "Original Units",
    "Remaining Units",
    "Cost Per Unit",
    "Remaining Cost Basis",
]

_REALIZED_GAIN_COLUMNS = [
    "Portfolio ID",
    "Fund ID",
    "Sell Transaction ID",
    "Source Buy Transaction ID",
    "Acquisition Date",
    "Disposal Date",
    "Holding Period Days",
    "Units Sold",
    "Sale Proceeds",
    "Cost Basis",
    "Realized Gain",
]


def _format_currency(
    value: Decimal,
) -> str:
    """Format a signed Indian rupee value."""

    numeric_value = Decimal(value)

    sign = (
        "-"
        if numeric_value < Decimal("0.00")
        else ""
    )

    return (
        f"{sign}₹"
        f"{abs(numeric_value):,.2f}"
    )


def _build_open_lots_dataframe(
    open_lots: Sequence[TaxLot],
) -> pd.DataFrame:
    """Convert open tax lots into display-ready rows."""

    rows = [
        {
            "Portfolio ID": lot.portfolio_id,
            "Fund ID": lot.fund_id,
            "Source Transaction ID": (
                lot.source_transaction_id
            ),
            "Acquisition Date": (
                lot.acquisition_date
            ),
            "Original Units": float(
                lot.original_units
            ),
            "Remaining Units": float(
                lot.remaining_units
            ),
            "Cost Per Unit": float(
                lot.cost_per_unit
            ),
            "Remaining Cost Basis": float(
                lot.remaining_cost_basis
            ),
        }
        for lot in open_lots
    ]

    return pd.DataFrame(
        rows,
        columns=_OPEN_LOT_COLUMNS,
    )


def _build_realized_gains_dataframe(
    realized_gains: Sequence[RealizedGain],
) -> pd.DataFrame:
    """Convert realized FIFO matches into display-ready rows."""

    rows = [
        {
            "Portfolio ID": match.portfolio_id,
            "Fund ID": match.fund_id,
            "Sell Transaction ID": (
                match.sell_transaction_id
            ),
            "Source Buy Transaction ID": (
                match.source_buy_transaction_id
            ),
            "Acquisition Date": (
                match.acquisition_date
            ),
            "Disposal Date": (
                match.disposal_date
            ),
            "Holding Period Days": (
                match.holding_period_days
            ),
            "Units Sold": float(
                match.units_sold
            ),
            "Sale Proceeds": float(
                match.sale_proceeds
            ),
            "Cost Basis": float(
                match.cost_basis
            ),
            "Realized Gain": float(
                match.realized_gain
            ),
        }
        for match in realized_gains
    ]

    return pd.DataFrame(
        rows,
        columns=_REALIZED_GAIN_COLUMNS,
    )


def render_tax_lot_analytics(
    analysis: TaxLotAnalysis,
) -> None:
    """Render tax-lot metrics, tables, and Excel download."""

    if not isinstance(
        analysis,
        TaxLotAnalysis,
    ):
        raise TypeError(
            "analysis must be a TaxLotAnalysis"
        )

    st.subheader(
        "🧮 Tax-Lot & Realized Gain Analytics"
    )

    columns = st.columns(3)

    columns[0].metric(
        "Open Tax Lots",
        len(analysis.open_lots),
    )
    columns[1].metric(
        "Realized Matches",
        len(analysis.realized_gains),
    )
    columns[2].metric(
        "Realized Gain / Loss",
        _format_currency(
            analysis.total_realized_gain
        ),
    )

    st.markdown(
        "#### Open Tax Lots"
    )
    st.dataframe(
        _build_open_lots_dataframe(
            analysis.open_lots
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        "#### Realized FIFO Matches"
    )
    st.dataframe(
        _build_realized_gains_dataframe(
            analysis.realized_gains
        ),
        width="stretch",
        hide_index=True,
    )

    excel_service = (
        TaxLotExcelReportService()
    )

    (
        excel_bytes,
        filename,
        mime_type,
    ) = excel_service.prepare_download(
        analysis
    )

    st.download_button(
        "Download Tax-Lot Workbook",
        data=excel_bytes,
        file_name=filename,
        mime=mime_type,
        key="download_tax_lot_workbook",
    )