"""Tests for the repository-backed TransactionService."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pytest

from models.transaction import Transaction
from repositories.exceptions import RepositoryNotFoundError
from services.transaction_service import TransactionService


class FakeEntity:
    """Simple entity used by fake repositories."""

    def __init__(self, entity_id: int) -> None:
        self.id = entity_id


class FakePortfolioRepository:
    """In-memory portfolio repository used by service tests."""

    def __init__(self) -> None:
        self.items: dict[int, FakeEntity] = {}

    def add(self, portfolio_id: int) -> FakeEntity:
        """Create and store a fake portfolio."""

        portfolio = FakeEntity(portfolio_id)
        self.items[portfolio_id] = portfolio
        return portfolio

    def get_by_id(self, portfolio_id: int) -> FakeEntity:
        """Return a portfolio or raise when it does not exist."""

        portfolio = self.items.get(portfolio_id)

        if portfolio is None:
            raise RepositoryNotFoundError(
                f"Portfolio with id={portfolio_id} was not found."
            )

        return portfolio


class FakeFundRepository:
    """In-memory fund repository used by service tests."""

    def __init__(self) -> None:
        self.items: dict[int, FakeEntity] = {}

    def add(self, fund_id: int) -> FakeEntity:
        """Create and store a fake fund."""

        fund = FakeEntity(fund_id)
        self.items[fund_id] = fund
        return fund

    def get_by_id(self, fund_id: int) -> FakeEntity:
        """Return a fund or raise when it does not exist."""

        fund = self.items.get(fund_id)

        if fund is None:
            raise RepositoryNotFoundError(
                f"Fund with id={fund_id} was not found."
            )

        return fund


class FakeTransactionRepository:
    """In-memory transaction repository used by service tests."""

    def __init__(self) -> None:
        self.items: list[Transaction] = []
        self.add_called = False

    def add(self, transaction: Transaction) -> Transaction:
        """Store a transaction and simulate database ID assignment."""

        self.add_called = True

        if getattr(transaction, "id", None) is None:
            transaction.id = len(self.items) + 1

        self.items.append(transaction)
        return transaction

    def get_by_id(
        self,
        transaction_id: int,
    ) -> Optional[Transaction]:
        """Return a transaction by its simulated database ID."""

        for transaction in self.items:
            if transaction.id == transaction_id:
                return transaction

        return None

    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[Transaction]:
        """Return transactions belonging to a portfolio."""

        return [
            transaction
            for transaction in self.items
            if transaction.portfolio_id == portfolio_id
        ]

    def get_for_fund(
        self,
        fund_id: int,
    ) -> list[Transaction]:
        """Return transactions belonging to a fund."""

        return [
            transaction
            for transaction in self.items
            if transaction.fund_id == fund_id
        ]


class FakeUnitOfWork:
    """Minimal UnitOfWork implementation for TransactionService tests."""

    def __init__(
        self,
        transactions: Optional[FakeTransactionRepository] = None,
        portfolios: Optional[FakePortfolioRepository] = None,
        funds: Optional[FakeFundRepository] = None,
    ) -> None:
        self.transactions = (
            transactions
            if transactions is not None
            else FakeTransactionRepository()
        )

        self.portfolios = (
            portfolios
            if portfolios is not None
            else FakePortfolioRepository()
        )

        self.funds = (
            funds
            if funds is not None
            else FakeFundRepository()
        )

        self.commit_called = False
        self.rollback_called = False
        self.enter_called = False
        self.exit_called = False

    def __enter__(self) -> "FakeUnitOfWork":
        self.enter_called = True
        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> bool:
        self.exit_called = True

        if exception_type is not None:
            self.rollback()

        return False

    def commit(self) -> None:
        """Record that the UnitOfWork was committed."""

        self.commit_called = True

    def rollback(self) -> None:
        """Record that the UnitOfWork was rolled back."""

        self.rollback_called = True


def test_buy_units_creates_transaction() -> None:
    """buy_units should return a Transaction containing supplied values."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction_date = date(2026, 7, 17)

    transaction = service.buy_units(
        portfolio_id=1,
        fund_id=2,
        units=10.0,
        amount=250.0,
        transaction_date=transaction_date,
    )

    assert isinstance(transaction, Transaction)
    assert transaction.portfolio_id == 1
    assert transaction.fund_id == 2
    assert float(transaction.units) == pytest.approx(10.0)
    assert float(transaction.amount) == pytest.approx(250.0)
    assert transaction.transaction_date == transaction_date


