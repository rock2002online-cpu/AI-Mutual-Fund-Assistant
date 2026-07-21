"""Portfolio analytics domain model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioAnalytics:
    """Immutable portfolio analytics summary."""

    portfolio_id: int
    invested_amount: float
    current_value: float
    unrealized_gain: float
    unrealized_return_pct: float
    number_of_positions: int
    diversification_score: float
    concentration_score: float