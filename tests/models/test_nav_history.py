"""
Unit tests for the NAVHistory ORM model.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import inspect

from models.nav_history import NAVHistory


def test_nav_history_table_name() -> None:
    assert NAVHistory.__tablename__ == "nav_history"


def test_nav_history_columns() -> None:
    mapper = inspect(NAVHistory)

    assert {column.key for column in mapper.columns} == {
        "id",
        "fund_id",
        "nav_date",
        "nav",
        "created_at",
        "updated_at",
    }


def test_nav_history_primary_key() -> None:
    mapper = inspect(NAVHistory)

    assert [column.key for column in mapper.primary_key] == ["id"]


def test_nav_history_foreign_key() -> None:
    mapper = inspect(NAVHistory)

    foreign_keys = mapper.columns["fund_id"].foreign_keys

    assert len(foreign_keys) == 1
    assert next(iter(foreign_keys)).target_fullname == "funds.id"


def test_nav_history_required_fields() -> None:
    mapper = inspect(NAVHistory)

    assert mapper.columns["fund_id"].nullable is False
    assert mapper.columns["nav_date"].nullable is False
    assert mapper.columns["nav"].nullable is False


def test_nav_history_indexes() -> None:
    mapper = inspect(NAVHistory)

    assert mapper.columns["fund_id"].index is True
    assert mapper.columns["nav_date"].index is True


def test_nav_precision() -> None:
    mapper = inspect(NAVHistory)

    nav_type = mapper.columns["nav"].type

    assert nav_type.precision == 18
    assert nav_type.scale == 4


def test_nav_history_instance_creation() -> None:
    record = NAVHistory(
        fund_id=1,
        nav_date=date(2026, 7, 17),
        nav=Decimal("123.4567"),
    )

    assert record.fund_id == 1
    assert record.nav_date == date(2026, 7, 17)
    assert record.nav == Decimal("123.4567")


def test_nav_history_repr() -> None:
    record = NAVHistory(
        fund_id=1,
        nav_date=date(2026, 7, 17),
        nav=Decimal("123.4567"),
    )

    representation = repr(record)

    assert "NAVHistory(" in representation
    assert "123.4567" in representation