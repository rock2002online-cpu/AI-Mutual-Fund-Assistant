"""Portfolio reconciliation reporting orchestration service."""

from __future__ import annotations

from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
    PortfolioReconciliationService,
)
from services.portfolio_tax_lot_service import (
    PortfolioTaxLotService,
)
from services.position_service import PositionService


class PortfolioReconciliationReportingService:
    """Coordinate portfolio data retrieval and reconciliation."""

    def __init__(
        self,
        *,
        position_service: PositionService,
        portfolio_tax_lot_service: PortfolioTaxLotService,
        reconciliation_service: PortfolioReconciliationService,
    ) -> None:
        self._position_service = position_service
        self._portfolio_tax_lot_service = (
            portfolio_tax_lot_service
        )
        self._reconciliation_service = (
            reconciliation_service
        )

    def reconcile_portfolio(
        self,
        *,
        portfolio_id: int,
    ) -> PortfolioReconciliationResult:
        """Return reconciliation reporting data for a portfolio."""
        if portfolio_id <= 0:
                    raise ValueError(
                        "portfolio_id must be positive"
                    )
        positions = (
            self._position_service.get_positions(
                portfolio_id=portfolio_id,
            )
        )

        tax_lot_analysis = (
            self._portfolio_tax_lot_service
            .analyze_portfolio(
                portfolio_id=portfolio_id,
            )
        )

        return self._reconciliation_service.reconcile(
            positions=positions,
            tax_lot_analysis=tax_lot_analysis,
        )


__all__ = [
    "PortfolioReconciliationReportingService",
]