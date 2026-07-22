"""Tests for the Portfolio page view."""

from unittest.mock import ANY, MagicMock, patch

import pandas as pd

from views.portfolio_view import (
    _render_transaction_import,
    render_portfolio,
)


@patch("views.portfolio_view.show_history")
@patch("views.portfolio_view.show_portfolio")
@patch("views.portfolio_view.show_portfolio_summary")
@patch("views.portfolio_view.PortfolioService")
@patch("views.portfolio_view.st.file_uploader")
def test_render_portfolio_displays_transaction_csv_uploader(
    mock_file_uploader,
    mock_portfolio_service_class,
    mock_show_portfolio_summary,
    mock_show_portfolio,
    mock_show_history,
) -> None:
    """Expose a CSV-only uploader on the Portfolio page."""

    portfolio_service = mock_portfolio_service_class.return_value
    portfolio_service.get_portfolio.return_value = pd.DataFrame()
    portfolio_service.loader.project_root = "/project"
    mock_file_uploader.return_value = None

    render_portfolio()

    mock_file_uploader.assert_called_once_with(
        "Upload transaction CSV",
        type=["csv"],
        key="transaction_csv_upload",
    )


@patch("views.portfolio_view.st.dataframe")
@patch(
    "views.portfolio_view.TransactionImportService",
    create=True,
)
@patch("views.portfolio_view.st.file_uploader")
def test_transaction_csv_upload_is_previewed_without_persistence(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
) -> None:
    """Validate and preview an upload without writing to the database."""

    uploaded_file = MagicMock()
    uploaded_file.name = "transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,122639,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    transaction = MagicMock()
    transaction.transaction_date = "2025-01-10"
    transaction.fund_id = 1
    transaction.transaction_type = "BUY"
    transaction.units = 10.0
    transaction.amount = 900.0

    import_service = mock_import_service_class.return_value
    import_service.import_csv.return_value = (transaction,)

    _render_transaction_import()

    import_service.import_csv.assert_called_once_with(
        csv_path=ANY,
        portfolio_id=1,
        persist=False,
    )

    preview = mock_dataframe.call_args.args[0]

    assert preview.to_dict("records") == [
        {
            "Date": "2025-01-10",
            "Fund ID": 1,
            "Transaction Type": "BUY",
            "Units": 10.0,
            "Amount": 900.0,
        }
    ]

@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.st.error")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_transaction_csv_validation_error_is_displayed(
    mock_file_uploader,
    mock_import_service_class,
    mock_error,
    mock_dataframe,
) -> None:
    """Display CSV validation errors without rendering a preview."""

    uploaded_file = MagicMock()
    uploaded_file.name = "invalid-transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,999999,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    import_service = mock_import_service_class.return_value
    import_service.import_csv.side_effect = ValueError(
        "unknown scheme code: 999999"
    )

    _render_transaction_import()

    mock_error.assert_called_once_with(
        "Transaction CSV validation failed: "
        "unknown scheme code: 999999"
    )
    mock_dataframe.assert_not_called()
@patch("views.portfolio_view.st.button")
@patch("views.portfolio_view.st.checkbox")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_transaction_import_requires_explicit_confirmation(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
    mock_checkbox,
    mock_button,
) -> None:
    """Keep persistence disabled until the user confirms the preview."""

    uploaded_file = MagicMock()
    uploaded_file.name = "transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,122639,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    transaction = MagicMock()
    transaction.transaction_date = "2025-01-10"
    transaction.fund_id = 1
    transaction.transaction_type = "BUY"
    transaction.units = 10.0
    transaction.amount = 900.0

    import_service = mock_import_service_class.return_value
    import_service.import_csv.return_value = (transaction,)

    mock_checkbox.return_value = False
    mock_button.return_value = False

    _render_transaction_import()

    mock_checkbox.assert_called_once_with(
        "I have reviewed the preview and confirm this import.",
        key="confirm_transaction_import",
    )

    mock_button.assert_called_once_with(
        "Import Transactions",
        type="primary",
        disabled=True,
        key="persist_transaction_import",
    )

    import_service.import_csv.assert_called_once_with(
        csv_path=ANY,
        portfolio_id=1,
        persist=False,
    )
