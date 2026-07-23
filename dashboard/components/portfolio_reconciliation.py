"""Portfolio reconciliation dashboard component."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import streamlit as st
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationItem,
    PortfolioReconciliationResult,
)
from services.reporting.reconciliation_excel_report_service import (
    ReconciliationExcelReportService,
)
_RECONCILIATION_COLUMNS = [
    "Portfolio ID",
    "Fund ID",
    "Fund Name",
    "Position Units",
    "Transaction Units",
    "Unit Variance",
    "Position Cost Basis",
    "Transaction Cost Basis",
    "Cost Basis Variance",
    "Status",
]


def _build_reconciliation_dataframe(
    items: Sequence[PortfolioReconciliationItem],
) -> pd.DataFrame:
    """Convert reconciliation items into display-ready rows."""

    rows = [
        {
            "Portfolio ID": item.portfolio_id,
            "Fund ID": item.fund_id,
            "Fund Name": item.fund_name,
            "Position Units": float(
                item.position_units
            ),
            "Transaction Units": float(
                item.transaction_units
            ),
            "Unit Variance": float(
                item.unit_variance
            ),
            "Position Cost Basis": float(
                item.position_cost_basis
            ),
            "Transaction Cost Basis": float(
                item.transaction_cost_basis
            ),
            "Cost Basis Variance": float(
                item.cost_basis_variance
            ),
            "Status": item.status.replace(
                "_",
                " ",
            ).title(),
        }
        for item in items
    ]

    return pd.DataFrame(
        rows,
        columns=_RECONCILIATION_COLUMNS,
    )


__all__ = [
    "_build_reconciliation_dataframe",
    "render_portfolio_reconciliation",
]
def render_portfolio_reconciliation(
    result: PortfolioReconciliationResult,
) -> None:
    """Render portfolio reconciliation summary metrics."""

    if not isinstance(
        result,
        PortfolioReconciliationResult,
    ):
        raise TypeError(
            "result must be a PortfolioReconciliationResult"
        )

    st.subheader(
        "🔍 Portfolio Reconciliation"
    )

    columns = st.columns(4)

    columns[0].metric(
        "Overall Status",
        (
            "Reconciled"
            if result.is_reconciled
            else "Unreconciled"
        ),
    )
    columns[1].metric(
        "Total Funds",
        result.total_count,
    )
    columns[2].metric(
        "Unit Exceptions",
        result.unreconciled_count,
    )
    columns[3].metric(
        "Cost-Basis Variances",
        result.cost_basis_variance_count,
        help=(
            "Informational only; unit balances determine "
            "reconciliation status."
        ),
    )
    st.dataframe(
        _build_reconciliation_dataframe(
            result.items
        ),
        width="stretch",
        hide_index=True,
    )
    excel_service = (
        ReconciliationExcelReportService()
    )

    (
        excel_bytes,
        filename,
        mime_type,
    ) = excel_service.prepare_download(
        result
    )

    st.download_button(
        "Download Reconciliation Workbook",
        data=excel_bytes,
        file_name=filename,
        mime=mime_type,
        key="download_reconciliation_workbook",
    )