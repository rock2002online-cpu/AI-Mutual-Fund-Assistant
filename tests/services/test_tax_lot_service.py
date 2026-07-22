"""Tests for FIFO tax-lot analytics."""

from datetime import date
from decimal import Decimal

from models.transaction import Transaction
from services.tax_lot_service import TaxLotService
import pytest

def test_analyze_single_buy_creates_open_tax_lot() -> None:
    """A BUY transaction should create one fully open tax lot."""

    transaction = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("100.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("1000.00"),
    )

    analysis = TaxLotService().analyze(
        transactions=[transaction],
    )

    assert analysis.realized_gains == []
    assert len(analysis.open_lots) == 1

    lot = analysis.open_lots[0]

    assert lot.fund_id == 20
    assert lot.source_transaction_id == 1
    assert lot.acquisition_date == date(2026, 1, 10)
    assert lot.original_units == Decimal("100.000000")
    assert lot.remaining_units == Decimal("100.000000")
    assert lot.cost_per_unit == Decimal("10.0000")
    assert lot.remaining_cost_basis == Decimal("1000.00")
def test_analyze_partial_sell_consumes_oldest_lot() -> None:
    """A partial SELL should consume units from the oldest open lot."""

    buy = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("100.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("1000.00"),
    )

    sell = Transaction(
        id=2,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 2, 10),
        transaction_type="SELL",
        units=Decimal("40.000000"),
        nav=Decimal("15.0000"),
        amount=Decimal("600.00"),
    )

    analysis = TaxLotService().analyze(
        transactions=[buy, sell],
    )

    assert len(analysis.open_lots) == 1

    lot = analysis.open_lots[0]

    assert lot.remaining_units == Decimal("60.000000")
    assert lot.remaining_cost_basis == Decimal("600.00")

    assert len(analysis.realized_gains) == 1

    realized_gain = analysis.realized_gains[0]

    assert realized_gain.sell_transaction_id == 2
    assert realized_gain.source_buy_transaction_id == 1
    assert realized_gain.fund_id == 20
    assert realized_gain.units_sold == Decimal("40.000000")
    assert realized_gain.sale_proceeds == Decimal("600.00")
    assert realized_gain.cost_basis == Decimal("400.00")
    assert realized_gain.realized_gain == Decimal("200.00")
def test_analyze_rejects_sell_exceeding_available_units() -> None:
    """A SELL cannot consume more units than the fund owns."""

    buy = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("100.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("1000.00"),
    )

    sell = Transaction(
        id=2,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 2, 10),
        transaction_type="SELL",
        units=Decimal("101.000000"),
        nav=Decimal("15.0000"),
        amount=Decimal("1515.00"),
    )

    with pytest.raises(
        ValueError,
        match="Insufficient units",
    ):
        TaxLotService().analyze(
            transactions=[buy, sell],
        )
def test_analyze_does_not_share_units_between_portfolios() -> None:
    """A portfolio cannot sell units owned by another portfolio."""

    first_portfolio_buy = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("100.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("1000.00"),
    )

    second_portfolio_sell = Transaction(
        id=2,
        portfolio_id=11,
        fund_id=20,
        transaction_date=date(2026, 2, 10),
        transaction_type="SELL",
        units=Decimal("10.000000"),
        nav=Decimal("15.0000"),
        amount=Decimal("150.00"),
    )

    with pytest.raises(
        ValueError,
        match="Insufficient units",
    ):
        TaxLotService().analyze(
            transactions=[
                first_portfolio_buy,
                second_portfolio_sell,
            ],
        )
def test_analyze_opening_balance_creates_open_tax_lot() -> None:
    """An opening balance establishes units without being a cash flow."""

    opening_balance = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 1),
        transaction_type="OPENING_BALANCE",
        units=Decimal("75.000000"),
        nav=Decimal("12.0000"),
        amount=Decimal("900.00"),
    )

    analysis = TaxLotService().analyze(
        transactions=[opening_balance],
    )

    assert analysis.realized_gains == []
    assert len(analysis.open_lots) == 1

    lot = analysis.open_lots[0]

    assert lot.portfolio_id == 10
    assert lot.fund_id == 20
    assert lot.source_transaction_id == 1
    assert lot.acquisition_date == date(2026, 1, 1)
    assert lot.original_units == Decimal("75.000000")
    assert lot.remaining_units == Decimal("75.000000")
    assert lot.cost_per_unit == Decimal("12.0000")
    assert lot.remaining_cost_basis == Decimal("900.00")