@patch("views.portfolio_view.st.button")
@patch("views.portfolio_view.st.checkbox")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_confirmed_transaction_import_is_persisted(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
    mock_checkbox,
    mock_button,
) -> None:
    """Persist the validated CSV after confirmation and button click."""

    uploaded_file = MagicMock()
    uploaded_file.name = "transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,122639,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    transaction = MagicMock()
    transaction.transaction_date = "2025-01-10"
    transaction.fund_id = 1
    transaction.transaction_type = "BUY"
    transaction.units = 10.0
    transaction.amount = 900.0

    import_service = mock_import_service_class.return_value
    import_service.import_csv.return_value = (transaction,)

    mock_checkbox.return_value = True
    mock_button.return_value = True

    _render_transaction_import()

    assert import_service.import_csv.call_count == 2

    preview_call = import_service.import_csv.call_args_list[0]
    persistence_call = import_service.import_csv.call_args_list[1]

    assert preview_call.kwargs == {
        "csv_path": ANY,
        "portfolio_id": 1,
        "persist": False,
    }

    assert persistence_call.kwargs == {
        "csv_path": ANY,
        "portfolio_id": 1,
        "persist": True,
    }
@patch("views.portfolio_view.st.success")
@patch("views.portfolio_view.st.error")
@patch("views.portfolio_view.st.button")
@patch("views.portfolio_view.st.checkbox")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_duplicate_transaction_import_error_is_displayed(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
    mock_checkbox,
    mock_button,
    mock_error,
    mock_success,
) -> None:
    """Display duplicate rejection without reporting import success."""

    uploaded_file = MagicMock()
    uploaded_file.name = "transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,122639,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    transaction = MagicMock()
    transaction.transaction_date = "2025-01-10"
    transaction.fund_id = 1
    transaction.transaction_type = "BUY"
    transaction.units = 10.0
    transaction.amount = 900.0

    import_service = mock_import_service_class.return_value
    import_service.import_csv.side_effect = (
        (transaction,),
        ValueError("duplicate transaction"),
    )

    mock_checkbox.return_value = True
    mock_button.return_value = True

    _render_transaction_import()

    mock_error.assert_called_once_with(
        "Transaction import failed: duplicate transaction"
    )
    mock_success.assert_not_called()
@patch("views.portfolio_view.st.rerun")
@patch("views.portfolio_view.st.success")
@patch("views.portfolio_view.st.button")
@patch("views.portfolio_view.st.checkbox")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_successful_transaction_import_refreshes_portfolio(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
    mock_checkbox,
    mock_button,
    mock_success,
    mock_rerun,
) -> None:
    """Refresh portfolio analytics after successful persistence."""

    uploaded_file = MagicMock()
    uploaded_file.name = "transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
        b"10-Jan-2025,122639,BUY,10.0,900.00\n"
    )
    mock_file_uploader.return_value = uploaded_file

    transaction = MagicMock()
    transaction.transaction_date = "2025-01-10"
    transaction.fund_id = 1
    transaction.transaction_type = "BUY"
    transaction.units = 10.0
    transaction.amount = 900.0

    import_service = mock_import_service_class.return_value
    import_service.import_csv.return_value = (transaction,)

    mock_checkbox.return_value = True
    mock_button.return_value = True

    _render_transaction_import()

    mock_success.assert_called_once_with(
        "1 transaction imported successfully. "
        "Portfolio analytics will now refresh."
    )
    mock_rerun.assert_called_once_with()
@patch("views.portfolio_view.st.rerun")
@patch("views.portfolio_view.st.button")
@patch("views.portfolio_view.st.checkbox")
@patch("views.portfolio_view.st.warning")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionImportService")
@patch("views.portfolio_view.st.file_uploader")
def test_empty_transaction_preview_cannot_be_imported(
    mock_file_uploader,
    mock_import_service_class,
    mock_dataframe,
    mock_warning,
    mock_checkbox,
    mock_button,
    mock_rerun,
) -> None:
    """Do not allow persistence or refresh for an empty transaction batch."""

    uploaded_file = MagicMock()
    uploaded_file.name = "empty-transactions.csv"
    uploaded_file.getvalue.return_value = (
        b"Date,Scheme Code,Transaction Type,Units,Amount\n"
    )
    mock_file_uploader.return_value = uploaded_file

    import_service = mock_import_service_class.return_value
    import_service.import_csv.return_value = ()

    _render_transaction_import()

    mock_warning.assert_called_once_with(
        "No valid BUY or SELL transactions were found."
    )
    mock_dataframe.assert_not_called()
    mock_checkbox.assert_not_called()
    mock_button.assert_not_called()
    mock_rerun.assert_not_called()

    import_service.import_csv.assert_called_once_with(
        csv_path=ANY,
        portfolio_id=1,
        persist=False,
    )

