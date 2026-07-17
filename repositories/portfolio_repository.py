"""
Repository for Portfolio entities.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.portfolio import Portfolio
from repositories.base_repository import BaseRepository


class PortfolioRepository(BaseRepository[Portfolio]):
    """Repository for Portfolio ORM operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(
            session=session,
            model=Portfolio,
        )

    def get_active(self) -> list[Portfolio]:
        """Return all active portfolios."""

        return (
            self.session.query(Portfolio)
            .filter(Portfolio.is_active.is_(True))
            .order_by(Portfolio.name)
            .all()
        )

    def get_by_owner(
        self,
        owner_reference: str,
    ) -> list[Portfolio]:
        """Return portfolios belonging to an owner."""

        return (
            self.session.query(Portfolio)
            .filter(
                Portfolio.owner_reference == owner_reference
            )
            .order_by(Portfolio.name)
            .all()
        )

    def get_by_name(
        self,
        name: str,
    ) -> Portfolio | None:
        """Return a portfolio by its name."""

        return (
            self.session.query(Portfolio)
            .filter(
                Portfolio.name == name
            )
            .one_or_none()
        )