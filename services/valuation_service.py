"""Portfolio valuation application service."""

from __future__ import annotations

import pandas as pd

from models.portfolio_valuation import PortfolioValuation
from services.position_service import PositionService


class ValuationService:
    """
    Calculate legacy DataFrame valuations and aggregate portfolio positions.

    PositionService is optional so existing code can continue using
    ValuationService() without constructor arguments.
    """

    def __init__(
        self,
        position_service: PositionService | None = None,
    ) -> None:
        self._position_service = position_service

    def calculate(
        self,
        portfolio_df: pd.DataFrame,
        nav_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calculate portfolio valuation using holdings and latest NAV data.

        This preserves the legacy DataFrame-based valuation API.
        """

        portfolio = portfolio_df.copy()
        nav = nav_df.copy()

        portfolio["Scheme Code"] = (
            portfolio["Scheme Code"].astype(str)
        )

        nav["Scheme Code"] = (
            nav["Scheme Code"].astype(str)
        )

        portfolio = portfolio.merge(
            nav[["Scheme Code", "NAV"]],
            on="Scheme Code",
            how="left",
        )

        portfolio.rename(
            columns={"NAV": "Latest NAV"},
            inplace=True,
        )

        portfolio["Latest NAV"] = pd.to_numeric(
            portfolio["Latest NAV"],
            errors="coerce",
        )

        portfolio["Units"] = pd.to_numeric(
            portfolio["Units"],
            errors="coerce",
        )

        portfolio["Avg NAV"] = pd.to_numeric(
            portfolio["Avg NAV"],
            errors="coerce",
        )

        portfolio["Investment"] = (
            portfolio["Units"]
            * portfolio["Avg NAV"]
        )

        portfolio["Current Value"] = (
            portfolio["Units"]
            * portfolio["Latest NAV"]
        )

        portfolio["Profit/Loss"] = (
            portfolio["Current Value"]
            - portfolio["Investment"]
        )

        portfolio["Return %"] = (
            portfolio["Profit/Loss"]
            / portfolio["Investment"]
        ) * 100

        portfolio["Status"] = portfolio["Return %"].apply(
            lambda value: (
                "OK"
                if value >= 0
                else "Warning"
            )
        )

        return portfolio

    def get_portfolio_valuation(
        self,
        *,
        portfolio_id: int,
    ) -> PortfolioValuation:
        """Return the aggregate valuation for a persisted portfolio."""

        if self._position_service is None:
            raise RuntimeError(
                "position_service is required for "
                "get_portfolio_valuation()."
            )

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

        return PortfolioValuation(
            portfolio_id=portfolio_id,
            invested_amount=invested_amount,
            current_value=current_value,
            unrealized_gain=unrealized_gain,
            unrealized_return_pct=unrealized_return_pct,
            number_of_positions=len(positions),
        )