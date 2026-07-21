"""
Unit tests for the Transaction ORM model.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import inspect

from models.transaction import Transaction


def test_transaction_table_name() -> None:
    assert Transaction.__tablename__ == "transactions"


def test_transaction_columns() -> None:
    mapper = inspect(Transaction)

    column_names = {column.key for column in mapper.columns}

    assert column_names == {
        "id",
        "portfolio_id",
        "fund_id",
        "transaction_date",
        "transaction_type",
        "units",
        "nav",
        "amount",
        "created_at",
        "updated_at",
    }


def test_transaction_primary_key() -> None:
    mapper = inspect(Transaction)

    primary_keys = [column.key for column in mapper.primary_key]

    assert primary_keys == ["id"]


def test_transaction_foreign_keys() -> None:
    mapper = inspect(Transaction)

    portfolio_foreign_keys = mapper.columns["portfolio_id"].foreign_keys
    fund_foreign_keys = mapper.columns["fund_id"].foreign_keys

    assert len(portfolio_foreign_keys) == 1
    assert len(fund_foreign_keys) == 1

    portfolio_target = next(iter(portfolio_foreign_keys)).target_fullname
    fund_target = next(iter(fund_foreign_keys)).target_fullname

    assert portfolio_target == "portfolios.id"
    assert fund_target == "funds.id"


def test_transaction_foreign_keys_are_required() -> None:
    mapper = inspect(Transaction)

    assert mapper.columns["portfolio_id"].nullable is False
    assert mapper.columns["fund_id"].nullable is False


def test_transaction_foreign_keys_are_indexed() -> None:
    mapper = inspect(Transaction)

    assert mapper.columns["portfolio_id"].index is True
    assert mapper.columns["fund_id"].index is True


def test_transaction_required_fields() -> None:
    mapper = inspect(Transaction)

    required_columns = {
        "transaction_date",
        "transaction_type",
        "units",
        "nav",
        "amount",
    }

    for column_name in required_columns:
        assert mapper.columns[column_name].nullable is False


def test_transaction_numeric_precision() -> None:
    mapper = inspect(Transaction)

    units_type = mapper.columns["units"].type
    nav_type = mapper.columns["nav"].type
    amount_type = mapper.columns["amount"].type

    assert units_type.precision == 18
    assert units_type.scale == 6

    assert nav_type.precision == 18
    assert nav_type.scale == 4

    assert amount_type.precision == 18
    assert amount_type.scale == 2


def test_transaction_instance_creation() -> None:
    transaction = Transaction(
        portfolio_id=1,
        fund_id=2,
        transaction_date=date(2026, 7, 17),
        transaction_type="PURCHASE",
        units=Decimal("12.345678"),
        nav=Decimal("123.4567"),
        amount=Decimal("1524.15"),
    )

    assert transaction.portfolio_id == 1
    assert transaction.fund_id == 2
    assert transaction.transaction_date == date(2026, 7, 17)
    assert transaction.transaction_type == "PURCHASE"
    assert transaction.units == Decimal("12.345678")
    assert transaction.nav == Decimal("123.4567")
    assert transaction.amount == Decimal("1524.15")


def test_transaction_repr() -> None:
    transaction = Transaction(
        portfolio_id=1,
        fund_id=2,
        transaction_date=date(2026, 7, 17),
        transaction_type="REDEMPTION",
        units=Decimal("5.000000"),
        nav=Decimal("100.0000"),
        amount=Decimal("500.00"),
    )

    representation = repr(transaction)

    assert "Transaction(" in representation
    assert "REDEMPTION" in representation
    assert "500.00" in representation