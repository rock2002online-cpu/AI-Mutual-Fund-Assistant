"""Portfolio position calculation service."""

from __future__ import annotations

from typing import Callable

from models.position import Position
from models.transaction import Transaction


class PositionService:
    """Build portfolio positions from transaction history and fund data."""

    def __init__(
        self,
        unit_of_work_factory: Callable,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def get_position(
        self,
        *,
        portfolio_id: int,
        fund_id: int,
    ) -> Position:
        """Return the current position for one portfolio and fund."""

        with self._unit_of_work_factory() as unit_of_work:
            fund = unit_of_work.funds.get_by_id(
                fund_id
            )

            portfolio_transactions = (
                unit_of_work.transactions.get_for_portfolio(
                    portfolio_id
                )
            )

        matching_transactions = [
            transaction
            for transaction in portfolio_transactions
            if transaction.fund_id == fund_id
        ]

        units, invested_amount = self._calculate_cost_basis(
            matching_transactions
        )

        average_nav = (
            invested_amount / units
            if units > 0
            else 0.0
        )

        latest_nav = float(fund.latest_nav)
        current_value = units * latest_nav
        unrealized_gain = current_value - invested_amount

        unrealized_return_pct = (
            unrealized_gain / invested_amount * 100.0
            if invested_amount > 0
            else 0.0
        )

        return Position(
            portfolio_id=portfolio_id,
            fund_id=fund_id,
            fund_name=str(fund.name),
            units=units,
            average_nav=average_nav,
            invested_amount=invested_amount,
            latest_nav=latest_nav,
            current_value=current_value,
            unrealized_gain=unrealized_gain,
            unrealized_return_pct=unrealized_return_pct,
        )

    def get_positions(
        self,
        *,
        portfolio_id: int,
    ) -> list[Position]:
        """
        Return all current fund positions for a portfolio.

        One aggregated Position is returned for each distinct fund found
        in the portfolio transaction history. Results are sorted by fund
        name.
        """

        with self._unit_of_work_factory() as unit_of_work:
            portfolio_transactions = (
                unit_of_work.transactions.get_for_portfolio(
                    portfolio_id
                )
            )

        fund_ids = {
            transaction.fund_id
            for transaction in portfolio_transactions
        }

        positions = [
            self.get_position(
                portfolio_id=portfolio_id,
                fund_id=fund_id,
            )
            for fund_id in fund_ids
        ]

        return sorted(
            positions,
            key=lambda position: position.fund_name.casefold(),
        )

    @staticmethod
    def _calculate_cost_basis(
        transactions: list[Transaction],
    ) -> tuple[float, float]:
        """
        Calculate current units and remaining invested cost.

        BUY transactions add units and acquisition cost.

        SELL transactions reduce units and remove their proportional
        moving-average cost basis. Redemption proceeds are not deducted
        from invested cost because sale amount represents proceeds, not
        the historical acquisition cost of the redeemed units.
        """

        current_units = 0.0
        invested_amount = 0.0

        for transaction in transactions:
            transaction_type = str(
                transaction.transaction_type
            ).strip().upper()

            transaction_units = float(
                transaction.units
            )
            transaction_amount = float(
                transaction.amount
            )

            if transaction_type == "BUY":
                current_units += transaction_units
                invested_amount += transaction_amount

            elif transaction_type == "SELL":
                if current_units <= 0:
                    continue

                units_to_remove = min(
                    transaction_units,
                    current_units,
                )

                average_cost = (
                    invested_amount / current_units
                    if current_units > 0
                    else 0.0
                )

                invested_amount -= (
                    average_cost * units_to_remove
                )
                current_units -= units_to_remove

        if abs(current_units) < 1e-12:
            current_units = 0.0

        if abs(invested_amount) < 1e-12:
            invested_amount = 0.0

        return current_units, invested_amount