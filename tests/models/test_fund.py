"""
Unit tests for the Fund ORM model.
"""

from __future__ import annotations

from sqlalchemy import inspect

from models.fund import Fund


def test_fund_table_name() -> None:
    assert Fund.__tablename__ == "funds"


def test_fund_columns() -> None:
    mapper = inspect(Fund)

    column_names = {column.key for column in mapper.columns}

    assert column_names == {
        "id",
        "scheme_code",
        "name",
        "amc",
        "category",
        "plan",
        "option",
        "created_at",
        "updated_at",
    }


def test_fund_primary_key() -> None:
    mapper = inspect(Fund)

    primary_keys = [column.key for column in mapper.primary_key]

    assert primary_keys == ["id"]


def test_fund_scheme_code_is_unique() -> None:
    mapper = inspect(Fund)
    scheme_code = mapper.columns["scheme_code"]

    assert scheme_code.unique is True
    assert scheme_code.nullable is False


def test_fund_required_fields() -> None:
    mapper = inspect(Fund)

    assert mapper.columns["name"].nullable is False
    assert mapper.columns["scheme_code"].nullable is False


def test_fund_optional_fields() -> None:
    mapper = inspect(Fund)

    assert mapper.columns["amc"].nullable is True
    assert mapper.columns["category"].nullable is True
    assert mapper.columns["plan"].nullable is True
    assert mapper.columns["option"].nullable is True


def test_fund_instance_creation() -> None:
    fund = Fund(
        scheme_code="120503",
        name="Example Mutual Fund",
        amc="Example AMC",
        category="Equity",
        plan="Direct",
        option="Growth",
    )

    assert fund.scheme_code == "120503"
    assert fund.name == "Example Mutual Fund"
    assert fund.amc == "Example AMC"
    assert fund.category == "Equity"
    assert fund.plan == "Direct"
    assert fund.option == "Growth"


def test_fund_repr() -> None:
    fund = Fund(
        scheme_code="120503",
        name="Example Mutual Fund",
    )

    representation = repr(fund)

    assert "Fund(" in representation
    assert "120503" in representation
    assert "Example Mutual Fund" in representation