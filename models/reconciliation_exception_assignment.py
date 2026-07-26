"""Reconciliation exception assignment-history ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from models.base import (
    Base,
    TimestampMixin,
)


class ReconciliationExceptionAssignment(
    Base,
    TimestampMixin,
):
    """Immutable record of an exception ownership change."""

    __tablename__ = (
        "reconciliation_exception_assignments"
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    exception_id: Mapped[int] = mapped_column(
        ForeignKey(
            "reconciliation_exceptions.id"
        ),
        nullable=False,
        index=True,
    )

    previous_assigned_to: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    assigned_to: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    reason: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )


__all__ = [
    "ReconciliationExceptionAssignment",
]