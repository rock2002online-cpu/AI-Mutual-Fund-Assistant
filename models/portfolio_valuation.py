"""Portfolio valuation domain model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """
    Immutable summary of a portfolio's valuation.

    Produced by ValuationService and consumed by dashboards,
    analytics, reports, and AI services.
    """

    portfolio_id: int

    invested_amount: float
    current_value: float

    unrealized_gain: float
    unrealized_return_pct: float

    number_of_positions: int