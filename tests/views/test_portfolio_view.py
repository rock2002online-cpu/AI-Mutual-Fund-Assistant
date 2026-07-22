"""Tests for the Portfolio page view."""

from unittest.mock import ANY, MagicMock, call, patch

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
                "Scheme Code": "122639",
                "Fund": "UTI Nifty 50 Index Fund",
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

    mock_dataframe.assert_called_once()

    rendered_history = (
        mock_dataframe.call_args.args[0]
    )

    pd.testing.assert_frame_equal(
        rendered_history,
        transaction_history,
    )

    assert mock_dataframe.call_args.kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
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
                "Scheme Code": "122639",
                "Fund": "UTI Nifty 50 Index Fund",
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
            "Scheme Code": [
                "122639",
                "122639",
                "120503",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
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

    mock_columns.side_effect = [
        (
            total_column,
            eligible_column,
            excluded_column,
        ),
        (
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ),
    ]

    _render_transaction_history()

    assert mock_columns.call_args_list == [
        call(3),
        call(2),
        call(3),
    ]

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

def test_filter_transaction_history_by_transaction_type() -> None:
    """Filter the ledger without modifying the source dataframe."""

    from views import portfolio_view

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Date": [
                "2024-12-31",
                "2025-01-10",
                "2025-03-15",
            ],
            "Fund ID": [1, 1, 2],
            "Scheme Code": [
                "122639",
                "122639",
                "120503",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
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

    result = (
        portfolio_view
        ._filter_transaction_history(
            transaction_history,
            transaction_types=("BUY",),
            funds=(),
            xirr_eligibility="All",
        )
    )

    assert result["Transaction Type"].tolist() == [
        "BUY",
    ]
    assert result.index.tolist() == [0]
    assert len(transaction_history) == 3

def test_filter_transaction_history_by_fund() -> None:
    """Filter the ledger by one or more selected fund names."""

    from views.portfolio_view import (
        _filter_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
                "SELL",
            ],
            "XIRR Eligible": [
                False,
                True,
                True,
            ],
        }
    )

    result = _filter_transaction_history(
        transaction_history,
        transaction_types=(),
        funds=(
            "Parag Parikh Flexi Cap Fund",
        ),
        xirr_eligibility="All",
    )

    assert result["Fund"].tolist() == [
        "Parag Parikh Flexi Cap Fund",
    ]
    assert result["Transaction ID"].tolist() == [
        3,
    ]
    assert len(transaction_history) == 3
def test_filter_transaction_history_by_xirr_eligibility() -> None:
    """Filter the ledger to transactions excluded from XIRR."""

    from views.portfolio_view import (
        _filter_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
                "SELL",
            ],
            "XIRR Eligible": [
                False,
                True,
                True,
            ],
        }
    )

    result = _filter_transaction_history(
        transaction_history,
        transaction_types=(),
        funds=(),
        xirr_eligibility="Excluded",
    )

    assert result["Transaction ID"].tolist() == [
        1,
    ]
    assert result["XIRR Eligible"].tolist() == [
        False,
    ]
    assert len(transaction_history) == 3
