from datetime import date

from services.transaction_import_service import (
    TransactionImportService,
)


def test_load_transaction_history_csv(tmp_path) -> None:
    csv_path = tmp_path / "transactions.csv"

    csv_path.write_text(
        "Date,Scheme Code,Transaction Type,Units,Amount\n"
        "15-Mar-2025,120503,SELL,2.5,250.00\n"
        "10-Jan-2025,122639,BUY,10.0,900.00\n",
        encoding="utf-8",
    )

    result = TransactionImportService().load_csv(
        csv_path=csv_path,
    )

    assert result.to_dict("records") == [
        {
            "Date": date(2025, 1, 10),
            "Scheme Code": "122639",
            "Transaction Type": "BUY",
            "Units": 10.0,
            "Amount": 900.0,
        },
        {
            "Date": date(2025, 3, 15),
            "Scheme Code": "120503",
            "Transaction Type": "SELL",
            "Units": 2.5,
            "Amount": 250.0,
        },
    ]

def test_resolve_funds_adds_existing_fund_ids() -> None:
    import pandas as pd

    class FakeFund:
        def __init__(
            self,
            fund_id: int,
        ) -> None:
            self.id = fund_id

    class FakeFundRepository:
        def __init__(self) -> None:
            self.funds = {
                "122639": FakeFund(1),
                "120503": FakeFund(2),
            }

        def get_by_scheme_code(
            self,
            scheme_code: str,
        ):
            return self.funds.get(scheme_code)

    class FakeUnitOfWork:
        def __init__(self) -> None:
            self.funds = FakeFundRepository()

        def __enter__(self):
            return self

        def __exit__(
            self,
            exception_type,
            exception_value,
            traceback,
        ) -> None:
            return None

    transactions = pd.DataFrame(
        {
            "Date": [
                date(2025, 1, 10),
                date(2025, 3, 15),
            ],
            "Scheme Code": [
                "122639",
                "120503",
            ],
            "Transaction Type": [
                "BUY",
                "SELL",
            ],
            "Units": [
                10.0,
                2.5,
            ],
            "Amount": [
                900.0,
                250.0,
            ],
        }
    )

    unit_of_work = FakeUnitOfWork()

    service = TransactionImportService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    result = service.resolve_funds(
        transactions
    )

    assert result["Fund ID"].tolist() == [
        1,
        2,
    ]

def test_build_transactions_creates_unsaved_entities() -> None:
    import pandas as pd

    from models.transaction import Transaction

    resolved = pd.DataFrame(
        {
            "Date": [
                date(2025, 1, 10),
                date(2025, 3, 15),
            ],
            "Scheme Code": [
                "122639",
                "120503",
            ],
            "Transaction Type": [
                "BUY",
                "SELL",
            ],
            "Units": [
                10.0,
                2.5,
            ],
            "Amount": [
                900.0,
                250.0,
            ],
            "Fund ID": [
                1,
                2,
            ],
        }
    )

    transactions = (
        TransactionImportService()
        .build_transactions(
            portfolio_id=1,
            resolved_transactions=resolved,
        )
    )

    assert len(transactions) == 2
    assert all(
        isinstance(transaction, Transaction)
        for transaction in transactions
    )

    assert transactions[0].portfolio_id == 1
    assert transactions[0].fund_id == 1
    assert transactions[0].transaction_type == "BUY"
    assert transactions[0].transaction_date == date(2025, 1, 10)
    assert float(transactions[0].units) == 10.0
    assert float(transactions[0].amount) == 900.0
    assert float(transactions[0].nav) == 90.0

    assert transactions[1].portfolio_id == 1
    assert transactions[1].fund_id == 2
    assert transactions[1].transaction_type == "SELL"
    assert float(transactions[1].nav) == 100.0

