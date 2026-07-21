"""
Repository for Fund entities.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.fund import Fund
from repositories.base_repository import BaseRepository


class FundRepository(BaseRepository[Fund]):
    """Repository for Fund ORM operations."""

    def __init__(self, session: Session) -> None:
        super().__init__(
            session=session,
            model=Fund,
        )

    def get_by_scheme_code(
        self,
        scheme_code: str,
    ) -> Fund | None:
        """Return a fund by its AMFI scheme code."""

        return (
            self.session.query(Fund)
            .filter(
                Fund.scheme_code == scheme_code
            )
            .one_or_none()
        )

    def search_by_name(
        self,
        text: str,
    ) -> list[Fund]:
        """Search funds by partial name."""

        return (
            self.session.query(Fund)
            .filter(
                Fund.name.ilike(f"%{text}%")
            )
            .order_by(Fund.name)
            .all()
        )

    def get_by_amc(
        self,
        amc: str,
    ) -> list[Fund]:
        """Return all funds belonging to an AMC."""

        return (
            self.session.query(Fund)
            .filter(
                Fund.amc == amc
            )
            .order_by(Fund.name)
            .all()
        )