"""
Transaction ORM model.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.fund import Fund
    from models.portfolio import Portfolio


class Transaction(Base, TimestampMixin):
    """Represents a mutual fund purchase or redemption."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"),
        nullable=False,
        index=True,
    )

    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id"),
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    units: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    nav: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    portfolio: Mapped["Portfolio"] = relationship(
        back_populates="transactions",
    )

    fund: Mapped["Fund"] = relationship(
        back_populates="transactions",
    )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, "
            f"type={self.transaction_type!r}, "
            f"amount={self.amount!r})"
        )