def test_save_transactions_persists_single_batch() -> None:
    from models.transaction import Transaction

    class FakeTransactionRepository:
        def __init__(self) -> None:
            self.items = []

        def add(
            self,
            transaction: Transaction,
        ) -> Transaction:
            transaction.id = len(self.items) + 1
            self.items.append(transaction)
            return transaction

        def get_for_portfolio(
            self,
            portfolio_id: int,
        ):
            return [
                transaction
                for transaction in self.items
                if transaction.portfolio_id == portfolio_id
            ]
    class FakeUnitOfWork:
        def __init__(self) -> None:
            self.transactions = FakeTransactionRepository()
            self.commit_called = False
            self.enter_called = False
            self.exit_called = False

        def __enter__(self):
            self.enter_called = True
            return self

        def __exit__(
            self,
            exception_type,
            exception_value,
            traceback,
        ) -> None:
            self.exit_called = True

        def commit(self) -> None:
            self.commit_called = True

    transactions = (
        Transaction(
            portfolio_id=1,
            fund_id=1,
            transaction_date=date(2025, 1, 10),
            transaction_type="BUY",
            units=10.0,
            nav=90.0,
            amount=900.0,
        ),
        Transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_date=date(2025, 3, 15),
            transaction_type="SELL",
            units=2.5,
            nav=100.0,
            amount=250.0,
        ),
    )

    unit_of_work = FakeUnitOfWork()

    service = TransactionImportService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    saved = service.save_transactions(
        transactions
    )

    assert saved == transactions
    assert unit_of_work.transactions.items == list(
        transactions
    )
    assert unit_of_work.commit_called is True
    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True

def test_import_csv_is_preview_only_by_default(
    tmp_path,
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import pandas as pd

    csv_path = tmp_path / "transactions.csv"
    csv_path.write_text(
        "placeholder",
        encoding="utf-8",
    )

    loaded = pd.DataFrame(
        {
            "Scheme Code": ["122639"],
        }
    )

    resolved = pd.DataFrame(
        {
            "Scheme Code": ["122639"],
            "Fund ID": [1],
        }
    )

    prepared = (Mock(),)

    service = TransactionImportService()

    load_csv = Mock(return_value=loaded)
    resolve_funds = Mock(return_value=resolved)
    build_transactions = Mock(return_value=prepared)
    save_transactions = Mock()

    monkeypatch.setattr(
        service,
        "load_csv",
        load_csv,
    )
    monkeypatch.setattr(
        service,
        "resolve_funds",
        resolve_funds,
    )
    monkeypatch.setattr(
        service,
        "build_transactions",
        build_transactions,
    )
    monkeypatch.setattr(
        service,
        "save_transactions",
        save_transactions,
    )

    result = service.import_csv(
        csv_path=csv_path,
        portfolio_id=1,
    )

    load_csv.assert_called_once_with(
        csv_path=csv_path,
    )
    resolve_funds.assert_called_once_with(
        loaded
    )
    build_transactions.assert_called_once_with(
        portfolio_id=1,
        resolved_transactions=resolved,
    )
    save_transactions.assert_not_called()
    assert result is prepared

def test_save_transactions_rejects_duplicate_import() -> None:
    import pytest

    from models.transaction import Transaction

    existing = Transaction(
        portfolio_id=1,
        fund_id=1,
        transaction_date=date(2025, 1, 10),
        transaction_type="BUY",
        units=10.0,
        nav=90.0,
        amount=900.0,
    )

    duplicate = Transaction(
        portfolio_id=1,
        fund_id=1,
        transaction_date=date(2025, 1, 10),
        transaction_type="BUY",
        units=10.0,
        nav=90.0,
        amount=900.0,
    )

    class FakeTransactionRepository:
        def __init__(self) -> None:
            self.items = [existing]
            self.add_called = False

        def get_for_portfolio(
            self,
            portfolio_id: int,
        ):
            return [
                transaction
                for transaction in self.items
                if transaction.portfolio_id == portfolio_id
            ]

        def add(
            self,
            transaction: Transaction,
        ) -> Transaction:
            self.add_called = True
            self.items.append(transaction)
            return transaction

    class FakeUnitOfWork:
        def __init__(self) -> None:
            self.transactions = FakeTransactionRepository()
            self.commit_called = False

        def __enter__(self):
            return self

        def __exit__(
            self,
            exception_type,
            exception_value,
            traceback,
        ) -> None:
            return None

        def commit(self) -> None:
            self.commit_called = True

    unit_of_work = FakeUnitOfWork()

    service = TransactionImportService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    with pytest.raises(
        ValueError,
        match="duplicate transaction",
    ):
        service.save_transactions(
            (duplicate,)
        )

    assert unit_of_work.transactions.add_called is False
    assert unit_of_work.commit_called is False

def test_load_csv_rejects_future_transaction_dates(
    tmp_path,
) -> None:
    import pytest

    csv_path = tmp_path / "future_transactions.csv"

    csv_path.write_text(
        "Date,Scheme Code,Transaction Type,Units,Amount\n"
        "31-Dec-2099,122639,BUY,10.0,900.00\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="future transaction dates",
    ):
        TransactionImportService().load_csv(
            csv_path=csv_path,
        )