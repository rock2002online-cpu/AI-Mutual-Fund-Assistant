"""Portfolio tax-lot view orchestration."""

from __future__ import annotations

from dashboard.components.tax_lot_analytics import (
    render_tax_lot_analytics,
)
from repositories.unit_of_work import UnitOfWork
from services.portfolio_tax_lot_service import (
    PortfolioTaxLotService,
)
from services.tax_lot_service import TaxLotService


def render_tax_lot_section(
    *,
    portfolio_id: int,
) -> None:
    """Load and render tax-lot analytics for a portfolio."""

    with UnitOfWork() as unit_of_work:
        service = PortfolioTaxLotService(
            transaction_repository=(
                unit_of_work.transactions
            ),
            tax_lot_service=TaxLotService(),
        )

        analysis = service.analyze_portfolio(
            portfolio_id=portfolio_id,
        )

    render_tax_lot_analytics(
        analysis
    )