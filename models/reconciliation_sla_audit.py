"""Persistent audit record for reconciliation SLA monitoring."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from models.base import (
    Base,
    TimestampMixin,
    utc_now,
)


class ReconciliationSLAAudit(
    Base,
    TimestampMixin,
):
    """Immutable summary of a reconciliation SLA monitoring run."""

    __tablename__ = (
        "reconciliation_sla_audits"
    )

    __table_args__ = (
        CheckConstraint(
            "assignment_breach_count >= 0",
            name=(
                "ck_reconciliation_sla_audits_"
                "assignment_count"
            ),
        ),
        CheckConstraint(
            "investigation_breach_count >= 0",
            name=(
                "ck_reconciliation_sla_audits_"
                "investigation_count"
            ),
        ),
        CheckConstraint(
            "resolution_breach_count >= 0",
            name=(
                "ck_reconciliation_sla_audits_"
                "resolution_count"
            ),
        ),
        CheckConstraint(
            "escalated_count >= 0",
            name=(
                "ck_reconciliation_sla_audits_"
                "escalated_count"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id"),
        nullable=False,
        index=True,
    )

    monitored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    assignment_breach_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
            server_default="0",
        )
    )

    investigation_breach_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
            server_default="0",
        )
    )

    resolution_breach_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
            server_default="0",
        )
    )

    escalated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )


__all__ = [
    "ReconciliationSLAAudit",
]