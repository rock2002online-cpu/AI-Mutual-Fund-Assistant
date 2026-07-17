"""
Unit tests for shared SQLAlchemy model utilities.
"""

from __future__ import annotations

from datetime import timezone

from sqlalchemy import inspect

from models import Fund, NAVHistory, Portfolio, Transaction
from models.base import Base, TimestampMixin, utc_now


def test_base_uses_sqlalchemy_declarative_mapping() -> None:
    """Base must expose SQLAlchemy metadata and registry objects."""
    assert Base.metadata is not None
    assert Base.registry is not None


def test_expected_tables_are_registered() -> None:
    """Importing the models must register every ORM table."""
    assert set(Base.metadata.tables) == {
        "funds",
        "portfolios",
        "transactions",
        "nav_history",
    }


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    """Timestamp helper must return a timezone-aware UTC value."""
    value = utc_now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timezone.utc.utcoffset(value)


def test_timestamp_mixin_columns_exist_on_models() -> None:
    """Every timestamp-enabled model must contain audit columns."""
    for model in (Fund, Portfolio, Transaction, NAVHistory):
        mapper = inspect(model)

        assert "created_at" in mapper.columns
        assert "updated_at" in mapper.columns


def test_timestamp_columns_are_required_and_have_defaults() -> None:
    """Timestamp columns must be non-nullable and automatically populated."""
    for model in (Fund, Portfolio, Transaction, NAVHistory):
        mapper = inspect(model)

        created_at = mapper.columns["created_at"]
        updated_at = mapper.columns["updated_at"]

        assert created_at.nullable is False
        assert updated_at.nullable is False

        assert created_at.default is not None
        assert updated_at.default is not None
        assert updated_at.onupdate is not None


def test_models_inherit_from_base_and_timestamp_mixin() -> None:
    """All domain models must inherit from the shared model classes."""
    for model in (Fund, Portfolio, Transaction, NAVHistory):
        assert issubclass(model, Base)
        assert issubclass(model, TimestampMixin)