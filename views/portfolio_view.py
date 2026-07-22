"""Portfolio page view."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from dashboard.components.history import show_history
from dashboard.components.portfolio import show_portfolio
from dashboard.components.portfolio_summary import show_portfolio_summary
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
        transactions = (
            _preview_uploaded_transactions(
                uploaded_file
            )
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
        persisted_transactions = (
            _import_uploaded_transactions(
                uploaded_file,
                persist=True,
            )
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
        transaction_history[
            "XIRR Eligible"
        ]
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

    st.dataframe(
        transaction_history,
        width="stretch",
        hide_index=True,
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

    show_history(
        service.loader.project_root
    )