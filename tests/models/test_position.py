"""Tests for the portfolio Position model."""

from dataclasses import FrozenInstanceError

import pytest

from models.position import Position


def make_position() -> Position:
    """Create a valid Position instance for testing."""

    return Position(
        portfolio_id=1,
        fund_id=25,
        fund_name="UTI Nifty 50 Index Fund",
        units=42.387,
        average_nav=143.26,
        invested_amount=6073.41,
        latest_nav=189.81,
        current_value=8045.62,
        unrealized_gain=1972.21,
        unrealized_return_pct=32.47,
    )


def test_position_stores_all_fields() -> None:
    """Position should preserve all supplied values."""

    position = make_position()

    assert position.portfolio_id == 1
    assert position.fund_id == 25
    assert position.fund_name == "UTI Nifty 50 Index Fund"

    assert position.units == pytest.approx(42.387)
    assert position.average_nav == pytest.approx(143.26)
    assert position.invested_amount == pytest.approx(6073.41)

    assert position.latest_nav == pytest.approx(189.81)
    assert position.current_value == pytest.approx(8045.62)

    assert position.unrealized_gain == pytest.approx(1972.21)
    assert position.unrealized_return_pct == pytest.approx(32.47)


def test_position_is_immutable() -> None:
    """Position should not allow field mutation."""

    position = make_position()

    with pytest.raises(FrozenInstanceError):
        position.units = 50.0  # type: ignore[misc]


def test_equal_positions_compare_equal() -> None:
    """Positions containing the same values should compare equal."""

    first = make_position()
    second = make_position()

    assert first == second


def test_position_supports_hashing() -> None:
    """Immutable positions should be usable in sets and dictionaries."""

    position = make_position()

    positions = {position}

    assert position in positions


def test_position_uses_slots() -> None:
    """Position should not expose a mutable instance dictionary."""

    position = make_position()

    assert not hasattr(position, "__dict__")