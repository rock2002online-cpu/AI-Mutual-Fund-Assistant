from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """
    Immutable representation of a portfolio position.

    A Position aggregates transactions into a single holding for a
    portfolio/fund combination.
    """

    portfolio_id: int
    fund_id: int
    fund_name: str

    units: float
    average_nav: float
    invested_amount: float

    latest_nav: float
    current_value: float

    unrealized_gain: float
    unrealized_return_pct: float