def test_buy_units_persists_transaction() -> None:
    """buy_units should add the transaction to the repository."""

    repository = FakeTransactionRepository()
    unit_of_work = FakeUnitOfWork(transactions=repository)

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    created = service.buy_units(
        portfolio_id=10,
        fund_id=20,
        units=5.0,
        amount=100.0,
        transaction_date=date(2026, 7, 17),
    )

    stored = repository.get_by_id(created.id)

    assert repository.add_called is True
    assert len(repository.items) == 1
    assert stored is created
    assert stored.portfolio_id == 10
    assert stored.fund_id == 20


def test_buy_units_assigns_database_id() -> None:
    """The persisted transaction should receive an ID."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction = service.buy_units(
        portfolio_id=1,
        fund_id=1,
        units=2.5,
        amount=75.0,
        transaction_date=date(2026, 7, 17),
    )

    assert transaction.id is not None
    assert transaction.id == 1


def test_buy_units_uses_default_transaction_date() -> None:
    """The current date should be used when no date is supplied."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction = service.buy_units(
        portfolio_id=1,
        fund_id=2,
        units=4.0,
        amount=120.0,
    )

    assert transaction.transaction_date == date.today()


def test_buy_units_commits_unit_of_work() -> None:
    """A successful purchase should commit the UnitOfWork."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    service.buy_units(
        portfolio_id=1,
        fund_id=2,
        units=3.0,
        amount=90.0,
        transaction_date=date(2026, 7, 17),
    )

    assert unit_of_work.commit_called is True
    assert unit_of_work.rollback_called is False


def test_buy_units_uses_unit_of_work_context_manager() -> None:
    """The UnitOfWork context manager should be entered and exited."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    service.buy_units(
        portfolio_id=1,
        fund_id=2,
        units=1.0,
        amount=50.0,
        transaction_date=date(2026, 7, 17),
    )

    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True


def test_buy_units_propagates_repository_error() -> None:
    """Repository errors should propagate and prevent a commit."""

    class FailingTransactionRepository(
        FakeTransactionRepository
    ):
        def add(
            self,
            transaction: Transaction,
        ) -> Transaction:
            raise RuntimeError(
                "Unable to persist transaction."
            )

    unit_of_work = FakeUnitOfWork(
        transactions=FailingTransactionRepository()
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to persist transaction",
    ):
        service.buy_units(
            portfolio_id=1,
            fund_id=2,
            units=5.0,
            amount=100.0,
            transaction_date=date(2026, 7, 17),
        )

    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True
    assert unit_of_work.exit_called is True

