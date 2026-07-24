"""Build immutable portfolio reconciliation audit snapshots."""

from __future__ import annotations

from datetime import datetime

from models.reconciliation_audit import (
    ReconciliationAuditItem,
    ReconciliationAuditSnapshot,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)


class ReconciliationAuditService:
    """Convert reconciliation results into audit aggregates."""

    def build_snapshot(
        self,
        *,
        portfolio_id: int,
        result: PortfolioReconciliationResult,
        recorded_at: datetime,

    ) -> ReconciliationAuditSnapshot:
        """Return an unsaved reconciliation audit snapshot."""
        if portfolio_id <= 0:
            raise ValueError(
                "portfolio_id must be positive"
            )
        if (
            recorded_at.tzinfo is None
            or recorded_at.utcoffset() is None
        ):
            raise ValueError(
                "recorded_at must be timezone-aware"
            )
        if any(
            item.portfolio_id != portfolio_id
            for item in result.items
        ):
            raise ValueError(
                "all reconciliation items must match "
                "portfolio_id"
            )

        audit_items = [
            ReconciliationAuditItem(
                fund_id=item.fund_id,
                fund_name=item.fund_name,
                position_units=item.position_units,
                transaction_units=item.transaction_units,
                unit_variance=item.unit_variance,
                position_cost_basis=(
                    item.position_cost_basis
                ),
                transaction_cost_basis=(
                    item.transaction_cost_basis
                ),
                cost_basis_variance=(
                    item.cost_basis_variance
                ),
                status=item.status,
            )
            for item in result.items
        ]

        return ReconciliationAuditSnapshot(
            portfolio_id=portfolio_id,
            recorded_at=recorded_at,
            is_reconciled=result.is_reconciled,
            total_count=result.total_count,
            matched_count=result.matched_count,
            unit_mismatch_count=(
                result.unit_mismatch_count
            ),
            missing_position_count=(
                result.missing_position_count
            ),
            missing_tax_lot_count=(
                result.missing_tax_lot_count
            ),
            cost_basis_variance_count=(
                result.cost_basis_variance_count
            ),
            items=audit_items,
        )


__all__ = [
    "ReconciliationAuditService",
]