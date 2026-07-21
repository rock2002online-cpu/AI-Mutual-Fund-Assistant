"""Portfolio analytics application service."""

from __future__ import annotations

from models.portfolio_analytics import PortfolioAnalytics
from services.position_service import PositionService


class PortfolioAnalyticsService:
    """Calculate aggregate analytics for a portfolio."""

    def __init__(
        self,
        position_service: PositionService,
    ) -> None:
        """Initialize the portfolio analytics service."""

        self._position_service = position_service

    def calculate(
        self,
        *,
        portfolio_id: int,
    ) -> PortfolioAnalytics:
        """Calculate aggregate analytics for a portfolio."""

        positions = self._position_service.get_positions(
            portfolio_id=portfolio_id,
        )

        invested_amount = sum(
            float(position.invested_amount)
            for position in positions
        )

        current_value = sum(
            float(position.current_value)
            for position in positions
        )

        unrealized_gain = (
            current_value
            - invested_amount
        )

        unrealized_return_pct = (
            unrealized_gain
            / invested_amount
            * 100.0
            if invested_amount > 0
            else 0.0
        )

        number_of_positions = len(positions)

        concentration_score = 0.0
        diversification_score = 0.0

        if current_value > 0:
            position_weights = [
                float(position.current_value)
                / current_value
                for position in positions
            ]

            hhi = sum(
                weight**2
                for weight in position_weights
            )

            concentration_score = (
                hhi
                * 100.0
            )

            diversification_score = (
                1.0
                - hhi
            ) * 100.0

        return PortfolioAnalytics(
            portfolio_id=portfolio_id,
            invested_amount=invested_amount,
            current_value=current_value,
            unrealized_gain=unrealized_gain,
            unrealized_return_pct=unrealized_return_pct,
            number_of_positions=number_of_positions,
            diversification_score=diversification_score,
            concentration_score=concentration_score,
        )