@patch("views.portfolio_view.st.selectbox")
@patch("views.portfolio_view.st.multiselect")
@patch("views.portfolio_view.st.columns")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_applies_selected_filters(
    mock_transaction_service_class,
    mock_dataframe,
    mock_columns,
    mock_multiselect,
    mock_selectbox,
) -> None:
    """Render only rows matching the selected ledger filters."""

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
            "Scheme Code": [
                "122639",
                "122639",
                "120503",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
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

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    mock_multiselect.side_effect = [
        ["BUY"],
        [],
    ]
    mock_selectbox.return_value = "All"

    _render_transaction_history()

    assert mock_multiselect.call_count == 2

    mock_selectbox.assert_called_once_with(
        "XIRR Eligibility",
        options=[
            "All",
            "Eligible",
            "Excluded",
        ],
        key="transaction_xirr_filter",
    )

    expected = transaction_history.iloc[
        [1]
    ].reset_index(
        drop=True
    )

    mock_dataframe.assert_called_once()

    rendered_history = (
        mock_dataframe.call_args.args[0]
    )

    pd.testing.assert_frame_equal(
        rendered_history,
        expected,
    )

    assert mock_dataframe.call_args.kwargs == {
        "width": "stretch",
        "hide_index": True,
    }
def test_build_transaction_history_csv_uses_filtered_rows() -> None:
    """Export only the transaction rows currently visible to the user."""

    from views import portfolio_view

    filtered_history = pd.DataFrame(
        {
            "Transaction ID": [3],
            "Date": ["2025-03-15"],
            "Fund ID": [2],
            "Scheme Code": ["120503"],
            "Fund": [
                "Parag Parikh Flexi Cap Fund",
            ],
            "Transaction Type": ["SELL"],
            "Units": [2.5],
            "NAV": [100.0],
            "Amount": [250.0],
            "XIRR Eligible": [True],
            "Cash Flow": [250.0],
        }
    )

    result = (
        portfolio_view
        ._build_transaction_history_csv(
            filtered_history
        )
    )

    assert isinstance(result, bytes)

    csv_text = result.decode("utf-8")

    assert (
        "Transaction ID,Date,Fund ID,Scheme Code,Fund,"
        "Transaction Type,Units,NAV,Amount,"
        "XIRR Eligible,Cash Flow"
        in csv_text
    )

    assert (
        "3,2025-03-15,2,120503,"
        "Parag Parikh Flexi Cap Fund,"
        "SELL,2.5,100.0,250.0,True,250.0"
        in csv_text
    )

    assert "UTI Nifty 50 Index Fund" not in csv_text
@patch("views.portfolio_view.st.download_button")
@patch("views.portfolio_view.st.selectbox")
@patch("views.portfolio_view.st.multiselect")
@patch("views.portfolio_view.st.columns")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_downloads_filtered_csv(
    mock_transaction_service_class,
    mock_dataframe,
    mock_columns,
    mock_multiselect,
    mock_selectbox,
    mock_download_button,
) -> None:
    """Download the currently filtered transaction ledger."""

    from views.portfolio_view import (
        _render_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [2],
            "Date": ["2025-01-10"],
            "Fund ID": [1],
            "Scheme Code": ["122639"],
            "Fund": [
                "UTI Nifty 50 Index Fund",
            ],
            "Transaction Type": ["BUY"],
            "Units": [10.0],
            "NAV": [90.0],
            "Amount": [900.0],
            "XIRR Eligible": [True],
            "Cash Flow": [-900.0],
        }
    )

    transaction_service = (
        mock_transaction_service_class.return_value
    )
    transaction_service.get_transaction_history.return_value = (
        transaction_history
    )

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    mock_multiselect.side_effect = [
        ["BUY"],
        [],
    ]
    mock_selectbox.return_value = "All"

    _render_transaction_history()

    expected_csv = transaction_history.to_csv(
        index=False,
    ).encode(
        "utf-8"
    )

    mock_download_button.assert_called_once_with(
        "Download Filtered Transactions",
        data=expected_csv,
        file_name="portfolio_transactions.csv",
        mime="text/csv",
        key="download_filtered_transactions",
    )
