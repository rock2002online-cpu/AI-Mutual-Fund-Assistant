"""
Portfolio ORM model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.transaction import Transaction


class Portfolio(Base, TimestampMixin):
    """Represents an investment portfolio."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owner_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    base_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Portfolio(id={self.id!r}, "
            f"name={self.name!r}, "
            f"base_currency={self.base_currency!r})"
        )