@pytest.mark.parametrize(
    "units",
    [
        0.0,
        -1.0,
    ],
)
def test_sell_units_rejects_non_positive_units(
    units: float,
) -> None:
    """sell_units should reject zero or negative unit quantities."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        ValueError,
        match="units must be greater than zero",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=units,
            amount=100.0,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.enter_called is False
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is False


@pytest.mark.parametrize(
    "amount",
    [
        0.0,
        -100.0,
    ],
)
def test_sell_units_rejects_non_positive_amount(
    amount: float,
) -> None:
    """sell_units should reject zero or negative redemption amounts."""

    unit_of_work = FakeUnitOfWork()

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        ValueError,
        match="amount must be greater than zero",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=5.0,
            amount=amount,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.enter_called is False
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is False


def test_sell_units_requires_existing_portfolio() -> None:
    """sell_units should fail when the portfolio does not exist."""

    funds = FakeFundRepository()
    funds.add(2)

    unit_of_work = FakeUnitOfWork(
        funds=funds,
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        RepositoryNotFoundError,
        match=r"Portfolio with id=1 was not found",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=5.0,
            amount=100.0,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True
    assert unit_of_work.transactions.add_called is False


def test_sell_units_requires_existing_fund() -> None:
    """sell_units should fail when the fund does not exist."""

    portfolios = FakePortfolioRepository()
    portfolios.add(1)

    unit_of_work = FakeUnitOfWork(
        portfolios=portfolios,
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        RepositoryNotFoundError,
        match=r"Fund with id=2 was not found",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=5.0,
            amount=100.0,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True
    assert unit_of_work.transactions.add_called is False

def make_transaction(
    *,
    portfolio_id: int,
    fund_id: int,
    transaction_type: str,
    units: float,
    amount: float = 100.0,
    transaction_date: date = date(2026, 7, 17),
) -> Transaction:
    """Create a transaction for holdings-related service tests."""

    return Transaction(
        portfolio_id=portfolio_id,
        fund_id=fund_id,
        transaction_type=transaction_type,
        units=units,
        nav=amount / units,
        amount=amount,
        transaction_date=transaction_date,
    )


def create_sell_ready_unit_of_work(
    *,
    portfolio_id: int = 1,
    fund_id: int = 2,
) -> FakeUnitOfWork:
    """Create a UnitOfWork containing an existing portfolio and fund."""

    portfolios = FakePortfolioRepository()
    portfolios.add(portfolio_id)

    funds = FakeFundRepository()
    funds.add(fund_id)

    return FakeUnitOfWork(
        portfolios=portfolios,
        funds=funds,
    )


def test_sell_units_rejects_overselling() -> None:
    """sell_units should reject a redemption above current holdings."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
                amount=200.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="SELL",
                units=3.0,
                amount=75.0,
            ),
        ]
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        ValueError,
        match="Insufficient units",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=7.01,
            amount=175.25,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.transactions.add_called is False
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True
    assert unit_of_work.exit_called is True


def test_sell_units_allows_exact_remaining_holdings() -> None:
    """sell_units should allow redemption of all remaining units."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
                amount=200.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="SELL",
                units=3.0,
                amount=75.0,
            ),
        ]
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction = service.sell_units(
        portfolio_id=1,
        fund_id=2,
        units=7.0,
        amount=175.0,
        transaction_date=date(2026, 7, 18),
    )

    assert transaction.transaction_type == "SELL"
    assert float(transaction.units) == pytest.approx(7.0)
    assert unit_of_work.transactions.add_called is True
    assert unit_of_work.commit_called is True
    assert unit_of_work.rollback_called is False


def test_sell_units_calculates_holdings_for_selected_portfolio_and_fund() -> None:
    """Only matching portfolio and fund transactions should affect holdings."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=3,
                transaction_type="BUY",
                units=100.0,
            ),
            make_transaction(
                portfolio_id=99,
                fund_id=2,
                transaction_type="BUY",
                units=100.0,
            ),
        ]
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        ValueError,
        match="Insufficient units",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=10.01,
            amount=200.20,
            transaction_date=date(2026, 7, 18),
        )

    assert unit_of_work.transactions.add_called is False
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True


def test_sell_units_creates_redemption_transaction() -> None:
    """sell_units should create a SELL transaction with supplied values."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type="BUY",
            units=20.0,
            amount=400.0,
        )
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction_date = date(2026, 7, 18)

    transaction = service.sell_units(
        portfolio_id=1,
        fund_id=2,
        units=5.0,
        amount=125.0,
        transaction_date=transaction_date,
    )

    assert isinstance(transaction, Transaction)
    assert transaction.portfolio_id == 1
    assert transaction.fund_id == 2
    assert transaction.transaction_type == "SELL"
    assert float(transaction.units) == pytest.approx(5.0)
    assert float(transaction.amount) == pytest.approx(125.0)
    assert float(transaction.nav) == pytest.approx(25.0)
    assert transaction.transaction_date == transaction_date


def test_sell_units_persists_redemption_transaction() -> None:
    """sell_units should add the redemption to the repository."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type="BUY",
            units=20.0,
            amount=400.0,
        )
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    created = service.sell_units(
        portfolio_id=1,
        fund_id=2,
        units=5.0,
        amount=125.0,
        transaction_date=date(2026, 7, 18),
    )

    stored = unit_of_work.transactions.get_by_id(created.id)

    assert unit_of_work.transactions.add_called is True
    assert stored is created
    assert stored.transaction_type == "SELL"