def test_filter_transaction_history_by_date_range() -> None:
    """Filter transactions using inclusive start and end dates."""

    from datetime import date

    from views.portfolio_view import (
        _filter_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Date": [
                "2024-12-31",
                "2025-01-10",
                "2025-03-15",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
                "SELL",
            ],
            "XIRR Eligible": [
                False,
                True,
                True,
            ],
        }
    )

    result = _filter_transaction_history(
        transaction_history,
        transaction_types=(),
        funds=(),
        xirr_eligibility="All",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

    assert result["Transaction ID"].tolist() == [
        2,
    ]
    assert len(transaction_history) == 3
@patch("views.portfolio_view.st.download_button")
@patch("views.portfolio_view.st.date_input")
@patch("views.portfolio_view.st.selectbox")
@patch("views.portfolio_view.st.multiselect")
@patch("views.portfolio_view.st.columns")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_applies_date_range_controls(
    mock_transaction_service_class,
    mock_dataframe,
    mock_columns,
    mock_multiselect,
    mock_selectbox,
    mock_date_input,
    mock_download_button,
) -> None:
    """Apply inclusive start and end dates to the visible ledger."""

    from datetime import date

    from views.portfolio_view import (
        _render_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2, 3],
            "Date": [
                date(2024, 12, 31),
                date(2025, 1, 10),
                date(2025, 3, 15),
            ],
            "Fund ID": [1, 1, 2],
            "Scheme Code": [
                "122639",
                "122639",
                "120503",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
                "Parag Parikh Flexi Cap Fund",
            ],
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

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    mock_multiselect.side_effect = [
        [],
        [],
    ]
    mock_selectbox.return_value = "All"
    mock_date_input.side_effect = [
        date(2025, 1, 1),
        date(2025, 1, 31),
    ]

    _render_transaction_history()

    assert mock_date_input.call_count == 2

    expected = transaction_history.iloc[
        [1]
    ].reset_index(
        drop=True
    )

    rendered_history = (
        mock_dataframe.call_args.args[0]
    )

    pd.testing.assert_frame_equal(
        rendered_history,
        expected,
    )
@patch("views.portfolio_view.st.columns")
def test_render_transaction_cash_flow_summary(
    mock_columns,
) -> None:
    """Render eligible transaction counts and signed cash-flow totals."""

    from views import portfolio_view

    buy_count_column = MagicMock()
    sell_count_column = MagicMock()

    buy_outflow_column = MagicMock()
    sell_inflow_column = MagicMock()
    net_cash_flow_column = MagicMock()

    mock_columns.side_effect = [
        (
            buy_count_column,
            sell_count_column,
        ),
        (
            buy_outflow_column,
            sell_inflow_column,
            net_cash_flow_column,
        ),
    ]

    portfolio_view._render_transaction_cash_flow_summary(
        {
            "buy_count": 1,
            "sell_count": 1,
            "buy_outflow": 900.0,
            "sell_inflow": 250.0,
            "net_cash_flow": -650.0,
        }
    )

    assert mock_columns.call_args_list == [
        call(2),
        call(3),
    ]

    buy_count_column.metric.assert_called_once_with(
        "BUY Transactions",
        1,
    )
    sell_count_column.metric.assert_called_once_with(
        "SELL Transactions",
        1,
    )
    buy_outflow_column.metric.assert_called_once_with(
        "BUY Outflow",
        "₹900.00",
    )
    sell_inflow_column.metric.assert_called_once_with(
        "SELL Inflow",
        "₹250.00",
    )
    net_cash_flow_column.metric.assert_called_once_with(
        "Net Cash Flow",
        "-₹650.00",
    )
@patch(
    "views.portfolio_view."
    "_render_transaction_cash_flow_summary"
)
@patch("views.portfolio_view.st.download_button")
@patch("views.portfolio_view.st.date_input")
@patch("views.portfolio_view.st.selectbox")
@patch("views.portfolio_view.st.multiselect")
@patch("views.portfolio_view.st.columns")
@patch("views.portfolio_view.st.dataframe")
@patch("views.portfolio_view.TransactionService")
def test_transaction_history_summarizes_filtered_cash_flows(
    mock_transaction_service_class,
    mock_dataframe,
    mock_columns,
    mock_multiselect,
    mock_selectbox,
    mock_date_input,
    mock_download_button,
    mock_render_cash_flow_summary,
) -> None:
    """Calculate cash-flow metrics from only the visible ledger rows."""

    from datetime import date

    from views.portfolio_view import (
        _render_transaction_history,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction ID": [1, 2],
            "Date": [
                date(2024, 12, 31),
                date(2025, 1, 10),
            ],
            "Fund ID": [1, 1],
            "Scheme Code": [
                "122639",
                "122639",
            ],
            "Fund": [
                "UTI Nifty 50 Index Fund",
                "UTI Nifty 50 Index Fund",
            ],
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
            ],
            "Units": [10.0, 10.0],
            "NAV": [80.0, 90.0],
            "Amount": [800.0, 900.0],
            "XIRR Eligible": [
                False,
                True,
            ],
            "Cash Flow": [
                None,
                -900.0,
            ],
        }
    )

    transaction_service = (
        mock_transaction_service_class.return_value
    )
    transaction_service.get_transaction_history.return_value = (
        transaction_history
    )

    cash_flow_summary = {
        "buy_count": 1,
        "sell_count": 0,
        "buy_outflow": 900.0,
        "sell_inflow": 0.0,
        "net_cash_flow": -900.0,
    }

    transaction_service.calculate_cash_flow_summary.return_value = (
        cash_flow_summary
    )

    mock_columns.return_value = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    mock_multiselect.side_effect = [
        ["BUY"],
        [],
    ]
    mock_selectbox.return_value = "All"
    mock_date_input.side_effect = [
        date(2024, 12, 31),
        date(2025, 1, 10),
    ]

    _render_transaction_history()

    transaction_service.calculate_cash_flow_summary.assert_called_once()

    summarized_history = (
        transaction_service
        .calculate_cash_flow_summary
        .call_args
        .args[0]
    )

    expected_history = transaction_history.iloc[
        [1]
    ].reset_index(
        drop=True
    )

    pd.testing.assert_frame_equal(
        summarized_history,
        expected_history,
    )

    mock_render_cash_flow_summary.assert_called_once_with(
        cash_flow_summary
    )