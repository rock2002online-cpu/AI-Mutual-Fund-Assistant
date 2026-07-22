"""Portfolio tax-lot application service."""

from __future__ import annotations

from datetime import date

from repositories.transaction_repository import (
    TransactionRepository,
)
from services.tax_lot_service import (
    TaxLotAnalysis,
    TaxLotService,
)


class PortfolioTaxLotService:
    """Coordinate transaction retrieval and tax-lot analysis."""

    def __init__(
        self,
        *,
        transaction_repository: TransactionRepository,
        tax_lot_service: TaxLotService,
    ) -> None:
        self._transaction_repository = (
            transaction_repository
        )
        self._tax_lot_service = tax_lot_service

    def analyze_portfolio(
        self,
        *,
        portfolio_id: int,
        as_of_date: date | None = None,
    ) -> TaxLotAnalysis:
        """Return FIFO tax-lot analytics for a portfolio."""

        if portfolio_id <= 0:
            raise ValueError(
                "portfolio_id must be positive"
            )

        if as_of_date is None:
            transactions = (
                self._transaction_repository
                .get_for_portfolio(
                    portfolio_id
                )
            )
        else:
            transactions = (
                self._transaction_repository
                .get_for_portfolio_through_date(
                    portfolio_id=portfolio_id,
                    end_date=as_of_date,
                )
            )

        return self._tax_lot_service.analyze(
            transactions=transactions,
        )