"""Reconciliation exception ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from models.base import (
    Base,
    TimestampMixin,
    utc_now,
)

if TYPE_CHECKING:
    from models.reconciliation_audit import (
        ReconciliationAuditItem,
    )


class ReconciliationException(
    Base,
    TimestampMixin,
):
    """Actionable exception raised from reconciliation evidence."""

    __tablename__ = "reconciliation_exceptions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    audit_item_id: Mapped[int] = mapped_column(
        ForeignKey(
            "reconciliation_audit_items.id"
        ),
        nullable=False,
        unique=True,
        index=True,
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

    exception_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="normal",
        server_default="normal",
        index=True,
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    assigned_to: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    assigned_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    escalation_reason: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    investigation_started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolved_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolution_notes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    audit_item: Mapped[
        "ReconciliationAuditItem"
    ] = relationship(
        "ReconciliationAuditItem",
    )


__all__ = [
    "ReconciliationException",
]