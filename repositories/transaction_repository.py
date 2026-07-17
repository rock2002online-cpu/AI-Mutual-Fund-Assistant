"""
Repository for Transaction entities.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.transaction import Transaction
from repositories.base_repository import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for Transaction ORM operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(
            session=session,
            model=Transaction,
        )

    def get_for_portfolio(
        self,
        portfolio_id: int,
    ) -> list[Transaction]:
        """Return transactions for a portfolio."""

        statement = (
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio_id
            )
            .order_by(Transaction.transaction_date)
        )

        return list(
            self.session.scalars(statement)
        )

    def get_for_fund(
        self,
        fund_id: int,
    ) -> list[Transaction]:
        """Return transactions for a fund."""

        statement = (
            select(Transaction)
            .where(
                Transaction.fund_id == fund_id
            )
            .order_by(Transaction.transaction_date)
        )

        return list(
            self.session.scalars(statement)
        )

    def get_between_dates(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Transaction]:
        """Return transactions within a date range."""

        statement = (
            select(Transaction)
            .where(
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .order_by(Transaction.transaction_date)
        )

        return list(
            self.session.scalars(statement)
        )