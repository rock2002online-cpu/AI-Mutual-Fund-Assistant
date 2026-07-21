"""Transaction-history import validation and normalization service."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from models.transaction import Transaction
from repositories.unit_of_work import UnitOfWork


class TransactionImportService:
    """Load and normalize transaction-history CSV files."""

    REQUIRED_COLUMNS = (
        "Date",
        "Scheme Code",
        "Transaction Type",
        "Units",
        "Amount",
    )

    def __init__(
        self,
        unit_of_work_factory: Callable | None = None,
    ) -> None:
        """Configure the repository UnitOfWork used for fund resolution."""

        self._unit_of_work_factory = (
            unit_of_work_factory
            if unit_of_work_factory is not None
            else UnitOfWork
        )

    def import_csv(
        self,
        *,
        csv_path: Path,
        portfolio_id: int,
        persist: bool = False,
    ) -> tuple[Transaction, ...]:
        """Validate and prepare a CSV, persisting only when requested."""

        loaded = self.load_csv(
            csv_path=csv_path,
        )
        resolved = self.resolve_funds(
            loaded
        )
        prepared = self.build_transactions(
            portfolio_id=portfolio_id,
            resolved_transactions=resolved,
        )

        if persist:
            return self.save_transactions(
                prepared
            )

        return prepared

    def resolve_funds(
        self,
        transactions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Add existing database fund IDs to normalized transactions."""

        result = transactions.copy()
        fund_ids: dict[str, int] = {}

        with self._unit_of_work_factory() as unit_of_work:
            for scheme_code in result["Scheme Code"].unique():
                normalized_code = str(scheme_code).strip()
                fund = unit_of_work.funds.get_by_scheme_code(
                    normalized_code
                )

                if fund is None:
                    raise ValueError(
                        "unknown scheme code: "
                        + normalized_code
                    )

                fund_ids[normalized_code] = int(fund.id)

        result["Fund ID"] = result["Scheme Code"].map(
            lambda value: fund_ids[str(value).strip()]
        )

        return result

    def build_transactions(
        self,
        *,
        portfolio_id: int,
        resolved_transactions: pd.DataFrame,
    ) -> tuple[Transaction, ...]:
        """Build unsaved Transaction entities from validated rows."""

        return tuple(
            Transaction(
                portfolio_id=portfolio_id,
                fund_id=int(row["Fund ID"]),
                transaction_date=row["Date"],
                transaction_type=row["Transaction Type"],
                units=float(row["Units"]),
                nav=(
                    float(row["Amount"])
                    / float(row["Units"])
                ),
                amount=float(row["Amount"]),
            )
            for _, row in resolved_transactions.iterrows()
        )

    def save_transactions(
        self,
        transactions: tuple[Transaction, ...],
    ) -> tuple[Transaction, ...]:
        """Persist a prepared transaction batch in one UnitOfWork."""

        persisted: list[Transaction] = []

        with self._unit_of_work_factory() as unit_of_work:
            portfolio_ids = {
                int(transaction.portfolio_id)
                for transaction in transactions
            }
            existing_keys = {
                self._transaction_key(existing)
                for portfolio_id in portfolio_ids
                for existing in (
                    unit_of_work.transactions.get_for_portfolio(
                        portfolio_id
                    )
                )
            }
            incoming_keys: set[tuple[object, ...]] = set()

            for transaction in transactions:
                transaction_key = self._transaction_key(
                    transaction
                )

                if (
                    transaction_key in existing_keys
                    or transaction_key in incoming_keys
                ):
                    raise ValueError(
                        "duplicate transaction"
                    )

                incoming_keys.add(transaction_key)

            for transaction in transactions:
                persisted.append(
                    unit_of_work.transactions.add(
                        transaction
                    )
                )

            unit_of_work.commit()

        return tuple(persisted)

    @staticmethod
    def _transaction_key(
        transaction: Transaction,
    ) -> tuple[object, ...]:
        """Return the business fields that identify one transaction."""

        return (
            int(transaction.portfolio_id),
            int(transaction.fund_id),
            transaction.transaction_date,
            str(transaction.transaction_type).strip().upper(),
            float(transaction.units),
            float(transaction.amount),
        )

    def load_csv(
        self,
        *,
        csv_path: Path,
    ) -> pd.DataFrame:
        """Load a transaction CSV without changing database state."""

        resolved_path = Path(csv_path)
        source = pd.read_csv(
            resolved_path,
            dtype={"Scheme Code": str},
        )

        missing_columns = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in source.columns
        ]

        if missing_columns:
            raise ValueError(
                "transaction history is missing required columns: "
                + ", ".join(missing_columns)
            )

        result = source[list(self.REQUIRED_COLUMNS)].copy()
        result["Date"] = pd.to_datetime(
            result["Date"],
            errors="coerce",
            dayfirst=True,
        )
        result["Scheme Code"] = (
            result["Scheme Code"].astype(str).str.strip()
        )
        result["Transaction Type"] = (
            result["Transaction Type"].astype(str).str.strip().str.upper()
        )
        result["Units"] = pd.to_numeric(
            result["Units"],
            errors="coerce",
        )
        result["Amount"] = pd.to_numeric(
            result["Amount"],
            errors="coerce",
        )

        future_rows = result[
            result["Date"] > pd.Timestamp(date.today())
        ]

        if not future_rows.empty:
            row_numbers = ", ".join(
                str(index + 2)
                for index in future_rows.index
            )
            raise ValueError(
                "transaction history contains future transaction dates "
                "in rows: "
                + row_numbers
            )

        invalid_rows = result[
            result.isna().any(axis=1)
            | ~result["Transaction Type"].isin({"BUY", "SELL"})
            | (result["Scheme Code"] == "")
            | (result["Units"] <= 0.0)
            | (result["Amount"] <= 0.0)
        ]

        if not invalid_rows.empty:
            row_numbers = ", ".join(
                str(index + 2)
                for index in invalid_rows.index
            )
            raise ValueError(
                "transaction history contains invalid rows: "
                + row_numbers
            )

        result["Date"] = result["Date"].dt.date

        return result.sort_values(
            ["Date", "Scheme Code"],
            ignore_index=True,
        )


__all__ = ["TransactionImportService"]