@patch("views.portfolio_view.st.dataframe")
@patch(
    "views.portfolio_view.TransactionService",
    create=True,
)
@patch("views.portfolio_view.show_history")
@patch("views.portfolio_view.show_portfolio")
@patch("views.portfolio_view.show_portfolio_summary")
@patch("views.portfolio_view.PortfolioService")
@patch("views.portfolio_view.st.file_uploader")
def test_render_portfolio_displays_transaction_history(
    mock_file_uploader,
    mock_portfolio_service_class,
    mock_show_portfolio_summary,
    mock_show_portfolio,
    mock_show_history,
    mock_transaction_service_class,
    mock_dataframe,
) -> None:
    """Load and display the auditable Portfolio transaction ledger."""

    portfolio_service = mock_portfolio_service_class.return_value
    portfolio_service.get_portfolio.return_value = pd.DataFrame()
    portfolio_service.loader.project_root = "/project"
    mock_file_uploader.return_value = None

    transaction_history = pd.DataFrame(
        [
            {
                "Transaction ID": 1,
                "Date": "2024-12-31",
                "Fund ID": 1,
                "Transaction Type": "OPENING_BALANCE",
                "Units": 10.0,
                "NAV": 80.0,
                "Amount": 800.0,
                "XIRR Eligible": False,
                "Cash Flow": None,
            }
        ]
    )

    transaction_service = (
        mock_transaction_service_class.return_value
    )
    transaction_service.get_transaction_history.return_value = (
        transaction_history
    )

    render_portfolio()

    transaction_service.get_transaction_history.assert_called_once_with(
        portfolio_id=1,
    )

    mock_dataframe.assert_called_once_with(
        transaction_history,
        width="stretch",
        hide_index=True,
    )
@patch("views.portfolio_view.st.info")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_explains_unavailable_xirr(
    mock_transaction_service_class,
    mock_dataframe,
    mock_info,
) -> None:
    """Explain XIRR unavailability when no eligible cash flows exist."""

    from views.portfolio_view import (
        _render_transaction_history,
    )

    transaction_history = pd.DataFrame(
        [
            {
                "Transaction ID": 1,
                "Date": "2024-12-31",
                "Fund ID": 1,
                "Transaction Type": "OPENING_BALANCE",
                "Units": 10.0,
                "NAV": 80.0,
                "Amount": 800.0,
                "XIRR Eligible": False,
                "Cash Flow": None,
            }
        ]
    )

    transaction_service = (
        mock_transaction_service_class.return_value
    )
    transaction_service.get_transaction_history.return_value = (
        transaction_history
    )

    _render_transaction_history()

    mock_info.assert_called_once_with(
        "Portfolio XIRR is unavailable because no eligible "
        "BUY or SELL transactions exist."
    )
@patch("views.portfolio_view.st.columns")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_displays_eligibility_counts(
    mock_transaction_service_class,
    mock_dataframe,
    mock_columns,
) -> None:
    """Summarize total, XIRR-eligible, and excluded transactions."""

    from views.portfolio_view import (
        _render_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Date": [
                "2024-12-31",
                "2025-01-10",
                "2025-03-15",
            ],
            "Fund ID": [1, 1, 2],
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
                "SELL",
            ],
            "Units": [10.0, 10.0, 2.5],
            "NAV": [80.0, 90.0, 100.0],
            "Amount": [800.0, 900.0, 250.0],
            "XIRR Eligible": [
                False,
                True,
                True,
            ],
            "Cash Flow": [
                None,
                -900.0,
                250.0,
            ],
        }
    )

    transaction_service = (
        mock_transaction_service_class.return_value
    )
    transaction_service.get_transaction_history.return_value = (
        transaction_history
    )

    total_column = MagicMock()
    eligible_column = MagicMock()
    excluded_column = MagicMock()

    mock_columns.return_value = (
        total_column,
        eligible_column,
        excluded_column,
    )

    _render_transaction_history()

    mock_columns.assert_called_once_with(3)

    total_column.metric.assert_called_once_with(
        "Total Transactions",
        3,
    )
    eligible_column.metric.assert_called_once_with(
        "XIRR Eligible",
        2,
    )
    excluded_column.metric.assert_called_once_with(
        "Excluded",
        1,
    )