def test_sell_units_uses_default_transaction_date() -> None:
    """sell_units should use today's date when no date is supplied."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type="BUY",
            units=10.0,
        )
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    transaction = service.sell_units(
        portfolio_id=1,
        fund_id=2,
        units=2.0,
        amount=50.0,
    )

    assert transaction.transaction_date == date.today()


def test_sell_units_commits_unit_of_work() -> None:
    """A successful redemption should commit the UnitOfWork."""

    unit_of_work = create_sell_ready_unit_of_work()

    unit_of_work.transactions.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type="BUY",
            units=10.0,
        )
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    service.sell_units(
        portfolio_id=1,
        fund_id=2,
        units=2.0,
        amount=50.0,
        transaction_date=date(2026, 7, 18),
    )

    assert unit_of_work.commit_called is True
    assert unit_of_work.rollback_called is False
    assert unit_of_work.enter_called is True
    assert unit_of_work.exit_called is True


def test_sell_units_propagates_repository_error_and_rolls_back() -> None:
    """Persistence failures should propagate and trigger rollback."""

    class FailingTransactionRepository(
        FakeTransactionRepository
    ):
        def add(
            self,
            transaction: Transaction,
        ) -> Transaction:
            self.add_called = True
            raise RuntimeError(
                "Unable to persist redemption transaction."
            )

    transactions = FailingTransactionRepository()

    transactions.items.append(
        make_transaction(
            portfolio_id=1,
            fund_id=2,
            transaction_type="BUY",
            units=10.0,
        )
    )

    portfolios = FakePortfolioRepository()
    portfolios.add(1)

    funds = FakeFundRepository()
    funds.add(2)

    unit_of_work = FakeUnitOfWork(
        transactions=transactions,
        portfolios=portfolios,
        funds=funds,
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to persist redemption transaction",
    ):
        service.sell_units(
            portfolio_id=1,
            fund_id=2,
            units=2.0,
            amount=50.0,
            transaction_date=date(2026, 7, 18),
        )

    assert transactions.add_called is True
    assert unit_of_work.commit_called is False
    assert unit_of_work.rollback_called is True
    assert unit_of_work.exit_called is True

def test_get_cash_flow_history_converts_buy_and_sell_signs() -> None:
    """BUY is an outflow and SELL is an inflow for investor XIRR."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="SELL",
                units=2.0,
                amount=60.0,
                transaction_date=date(2026, 3, 15),
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=10.0,
                amount=250.0,
                transaction_date=date(2026, 1, 10),
            ),
            make_transaction(
                portfolio_id=2,
                fund_id=3,
                transaction_type="BUY",
                units=5.0,
                amount=100.0,
                transaction_date=date(2026, 2, 1),
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository,
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    history = service.get_cash_flow_history(
        portfolio_id=1,
    )

    assert history.to_dict("records") == [
        {
            "Date": date(2026, 1, 10),
            "Amount": -250.0,
        },
        {
            "Date": date(2026, 3, 15),
            "Amount": 60.0,
        },
    ]

def test_get_cash_flow_history_excludes_opening_balances() -> None:
    """Imported holdings lack genuine purchase dates and cannot drive XIRR."""

    repository = FakeTransactionRepository()

    repository.items.extend(
        [
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="OPENING_BALANCE",
                units=10.0,
                amount=250.0,
                transaction_date=date(2026, 7, 17),
            ),
            make_transaction(
                portfolio_id=1,
                fund_id=2,
                transaction_type="BUY",
                units=2.0,
                amount=60.0,
                transaction_date=date(2026, 7, 18),
            ),
        ]
    )

    unit_of_work = FakeUnitOfWork(
        transactions=repository,
    )

    service = TransactionService(
        unit_of_work_factory=lambda: unit_of_work,
    )

    history = service.get_cash_flow_history(
        portfolio_id=1,
    )

    assert history.to_dict("records") == [
        {
            "Date": date(2026, 7, 18),
            "Amount": -60.0,
        },
    ]