def test_analyze_preserves_sell_amount_across_multiple_lots() -> None:
    """Allocated proceeds must add up exactly to the SELL amount."""

    transactions = [
        Transaction(
            id=1,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 1, 1),
            transaction_type="BUY",
            units=Decimal("1.000000"),
            nav=Decimal("10.0000"),
            amount=Decimal("10.00"),
        ),
        Transaction(
            id=2,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 1, 2),
            transaction_type="BUY",
            units=Decimal("1.000000"),
            nav=Decimal("20.0000"),
            amount=Decimal("20.00"),
        ),
        Transaction(
            id=3,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 1, 3),
            transaction_type="BUY",
            units=Decimal("1.000000"),
            nav=Decimal("30.0000"),
            amount=Decimal("30.00"),
        ),
        Transaction(
            id=4,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 2, 1),
            transaction_type="SELL",
            units=Decimal("3.000000"),
            nav=Decimal("33.3333"),
            amount=Decimal("100.00"),
        ),
    ]

    analysis = TaxLotService().analyze(
        transactions=transactions,
    )

    assert len(analysis.realized_gains) == 3

    total_proceeds = sum(
        (
            match.sale_proceeds
            for match in analysis.realized_gains
        ),
        start=Decimal("0.00"),
    )
    total_cost_basis = sum(
        (
            match.cost_basis
            for match in analysis.realized_gains
        ),
        start=Decimal("0.00"),
    )
    total_realized_gain = sum(
        (
            match.realized_gain
            for match in analysis.realized_gains
        ),
        start=Decimal("0.00"),
    )

    assert total_proceeds == Decimal("100.00")
    assert total_cost_basis == Decimal("60.00")
    assert total_realized_gain == Decimal("40.00")
def test_analyze_rejects_unsupported_transaction_type() -> None:
    """Unknown transaction types must not be silently ignored."""

    transaction = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="TRANSFER",
        units=Decimal("25.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("250.00"),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported transaction type",
    ):
        TaxLotService().analyze(
            transactions=[transaction],
        )
def test_analyze_rejects_zero_transaction_units() -> None:
    """Every transaction must contain a positive unit quantity."""

    transaction = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("0.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("0.00"),
    )

    with pytest.raises(
        ValueError,
        match="units must be positive",
    ):
        TaxLotService().analyze(
            transactions=[transaction],
        )
def test_analyze_rejects_zero_transaction_amount() -> None:
    """Every transaction must contain a positive monetary amount."""

    transaction = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("10.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("0.00"),
    )

    with pytest.raises(
        ValueError,
        match="amount must be positive",
    ):
        TaxLotService().analyze(
            transactions=[transaction],
        )
def test_realized_gain_records_holding_period() -> None:
    """A realized match should expose its acquisition and disposal dates."""

    buy = Transaction(
        id=1,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 1, 10),
        transaction_type="BUY",
        units=Decimal("10.000000"),
        nav=Decimal("10.0000"),
        amount=Decimal("100.00"),
    )

    sell = Transaction(
        id=2,
        portfolio_id=10,
        fund_id=20,
        transaction_date=date(2026, 2, 10),
        transaction_type="SELL",
        units=Decimal("10.000000"),
        nav=Decimal("15.0000"),
        amount=Decimal("150.00"),
    )

    analysis = TaxLotService().analyze(
        transactions=[buy, sell],
    )

    realized_gain = analysis.realized_gains[0]

    assert realized_gain.acquisition_date == date(2026, 1, 10)
    assert realized_gain.disposal_date == date(2026, 2, 10)
    assert realized_gain.holding_period_days == 31
def test_analysis_summarizes_realized_gains() -> None:
    """Analysis should aggregate all realized FIFO matches."""

    transactions = [
        Transaction(
            id=1,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 1, 10),
            transaction_type="BUY",
            units=Decimal("100.000000"),
            nav=Decimal("10.0000"),
            amount=Decimal("1000.00"),
        ),
        Transaction(
            id=2,
            portfolio_id=10,
            fund_id=20,
            transaction_date=date(2026, 2, 10),
            transaction_type="SELL",
            units=Decimal("40.000000"),
            nav=Decimal("15.0000"),
            amount=Decimal("600.00"),
        ),
    ]

    analysis = TaxLotService().analyze(
        transactions=transactions,
    )

    assert analysis.total_sale_proceeds == Decimal("600.00")
    assert analysis.total_realized_cost_basis == Decimal("400.00")
    assert analysis.total_realized_gain == Decimal("200.00")