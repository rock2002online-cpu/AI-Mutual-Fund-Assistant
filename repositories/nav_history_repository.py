"""
Repository for NAVHistory entities.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.nav_history import NAVHistory
from repositories.base_repository import BaseRepository


class NAVHistoryRepository(BaseRepository[NAVHistory]):
    """Repository for NAV history."""

    def __init__(self, session: Session) -> None:
        super().__init__(
            session=session,
            model=NAVHistory,
        )

    def get_latest(
        self,
        fund_id: int,
    ) -> NAVHistory | None:
        """Return the most recent NAV."""

        statement = (
            select(NAVHistory)
            .where(
                NAVHistory.fund_id == fund_id
            )
            .order_by(
                NAVHistory.nav_date.desc()
            )
        )

        return self.session.scalars(statement).first()

    def get_between_dates(
        self,
        fund_id: int,
        start_date: date,
        end_date: date,
    ) -> list[NAVHistory]:
        """Return NAV history within a date range."""

        statement = (
            select(NAVHistory)
            .where(
                NAVHistory.fund_id == fund_id,
                NAVHistory.nav_date >= start_date,
                NAVHistory.nav_date <= end_date,
            )
            .order_by(NAVHistory.nav_date)
        )

        return list(
            self.session.scalars(statement)
        )

    def get_history(
        self,
        fund_id: int,
    ) -> list[NAVHistory]:
        """Return the complete NAV history."""

        statement = (
            select(NAVHistory)
            .where(
                NAVHistory.fund_id == fund_id
            )
            .order_by(
                NAVHistory.nav_date
            )
        )

        return list(
            self.session.scalars(statement)
        )