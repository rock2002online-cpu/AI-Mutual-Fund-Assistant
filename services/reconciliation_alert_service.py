"""Operational alerts derived from portfolio reconciliation results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)


@dataclass(frozen=True, slots=True)
class ReconciliationAlert:
    """Actionable or informational reconciliation alert."""

    portfolio_id: int
    fund_id: int
    fund_name: str | None
    code: str
    severity: str
    message: str


class ReconciliationAlertService:
    """Convert reconciliation results into operational alerts."""

    def build_alerts(
        self,
        result: PortfolioReconciliationResult,
    ) -> list[ReconciliationAlert]:
        """Return alerts for reconciliation exceptions."""
        if not isinstance(
            result,
            PortfolioReconciliationResult,
        ):
            raise TypeError(
                "result must be a "
                "PortfolioReconciliationResult"
            )

        alerts: list[ReconciliationAlert] = []

        for item in result.items:
            if item.status == "unit_mismatch":
                alerts.append(
                    ReconciliationAlert(
                        portfolio_id=item.portfolio_id,
                        fund_id=item.fund_id,
                        fund_name=item.fund_name,
                        code="unit_mismatch",
                        severity="critical",
                        message=(
                            "Position units differ from "
                            "transaction units by "
                            f"{abs(item.unit_variance):.6f}."
                        ),
                    )
                )
            elif item.status == "missing_position":
                alerts.append(
                    ReconciliationAlert(
                        portfolio_id=item.portfolio_id,
                        fund_id=item.fund_id,
                        fund_name=item.fund_name,
                        code="missing_position",
                        severity="critical",
                        message=(
                            "Transaction tax lots contain "
                            f"{item.transaction_units:.6f} units "
                            "without a portfolio position."
                        ),
                    )
                )
            elif item.status == "missing_tax_lots":
                alerts.append(
                    ReconciliationAlert(
                        portfolio_id=item.portfolio_id,
                        fund_id=item.fund_id,
                        fund_name=item.fund_name,
                        code="missing_tax_lots",
                        severity="critical",
                        message=(
                            "Portfolio position contains "
                            f"{item.position_units:.6f} units "
                            "without transaction tax lots."
                        ),
                    )
                )
            elif (
                item.status == "matched"
                and item.cost_basis_variance
                != Decimal("0.00")
            ):
                alerts.append(
                    ReconciliationAlert(
                        portfolio_id=item.portfolio_id,
                        fund_id=item.fund_id,
                        fund_name=item.fund_name,
                        code="cost_basis_variance",
                        severity="info",
                        message=(
                            "Moving-average and FIFO cost bases "
                            "differ by "
                            f"₹{abs(item.cost_basis_variance):,.2f}; "
                            "units remain reconciled."
                        ),
                    )
                )
        return alerts


__all__ = [
    "ReconciliationAlert",
    "ReconciliationAlertService",
]