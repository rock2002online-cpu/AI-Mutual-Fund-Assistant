"""Transaction application service."""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from models.transaction import Transaction
from repositories.unit_of_work import UnitOfWork
from services.holdings_service import HoldingsService


class TransactionService:
    """Coordinate transaction-related business operations."""

    def __init__(
        self,
        unit_of_work_factory: Callable | None = None,
        holdings_service: HoldingsService | None = None,
    ) -> None:
        resolved_unit_of_work_factory = (
            unit_of_work_factory
            if unit_of_work_factory is not None
            else UnitOfWork
        )

        self._unit_of_work_factory = resolved_unit_of_work_factory

        self._holdings_service = (
            holdings_service
            if holdings_service is not None
            else HoldingsService(
                resolved_unit_of_work_factory
            )
        )

    def get_transaction_history(
        self,
        *,
        portfolio_id: int,
    ) -> pd.DataFrame:
        """
        Return an auditable transaction ledger for a portfolio.

        BUY and SELL transactions are marked as XIRR eligible and receive
        signed cash-flow values. OPENING_BALANCE and any other transaction
        types remain visible but are excluded from XIRR.

        Fund relationship data is resolved while the UnitOfWork session is
        open so callers receive display-ready scheme codes and fund names.
        """

        rows: list[dict[str, object]] = []

        with self._unit_of_work_factory() as unit_of_work:
            transactions = (
                unit_of_work.transactions.get_for_portfolio(
                    portfolio_id
                )
            )

            for transaction in transactions:
                transaction_type = str(
                    transaction.transaction_type
                ).strip().upper()

                xirr_eligible = transaction_type in {
                    "BUY",
                    "SELL",
                }

                cash_flow = None

                if transaction_type == "BUY":
                    cash_flow = -float(
                        transaction.amount
                    )
                elif transaction_type == "SELL":
                    cash_flow = float(
                        transaction.amount
                    )

                fund = transaction.fund

                rows.append(
                    {
                        "Transaction ID": transaction.id,
                        "Date": transaction.transaction_date,
                        "Fund ID": transaction.fund_id,
                        "Scheme Code": str(
                            fund.scheme_code
                        ),
                        "Fund": str(
                            fund.name
                        ),
                        "Transaction Type": transaction_type,
                        "Units": float(
                            transaction.units
                        ),
                        "NAV": float(
                            transaction.nav
                        ),
                        "Amount": float(
                            transaction.amount
                        ),
                        "XIRR Eligible": xirr_eligible,
                        "Cash Flow": cash_flow,
                    }
                )

        return pd.DataFrame(
            rows,
            columns=[
                "Transaction ID",
                "Date",
                "Fund ID",
                "Scheme Code",
                "Fund",
                "Transaction Type",
                "Units",
                "NAV",
                "Amount",
                "XIRR Eligible",
                "Cash Flow",
            ],
        ).sort_values(
            [
                "Date",
                "Transaction ID",
            ],
            ignore_index=True,
        )

    def get_cash_flow_history(
        self,
        *,
        portfolio_id: int,
    ) -> pd.DataFrame:
        """Return signed BUY and SELL cash flows for portfolio XIRR."""

        with self._unit_of_work_factory() as unit_of_work:
            transactions = (
                unit_of_work.transactions.get_for_portfolio(
                    portfolio_id
                )
            )

        cash_flows = [
            {
                "Date": transaction.transaction_date,
                "Amount": (
                    -float(transaction.amount)
                    if transaction.transaction_type == "BUY"
                    else float(transaction.amount)
                ),
            }
            for transaction in transactions
            if transaction.transaction_type in {
                "BUY",
                "SELL",
            }
        ]

        return pd.DataFrame(
            cash_flows,
            columns=[
                "Date",
                "Amount",
            ],
        ).sort_values(
            "Date",
            ignore_index=True,
        )

    def buy_units(
        self,
        *,
        portfolio_id: int,
        fund_id: int,
        units: float,
        amount: float,
        transaction_date: Optional[date] = None,
    ) -> Transaction:
        """Create and persist a mutual-fund purchase transaction."""

        if units <= 0:
            raise ValueError(
                "units must be greater than zero"
            )

        if amount <= 0:
            raise ValueError(
                "amount must be greater than zero"
            )

        effective_date = (
            transaction_date
            if transaction_date is not None
            else date.today()
        )

        transaction = Transaction(
            portfolio_id=portfolio_id,
            fund_id=fund_id,
            transaction_type="BUY",
            nav=amount / units,
            units=units,
            amount=amount,
            transaction_date=effective_date,
        )

        with self._unit_of_work_factory() as unit_of_work:
            persisted = (
                unit_of_work.transactions.add(
                    transaction
                )
            )
            unit_of_work.commit()

        return persisted

    def sell_units(
        self,
        *,
        portfolio_id: int,
        fund_id: int,
        units: float,
        amount: float,
        transaction_date: Optional[date] = None,
    ) -> Transaction:
        """
        Create and persist a mutual-fund redemption transaction.

        The redemption is rejected when the requested units exceed the
        current units held for the selected portfolio and fund.
        """

        if units <= 0:
            raise ValueError(
                "units must be greater than zero"
            )

        if amount <= 0:
            raise ValueError(
                "amount must be greater than zero"
            )

        effective_date = (
            transaction_date
            if transaction_date is not None
            else date.today()
        )

        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.portfolios.get_by_id(
                portfolio_id
            )
            unit_of_work.funds.get_by_id(
                fund_id
            )

            current_units = (
                self._holdings_service.get_current_units(
                    portfolio_id=portfolio_id,
                    fund_id=fund_id,
                )
            )

            if units > current_units:
                raise ValueError(
                    "Insufficient units available for redemption"
                )

            transaction = Transaction(
                portfolio_id=portfolio_id,
                fund_id=fund_id,
                transaction_type="SELL",
                nav=amount / units,
                units=units,
                amount=amount,
                transaction_date=effective_date,
            )

            persisted = (
                unit_of_work.transactions.add(
                    transaction
                )
            )
            unit_of_work.commit()

        return persisted


__all__ = ["TransactionService"]