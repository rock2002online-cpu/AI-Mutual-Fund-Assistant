"""Portfolio page view."""

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from dashboard.components.history import show_history
from dashboard.components.portfolio import show_portfolio
from dashboard.components.portfolio_summary import show_portfolio_summary
from views.tax_lot_view import render_tax_lot_section
from services.portfolio_service import PortfolioService
from services.transaction_import_service import TransactionImportService
from services.transaction_service import TransactionService


def _build_transaction_preview(
    transactions: tuple,
) -> pd.DataFrame:
    """Convert prepared transactions into a display dataframe."""

    return pd.DataFrame(
        [
            {
                "Date": transaction.transaction_date,
                "Fund ID": transaction.fund_id,
                "Transaction Type": transaction.transaction_type,
                "Units": float(transaction.units),
                "Amount": float(transaction.amount),
            }
            for transaction in transactions
        ]
    )


def _filter_transaction_history(
    transaction_history: pd.DataFrame,
    *,
    transaction_types: tuple[str, ...],
    funds: tuple[str, ...],
    xirr_eligibility: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Return a filtered copy of the transaction ledger."""

    filtered_history = transaction_history.copy()

    if transaction_types:
        normalized_types = {
            str(transaction_type).strip().upper()
            for transaction_type in transaction_types
        }

        filtered_history = filtered_history[
            filtered_history["Transaction Type"]
            .astype(str)
            .str.strip()
            .str.upper()
            .isin(normalized_types)
        ]

    if funds:
        normalized_funds = {
            str(fund).strip()
            for fund in funds
        }

        filtered_history = filtered_history[
            filtered_history["Fund"]
            .astype(str)
            .str.strip()
            .isin(normalized_funds)
        ]

    normalized_eligibility = (
        str(xirr_eligibility).strip().lower()
    )

    if normalized_eligibility == "eligible":
        filtered_history = filtered_history[
            filtered_history["XIRR Eligible"]
            .fillna(False)
            .astype(bool)
        ]
    elif normalized_eligibility == "excluded":
        filtered_history = filtered_history[
            ~filtered_history["XIRR Eligible"]
            .fillna(False)
            .astype(bool)
        ]

    if (
        start_date is not None
        or end_date is not None
    ):
        transaction_dates = pd.to_datetime(
            filtered_history["Date"],
            errors="coerce",
        )

        if start_date is not None:
            filtered_history = filtered_history[
                transaction_dates
                >= pd.Timestamp(start_date)
            ]

            transaction_dates = pd.to_datetime(
                filtered_history["Date"],
                errors="coerce",
            )

        if end_date is not None:
            filtered_history = filtered_history[
                transaction_dates
                <= pd.Timestamp(end_date)
            ]

    return filtered_history.reset_index(
        drop=True
    )


def _build_transaction_history_csv(
    filtered_history: pd.DataFrame,
) -> bytes:
    """Return the currently filtered transaction ledger as UTF-8 CSV."""

    return filtered_history.to_csv(
        index=False,
    ).encode(
        "utf-8"
    )


def _format_currency(
    value: float,
) -> str:
    """Format a signed Indian rupee amount."""

    numeric_value = float(value)

    sign = (
        "-"
        if numeric_value < 0.0
        else ""
    )

    return (
        f"{sign}₹"
        f"{abs(numeric_value):,.2f}"
    )


def _render_transaction_cash_flow_summary(
    summary: dict[str, int | float],
) -> None:
    """Render eligible transaction counts and cash-flow totals."""

    count_columns = st.columns(2)

    count_columns[0].metric(
        "BUY Transactions",
        int(summary["buy_count"]),
    )
    count_columns[1].metric(
        "SELL Transactions",
        int(summary["sell_count"]),
    )

    amount_columns = st.columns(3)

    amount_columns[0].metric(
        "BUY Outflow",
        _format_currency(
            float(summary["buy_outflow"])
        ),
    )
    amount_columns[1].metric(
        "SELL Inflow",
        _format_currency(
            float(summary["sell_inflow"])
        ),
    )
    amount_columns[2].metric(
        "Net Cash Flow",
        _format_currency(
            float(summary["net_cash_flow"])
        ),
    )


def _import_uploaded_transactions(
    uploaded_file,
    *,
    persist: bool,
) -> tuple:
    """Process an uploaded CSV in preview or persistence mode."""

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            suffix=".csv",
            delete=False,
        ) as temporary_file:
            temporary_file.write(
                uploaded_file.getvalue()
            )
            temporary_path = Path(
                temporary_file.name
            )

        import_service = TransactionImportService()

        return import_service.import_csv(
            csv_path=temporary_path,
            portfolio_id=1,
            persist=persist,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )


def _preview_uploaded_transactions(
    uploaded_file,
) -> tuple:
    """Validate an uploaded CSV without persisting transactions."""

    return _import_uploaded_transactions(
        uploaded_file,
        persist=False,
    )


def _render_transaction_import() -> None:
    """Render the transaction-history CSV import section."""

    st.divider()
    st.subheader("📥 Import Transactions")

    st.caption(
        "Upload BUY and SELL transactions to preview them before import."
    )

    uploaded_file = st.file_uploader(
        "Upload transaction CSV",
        type=["csv"],
        key="transaction_csv_upload",
    )

    if uploaded_file is None:
        return

    try:
        transactions = _preview_uploaded_transactions(
            uploaded_file
        )
    except ValueError as error:
        st.error(
            "Transaction CSV validation failed: "
            f"{error}"
        )
        return

    if not transactions:
        st.warning(
            "No valid BUY or SELL transactions were found."
        )
        return

    preview = _build_transaction_preview(
        transactions
    )

    st.dataframe(
        preview,
        width="stretch",
        hide_index=True,
    )

    confirmed = st.checkbox(
        "I have reviewed the preview and confirm this import.",
        key="confirm_transaction_import",
    )

    import_requested = st.button(
        "Import Transactions",
        type="primary",
        disabled=not confirmed,
        key="persist_transaction_import",
    )

    if not confirmed or not import_requested:
        return

    try:
        persisted_transactions = _import_uploaded_transactions(
            uploaded_file,
            persist=True,
        )
    except ValueError as error:
        st.error(
            "Transaction import failed: "
            f"{error}"
        )
        return

    transaction_count = len(
        persisted_transactions
    )

    transaction_label = (
        "transaction"
        if transaction_count == 1
        else "transactions"
    )

    st.success(
        f"{transaction_count} {transaction_label} "
        "imported successfully. "
        "Portfolio analytics will now refresh."
    )

    st.rerun()


def _render_transaction_history() -> None:
    """Render the auditable Portfolio transaction ledger."""

    st.divider()
    st.subheader("🧾 Transaction History")

    st.caption(
        "BUY and SELL transactions are eligible for Portfolio XIRR. "
        "OPENING_BALANCE records remain visible but are excluded."
    )

    transaction_service = TransactionService()

    transaction_history = (
        transaction_service.get_transaction_history(
            portfolio_id=1,
        )
    )

    total_count = len(
        transaction_history
    )

    eligible_count = int(
        transaction_history["XIRR Eligible"]
        .fillna(False)
        .astype(bool)
        .sum()
    )

    excluded_count = (
        total_count - eligible_count
    )

    summary_columns = st.columns(3)

    summary_columns[0].metric(
        "Total Transactions",
        total_count,
    )
    summary_columns[1].metric(
        "XIRR Eligible",
        eligible_count,
    )
    summary_columns[2].metric(
        "Excluded",
        excluded_count,
    )

    if eligible_count == 0:
        st.info(
            "Portfolio XIRR is unavailable because no eligible "
            "BUY or SELL transactions exist."
        )

    transaction_type_options = sorted(
        transaction_history["Transaction Type"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    fund_options = sorted(
        transaction_history["Fund"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_transaction_types = tuple(
        st.multiselect(
            "Transaction Type",
            options=transaction_type_options,
            key="transaction_type_filter",
        )
    )

    selected_funds = tuple(
        st.multiselect(
            "Fund",
            options=fund_options,
            key="transaction_fund_filter",
        )
    )

    selected_eligibility = st.selectbox(
        "XIRR Eligibility",
        options=[
            "All",
            "Eligible",
            "Excluded",
        ],
        key="transaction_xirr_filter",
    )

    valid_dates = pd.to_datetime(
        transaction_history["Date"],
        errors="coerce",
    ).dropna()

    if valid_dates.empty:
        minimum_date = date.today()
        maximum_date = date.today()
    else:
        minimum_date = (
            valid_dates.min().date()
        )
        maximum_date = (
            valid_dates.max().date()
        )

    selected_start_date = st.date_input(
        "Start Date",
        value=minimum_date,
        min_value=minimum_date,
        max_value=maximum_date,
        key="transaction_start_date_filter",
    )

    selected_end_date = st.date_input(
        "End Date",
        value=maximum_date,
        min_value=minimum_date,
        max_value=maximum_date,
        key="transaction_end_date_filter",
    )

    filtered_history = _filter_transaction_history(
        transaction_history,
        transaction_types=selected_transaction_types,
        funds=selected_funds,
        xirr_eligibility=selected_eligibility,
        start_date=selected_start_date,
        end_date=selected_end_date,
    )

    cash_flow_summary = (
        transaction_service
        .calculate_cash_flow_summary(
            filtered_history
        )
    )

    st.markdown(
        "#### Eligible Cash-Flow Summary"
    )

    _render_transaction_cash_flow_summary(
        cash_flow_summary
    )

    st.dataframe(
        filtered_history,
        width="stretch",
        hide_index=True,
    )

    st.download_button(
        "Download Filtered Transactions",
        data=_build_transaction_history_csv(
            filtered_history
        ),
        file_name="portfolio_transactions.csv",
        mime="text/csv",
        key="download_filtered_transactions",
    )


def render_portfolio() -> None:
    """Render the complete Portfolio page."""

    st.title("📂 Portfolio")

    service = PortfolioService()
    portfolio = service.get_portfolio()

    show_portfolio_summary(
        portfolio
    )

    st.divider()

    show_portfolio(
        portfolio
    )

    _render_transaction_import()

    _render_transaction_history()

    st.divider()

    render_tax_lot_section(
        portfolio_id=1,
    )

    st.divider()

    show_history(
        service.loader.project_root
    )