def test_transaction_service_uses_default_unit_of_work() -> None:
    """The application service should use the production UoW by default."""

    from repositories.unit_of_work import UnitOfWork

    service = TransactionService()

    assert service._unit_of_work_factory is UnitOfWork

def test_get_transaction_history_labels_xirr_eligibility() -> None:
    """Return a fund-labelled ledger including opening balances."""

    from datetime import date
    from types import SimpleNamespace

    import pandas as pd

    from services.transaction_service import TransactionService

    fund_one = SimpleNamespace(
        scheme_code="122639",
        name="UTI Nifty 50 Index Fund",
    )

    fund_two = SimpleNamespace(
        scheme_code="120503",
        name="Parag Parikh Flexi Cap Fund",
    )

    transactions = [
        SimpleNamespace(
            id=1,
            portfolio_id=1,
            fund_id=1,
            fund=fund_one,
            transaction_date=date(2024, 12, 31),
            transaction_type="OPENING_BALANCE",
            units=10.0,
            nav=80.0,
            amount=800.0,
        ),
        SimpleNamespace(
            id=2,
            portfolio_id=1,
            fund_id=1,
            fund=fund_one,
            transaction_date=date(2025, 1, 10),
            transaction_type="BUY",
            units=10.0,
            nav=90.0,
            amount=900.0,
        ),
        SimpleNamespace(
            id=3,
            portfolio_id=1,
            fund_id=2,
            fund=fund_two,
            transaction_date=date(2025, 3, 15),
            transaction_type="SELL",
            units=2.5,
            nav=100.0,
            amount=250.0,
        ),
    ]

    class FakeTransactionRepository:
        def get_for_portfolio(
            self,
            portfolio_id: int,
        ):
            assert portfolio_id == 1
            return transactions

    class FakeUnitOfWork:
        def __init__(self) -> None:
            self.transactions = FakeTransactionRepository()

        def __enter__(self):
            return self

        def __exit__(
            self,
            exception_type,
            exception_value,
            traceback,
        ) -> None:
            return None

    service = TransactionService(
        unit_of_work_factory=FakeUnitOfWork,
    )

    result = service.get_transaction_history(
        portfolio_id=1,
    )

    assert result.columns.tolist() == [
        "Transaction ID",
        "Date",
        "Fund ID",
        "Scheme Code",
        "Fund",
        "Transaction Type",
        "Units",
        "NAV",
        "Amount",
        "XIRR Eligible",
        "Cash Flow",
    ]

    assert result["Scheme Code"].tolist() == [
        "122639",
        "122639",
        "120503",
    ]

    assert result["Fund"].tolist() == [
        "UTI Nifty 50 Index Fund",
        "UTI Nifty 50 Index Fund",
        "Parag Parikh Flexi Cap Fund",
    ]

    assert result["Transaction Type"].tolist() == [
        "OPENING_BALANCE",
        "BUY",
        "SELL",
    ]

    assert result["XIRR Eligible"].tolist() == [
        False,
        True,
        True,
    ]

    assert pd.isna(
        result.loc[0, "Cash Flow"]
    )
    assert (
        result.loc[1, "Cash Flow"]
        == -900.0
    )
    assert (
        result.loc[2, "Cash Flow"]
        == 250.0
    )
def test_calculate_cash_flow_summary_excludes_opening_balances() -> None:
    """Summarize only XIRR-eligible BUY and SELL cash flows."""

    import pandas as pd

    from services.transaction_service import (
        TransactionService,
    )

    transaction_history = pd.DataFrame(
        {
            "Transaction Type": [
                "OPENING_BALANCE",
                "BUY",
                "SELL",
            ],
            "Amount": [
                800.0,
                900.0,
                250.0,
            ],
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
        TransactionService
        .calculate_cash_flow_summary(
            transaction_history
        )
    )

    assert result == {
        "buy_count": 1,
        "sell_count": 1,
        "buy_outflow": 900.0,
        "sell_inflow": 250.0,
        "net_cash_flow": -650.0,
    }