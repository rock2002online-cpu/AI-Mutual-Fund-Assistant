"""Portfolio position and transaction reconciliation service."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from models.position import Position
from services.tax_lot_service import TaxLotAnalysis


UNIT_PRECISION = Decimal("0.000001")
MONEY_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class PortfolioReconciliationItem:
    """Reconciliation result for one portfolio fund."""

    portfolio_id: int
    fund_id: int
    fund_name: str | None
    position_units: Decimal
    transaction_units: Decimal
    unit_variance: Decimal
    position_cost_basis: Decimal
    transaction_cost_basis: Decimal
    cost_basis_variance: Decimal
    status: str


@dataclass(frozen=True)
class PortfolioReconciliationResult:
    """Aggregate portfolio reconciliation result."""

    items: list[PortfolioReconciliationItem]
    is_reconciled: bool

    @property
    def matched_count(self) -> int:
        """Return the number of reconciled fund items."""

        return sum(
            item.status == "matched"
            for item in self.items
        )

    @property
    def unreconciled_count(self) -> int:
        """Return the number of unreconciled fund items."""

        return sum(
            item.status != "matched"
            for item in self.items
        )

    @property
    def unit_mismatch_count(self) -> int:
        """Return the number of items with unequal unit balances."""

        return sum(
            item.status == "unit_mismatch"
            for item in self.items
        )

    @property
    def missing_position_count(self) -> int:
        """Return the number of tax-lot balances without positions."""

        return sum(
            item.status == "missing_position"
            for item in self.items
        )

    @property
    def missing_tax_lot_count(self) -> int:
        """Return the number of positions without open tax lots."""

        return sum(
            item.status == "missing_tax_lots"
            for item in self.items
        )

    @property
    def total_count(self) -> int:
        """Return the total number of reconciliation items."""

        return len(self.items)

    @property
    def cost_basis_variance_count(self) -> int:
        """Count informational variances for unit-matched items."""

        return sum(
            item.status == "matched"
            and item.cost_basis_variance != Decimal("0.00")
            for item in self.items
        )

class PortfolioReconciliationService:
    """Reconcile portfolio positions against open transaction tax lots."""

    def reconcile(
        self,
        *,
        positions: list[Position],
        tax_lot_analysis: TaxLotAnalysis,
    ) -> PortfolioReconciliationResult:
        """Return reconciliation results for the supplied portfolio data."""

        items: list[PortfolioReconciliationItem] = []

        position_keys = {
            (position.portfolio_id, position.fund_id)
            for position in positions
        }

        for position in positions:
            matching_lots = [
                lot
                for lot in tax_lot_analysis.open_lots
                if lot.portfolio_id == position.portfolio_id
                and lot.fund_id == position.fund_id
            ]

            items.append(
                self._build_position_item(
                    position=position,
                    matching_lots=matching_lots,
                )
            )

        transaction_only_keys = {
            (lot.portfolio_id, lot.fund_id)
            for lot in tax_lot_analysis.open_lots
        } - position_keys

        for portfolio_id, fund_id in sorted(transaction_only_keys):
            matching_lots = [
                lot
                for lot in tax_lot_analysis.open_lots
                if lot.portfolio_id == portfolio_id
                and lot.fund_id == fund_id
            ]

            transaction_units = sum(
                (
                    lot.remaining_units
                    for lot in matching_lots
                ),
                Decimal("0"),
            ).quantize(UNIT_PRECISION)

            transaction_cost_basis = sum(
                (
                    lot.remaining_cost_basis
                    for lot in matching_lots
                ),
                Decimal("0"),
            ).quantize(MONEY_PRECISION)

            items.append(
                PortfolioReconciliationItem(
                    portfolio_id=portfolio_id,
                    fund_id=fund_id,
                    fund_name=None,
                    position_units=Decimal("0.000000"),
                    transaction_units=transaction_units,
                    unit_variance=(
                        -transaction_units
                    ).quantize(UNIT_PRECISION),
                    position_cost_basis=Decimal("0.00"),
                    transaction_cost_basis=transaction_cost_basis,
                    cost_basis_variance=(
                        -transaction_cost_basis
                    ).quantize(MONEY_PRECISION),
                    status="missing_position",
                )
            )

        return PortfolioReconciliationResult(
            items=items,
            is_reconciled=all(
                item.status == "matched"
                for item in items
            ),
        )

    def _build_position_item(
        self,
        *,
        position: Position,
        matching_lots: list,
    ) -> PortfolioReconciliationItem:
        """Build reconciliation details for one position."""

        position_units = Decimal(
            str(position.units)
        ).quantize(UNIT_PRECISION)

        transaction_units = sum(
            (
                lot.remaining_units
                for lot in matching_lots
            ),
            Decimal("0"),
        ).quantize(UNIT_PRECISION)

        unit_variance = (
            position_units - transaction_units
        ).quantize(UNIT_PRECISION)

        position_cost_basis = Decimal(
            str(position.invested_amount)
        ).quantize(MONEY_PRECISION)

        transaction_cost_basis = sum(
            (
                lot.remaining_cost_basis
                for lot in matching_lots
            ),
            Decimal("0"),
        ).quantize(MONEY_PRECISION)

        cost_basis_variance = (
            position_cost_basis
            - transaction_cost_basis
        ).quantize(MONEY_PRECISION)

        if not matching_lots:
            status = "missing_tax_lots"
        elif unit_variance == Decimal("0.000000"):
            status = "matched"
        else:
            status = "unit_mismatch"

        return PortfolioReconciliationItem(
            portfolio_id=position.portfolio_id,
            fund_id=position.fund_id,
            fund_name=position.fund_name,
            position_units=position_units,
            transaction_units=transaction_units,
            unit_variance=unit_variance,
            position_cost_basis=position_cost_basis,
            transaction_cost_basis=transaction_cost_basis,
            cost_basis_variance=cost_basis_variance,
            status=status,
        )