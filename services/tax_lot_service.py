"""FIFO tax-lot analytics service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from models.transaction import Transaction

_MONEY_QUANTUM = Decimal("0.01")
_ZERO_UNITS = Decimal("0.000000")
_ZERO_MONEY = Decimal("0.00")
_ACQUISITION_TYPES = frozenset(
    {
        "BUY",
        "OPENING_BALANCE",
    }
)
_SUPPORTED_TRANSACTION_TYPES = (
    _ACQUISITION_TYPES
    | {"SELL"}
)


def _money(value: Decimal) -> Decimal:
    """Round a monetary value to two decimal places."""

    return value.quantize(
        _MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


@dataclass(frozen=True)
class TaxLot:
    """Represents units acquired by one purchase transaction."""

    portfolio_id: int
    fund_id: int
    source_transaction_id: int
    acquisition_date: date
    original_units: Decimal
    remaining_units: Decimal
    cost_per_unit: Decimal
    remaining_cost_basis: Decimal


@dataclass(frozen=True)
class RealizedGain:
    """Represents a FIFO match between a SELL and an acquisition."""

    portfolio_id: int
    fund_id: int
    sell_transaction_id: int
    source_buy_transaction_id: int
    acquisition_date: date
    disposal_date: date
    holding_period_days: int
    units_sold: Decimal
    sale_proceeds: Decimal
    cost_basis: Decimal
    realized_gain: Decimal


@dataclass(frozen=True)
class TaxLotAnalysis:
    """Result of FIFO tax-lot analysis."""

    open_lots: list[TaxLot]
    realized_gains: list[RealizedGain]

    @property
    def total_sale_proceeds(self) -> Decimal:
        """Return total proceeds allocated across realized matches."""

        return _money(
            sum(
                (
                    match.sale_proceeds
                    for match in self.realized_gains
                ),
                start=_ZERO_MONEY,
            )
        )

    @property
    def total_realized_cost_basis(self) -> Decimal:
        """Return total cost basis consumed by SELL transactions."""

        return _money(
            sum(
                (
                    match.cost_basis
                    for match in self.realized_gains
                ),
                start=_ZERO_MONEY,
            )
        )

    @property
    def total_realized_gain(self) -> Decimal:
        """Return total realized gain or loss."""

        return _money(
            sum(
                (
                    match.realized_gain
                    for match in self.realized_gains
                ),
                start=_ZERO_MONEY,
            )
        )


@dataclass
class _WorkingTaxLot:
    """Mutable tax lot used while processing transactions."""

    portfolio_id: int
    fund_id: int
    source_transaction_id: int
    acquisition_date: date
    original_units: Decimal
    remaining_units: Decimal
    cost_per_unit: Decimal
    remaining_cost_basis: Decimal


class TaxLotService:
    """Calculate open lots and realized gains using FIFO matching."""

    def analyze(
        self,
        *,
        transactions: Iterable[Transaction],
    ) -> TaxLotAnalysis:
        """Return FIFO open lots and realized gains."""

        ordered_transactions = sorted(
            transactions,
            key=lambda transaction: (
                transaction.transaction_date,
                transaction.id,
            ),
        )

        working_lots: list[_WorkingTaxLot] = []
        realized_gains: list[RealizedGain] = []

        for transaction in ordered_transactions:
            transaction_type = transaction.transaction_type.upper()

            if transaction_type not in _SUPPORTED_TRANSACTION_TYPES:
                raise ValueError(
                    "Unsupported transaction type "
                    f"{transaction.transaction_type!r} "
                    f"for transaction {transaction.id}"
                )

            if transaction.units <= _ZERO_UNITS:
                raise ValueError(
                    "Transaction units must be positive "
                    f"for transaction {transaction.id}"
                )

            if transaction.amount <= _ZERO_MONEY:
                raise ValueError(
                    "Transaction amount must be positive "
                    f"for transaction {transaction.id}"
                )

            if transaction_type in _ACQUISITION_TYPES:
                working_lots.append(
                    _WorkingTaxLot(
                        portfolio_id=transaction.portfolio_id,
                        fund_id=transaction.fund_id,
                        source_transaction_id=transaction.id,
                        acquisition_date=transaction.transaction_date,
                        original_units=transaction.units,
                        remaining_units=transaction.units,
                        cost_per_unit=transaction.nav,
                        remaining_cost_basis=transaction.amount,
                    )
                )
                continue

            available_units = sum(
                (
                    lot.remaining_units
                    for lot in working_lots
                    if (
                        lot.portfolio_id
                        == transaction.portfolio_id
                        and lot.fund_id
                        == transaction.fund_id
                    )
                ),
                start=_ZERO_UNITS,
            )

            if transaction.units > available_units:
                raise ValueError(
                    "Insufficient units for SELL transaction "
                    f"{transaction.id}: requested "
                    f"{transaction.units}, available "
                    f"{available_units}"
                )

            units_to_sell = transaction.units
            allocated_sale_proceeds = _ZERO_MONEY

            for lot in working_lots:
                if units_to_sell <= _ZERO_UNITS:
                    break

                if (
                    lot.portfolio_id
                    != transaction.portfolio_id
                    or lot.fund_id
                    != transaction.fund_id
                ):
                    continue

                if lot.remaining_units <= _ZERO_UNITS:
                    continue

                matched_units = min(
                    units_to_sell,
                    lot.remaining_units,
                )

                if matched_units == lot.remaining_units:
                    matched_cost_basis = lot.remaining_cost_basis
                else:
                    matched_cost_basis = _money(
                        lot.remaining_cost_basis
                        * matched_units
                        / lot.remaining_units
                    )

                if matched_units == units_to_sell:
                    sale_proceeds = _money(
                        transaction.amount
                        - allocated_sale_proceeds
                    )
                else:
                    sale_proceeds = _money(
                        transaction.amount
                        * matched_units
                        / transaction.units
                    )

                realized_gain = _money(
                    sale_proceeds
                    - matched_cost_basis
                )
                holding_period_days = (
                    transaction.transaction_date
                    - lot.acquisition_date
                ).days

                realized_gains.append(
                    RealizedGain(
                        portfolio_id=transaction.portfolio_id,
                        fund_id=transaction.fund_id,
                        sell_transaction_id=transaction.id,
                        source_buy_transaction_id=(
                            lot.source_transaction_id
                        ),
                        acquisition_date=lot.acquisition_date,
                        disposal_date=transaction.transaction_date,
                        holding_period_days=holding_period_days,
                        units_sold=matched_units,
                        sale_proceeds=sale_proceeds,
                        cost_basis=matched_cost_basis,
                        realized_gain=realized_gain,
                    )
                )

                allocated_sale_proceeds += sale_proceeds
                lot.remaining_units -= matched_units
                lot.remaining_cost_basis = _money(
                    lot.remaining_cost_basis
                    - matched_cost_basis
                )
                units_to_sell -= matched_units

        open_lots = [
            TaxLot(
                portfolio_id=lot.portfolio_id,
                fund_id=lot.fund_id,
                source_transaction_id=lot.source_transaction_id,
                acquisition_date=lot.acquisition_date,
                original_units=lot.original_units,
                remaining_units=lot.remaining_units,
                cost_per_unit=lot.cost_per_unit,
                remaining_cost_basis=lot.remaining_cost_basis,
            )
            for lot in working_lots
            if lot.remaining_units > _ZERO_UNITS
        ]

        return TaxLotAnalysis(
            open_lots=open_lots,
            realized_gains=realized_gains,
        )