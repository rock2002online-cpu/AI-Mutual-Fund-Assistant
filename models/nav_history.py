"""
NAV History ORM model.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.fund import Fund


class NAVHistory(Base, TimestampMixin):
    """Represents historical NAV values for a mutual fund."""

    __tablename__ = "nav_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id"),
        nullable=False,
        index=True,
    )

    nav_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    nav: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    fund: Mapped["Fund"] = relationship(
        back_populates="nav_history",
    )

    def __repr__(self) -> str:
        return (
            f"NAVHistory(id={self.id!r}, "
            f"fund_id={self.fund_id!r}, "
            f"nav_date={self.nav_date!r}, "
            f"nav={self.nav!r})"
        )