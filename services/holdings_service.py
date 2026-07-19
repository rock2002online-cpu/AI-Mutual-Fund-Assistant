"""Portfolio holdings calculation service."""

from __future__ import annotations

from typing import Callable

from models.transaction import Transaction


class HoldingsService:
    """Calculate current holdings from repository transactions."""

    def __init__(
        self,
        unit_of_work_factory: Callable,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def get_current_units(
        self,
        *,
        portfolio_id: int,
        fund_id: int,
    ) -> float:
        """
        Return net units held for a portfolio and fund.

        BUY transactions increase holdings.
        SELL transactions decrease holdings.
        """

        with self._unit_of_work_factory() as unit_of_work:
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

        return self._calculate_current_units(
            matching_transactions
        )

    @staticmethod
    def _calculate_current_units(
        transactions: list[Transaction],
    ) -> float:
        """Calculate net units from BUY and SELL transactions."""

        current_units = 0.0

        for transaction in transactions:
            transaction_type = str(
                transaction.transaction_type
            ).strip().upper()

            transaction_units = float(
                transaction.units
            )

            if transaction_type == "BUY":
                current_units += transaction_units
            elif transaction_type == "SELL":
                current_units -= transaction_units

        return current_units