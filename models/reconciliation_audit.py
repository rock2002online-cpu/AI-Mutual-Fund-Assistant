"""Reconciliation audit-trail ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from models.base import Base, TimestampMixin


class ReconciliationAuditSnapshot(
    Base,
    TimestampMixin,
):
    """Immutable summary of one portfolio reconciliation run."""

    __tablename__ = (
        "reconciliation_audit_snapshots"
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

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    is_reconciled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    matched_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_mismatch_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    missing_position_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    missing_tax_lot_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cost_basis_variance_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    items: Mapped[
        list["ReconciliationAuditItem"]
    ] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
class ReconciliationAuditItem(
    Base,
    TimestampMixin,
):
    """Immutable fund-level evidence for an audit snapshot."""

    __tablename__ = (
        "reconciliation_audit_items"
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "reconciliation_audit_snapshots.id"
        ),
        nullable=False,
        index=True,
    )

    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id"),
        nullable=False,
        index=True,
    )

    fund_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    position_units: Mapped[object] = mapped_column(
        Numeric(24, 6),
        nullable=False,
    )

    transaction_units: Mapped[object] = mapped_column(
        Numeric(24, 6),
        nullable=False,
    )

    unit_variance: Mapped[object] = mapped_column(
        Numeric(24, 6),
        nullable=False,
    )

    position_cost_basis: Mapped[object] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    transaction_cost_basis: Mapped[object] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    cost_basis_variance: Mapped[object] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    snapshot: Mapped[
        ReconciliationAuditSnapshot
    ] = relationship(
        back_populates="items",
    )


__all__ = [
    "ReconciliationAuditItem",
    "ReconciliationAuditSnapshot",
]