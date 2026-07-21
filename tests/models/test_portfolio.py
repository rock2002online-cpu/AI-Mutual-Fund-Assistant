"""
Unit tests for the Portfolio ORM model.
"""

from __future__ import annotations

from sqlalchemy import inspect

from models.portfolio import Portfolio


def test_portfolio_table_name() -> None:
    assert Portfolio.__tablename__ == "portfolios"


def test_portfolio_columns() -> None:
    mapper = inspect(Portfolio)

    column_names = {column.key for column in mapper.columns}

    assert column_names == {
        "id",
        "name",
        "description",
        "owner_reference",
        "base_currency",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_portfolio_primary_key() -> None:
    mapper = inspect(Portfolio)

    primary_keys = [column.key for column in mapper.primary_key]

    assert primary_keys == ["id"]


def test_portfolio_required_fields() -> None:
    mapper = inspect(Portfolio)

    assert mapper.columns["name"].nullable is False
    assert mapper.columns["base_currency"].nullable is False
    assert mapper.columns["is_active"].nullable is False


def test_portfolio_optional_fields() -> None:
    mapper = inspect(Portfolio)

    assert mapper.columns["description"].nullable is True
    assert mapper.columns["owner_reference"].nullable is True


def test_portfolio_owner_reference_is_indexed() -> None:
    mapper = inspect(Portfolio)

    assert mapper.columns["owner_reference"].index is True


def test_portfolio_defaults() -> None:
    mapper = inspect(Portfolio)

    currency_default = mapper.columns["base_currency"].default
    active_default = mapper.columns["is_active"].default

    assert currency_default is not None
    assert currency_default.arg == "INR"

    assert active_default is not None
    assert active_default.arg is True


def test_portfolio_instance_creation() -> None:
    portfolio = Portfolio(
        name="Primary Portfolio",
        description="Long-term mutual fund holdings",
        owner_reference="user-001",
        base_currency="INR",
        is_active=True,
    )

    assert portfolio.name == "Primary Portfolio"
    assert portfolio.description == "Long-term mutual fund holdings"
    assert portfolio.owner_reference == "user-001"
    assert portfolio.base_currency == "INR"
    assert portfolio.is_active is True


def test_portfolio_repr() -> None:
    portfolio = Portfolio(
        name="Primary Portfolio",
        base_currency="INR",
    )

    representation = repr(portfolio)

    assert "Portfolio(" in representation
    assert "Primary Portfolio" in representation
    assert "INR" in representation