"""
Fund ORM model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.nav_history import NAVHistory
    from models.transaction import Transaction


class Fund(Base, TimestampMixin):
    """Represents a mutual fund."""

    __tablename__ = "funds"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    scheme_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    amc: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    plan: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    option: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="fund",
        cascade="all, delete-orphan",
    )

    nav_history: Mapped[list["NAVHistory"]] = relationship(
        back_populates="fund",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Fund(id={self.id!r}, "
            f"scheme_code={self.scheme_code!r}, "
            f"name={self.name!r})"
        )