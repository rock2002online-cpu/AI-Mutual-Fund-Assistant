"""
Unit of Work implementation.

Coordinates SQLAlchemy sessions, repositories, and transaction boundaries.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from config.database import get_database_manager
from repositories.fund_repository import FundRepository
from repositories.portfolio_repository import PortfolioRepository
from repositories.transaction_repository import TransactionRepository
from repositories.nav_history_repository import NAVHistoryRepository


class UnitOfWork:
    """Coordinates repositories within a single transaction."""

    def __init__(self) -> None:
        manager = get_database_manager()
        self._session_factory = manager.session_factory

        self.session: Session | None = None

        self.funds: FundRepository | None = None
        self.portfolios: PortfolioRepository | None = None
        self.transactions: TransactionRepository | None = None
        self.nav_history: NAVHistoryRepository | None = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()

        self.funds = FundRepository(self.session)
        self.portfolios = PortfolioRepository(self.session)
        self.transactions = TransactionRepository(self.session)
        self.nav_history = NAVHistoryRepository(self.session)

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self.session is None:
            return

        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()

    def commit(self) -> None:
        """Commit the active transaction."""

        if self.session is None:
            raise RuntimeError(
                "UnitOfWork has not been entered."
            )

        self.session.commit()

    def rollback(self) -> None:
        """Rollback the active transaction."""

        if self.session is None:
            raise RuntimeError(
                "UnitOfWork has not been entered."
            )

        self.session.rollback()