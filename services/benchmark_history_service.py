"""Normalized benchmark history service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class BenchmarkHistoryService:
    """Load and normalize cached Nifty 50 TRI history."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
    ) -> None:
        """Configure the project root used by the default cache loader."""

        self.project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parent.parent
        )

    def load_default_history(self) -> pd.DataFrame:
        """Load the project's default cached Nifty 50 TRI history."""

        return self.load_history(
            cache_path=(
                self.project_root
                / "data"
                / "nifty_50_tri_history.csv"
            ),
        )

    def align_default_history(
        self,
        *,
        portfolio_history: pd.DataFrame,
    ) -> pd.DataFrame:
        """Align portfolio history with the default benchmark cache."""

        return self.align_monthly_returns(
            portfolio_history=portfolio_history,
            benchmark_history=self.load_default_history(),
        )

    def load_history(
        self,
        *,
        cache_path: Path,
    ) -> pd.DataFrame:
        """Load canonical benchmark values from a CSV cache."""

        resolved_cache_path = Path(
            cache_path
        )

        if not resolved_cache_path.exists():
            return self._empty_history()

        cached = pd.read_csv(
            resolved_cache_path
        )

        if "Date" not in cached.columns:
            raise ValueError(
                "benchmark history is missing required columns: Date"
            )

        value_column = next(
            (
                column
                for column in (
                    "Total Returns Index",
                    "Close",
                )
                if column in cached.columns
            ),
            None,
        )

        if value_column is None:
            raise ValueError(
                "benchmark history requires either "
                "Total Returns Index or Close"
            )

        result = cached[
            [
                "Date",
                value_column,
            ]
        ].copy()

        result["Date"] = pd.to_datetime(
            result["Date"],
            errors="coerce",
            dayfirst=True,
        )

        result["Benchmark Value"] = pd.to_numeric(
            result[value_column],
            errors="coerce",
        )

        result = result.dropna(
            subset=[
                "Date",
                "Benchmark Value",
            ]
        )

        result = result[
            result["Benchmark Value"] > 0.0
        ]

        result = result.drop_duplicates(
            subset=[
                "Date",
            ],
            keep="last",
        )

        result = result[
            [
                "Date",
                "Benchmark Value",
            ]
        ].sort_values(
            "Date"
        )

        return result.reset_index(
            drop=True,
        )

    def calculate_periodic_returns(
        self,
        history: pd.DataFrame,
    ) -> tuple[float, ...]:
        """Calculate consecutive benchmark returns from normalized values."""

        values = tuple(
            float(value)
            for value in history["Benchmark Value"]
        )

        return tuple(
            round(
                (current_value / previous_value) - 1.0,
                15,
            )
            for previous_value, current_value in zip(
                values[:-1],
                values[1:],
                strict=True,
            )
        )

    def align_monthly_returns(
        self,
        *,
        portfolio_history: pd.DataFrame,
        benchmark_history: pd.DataFrame,
    ) -> pd.DataFrame:
        """Align portfolio and benchmark returns by calendar month."""

        portfolio = portfolio_history[
            ["Date", "Value"]
        ].copy()
        benchmark = benchmark_history[
            ["Date", "Benchmark Value"]
        ].copy()

        portfolio["Date"] = pd.to_datetime(
            portfolio["Date"],
            errors="coerce",
        )
        benchmark["Date"] = pd.to_datetime(
            benchmark["Date"],
            errors="coerce",
        )

        portfolio = portfolio.dropna(
            subset=["Date", "Value"],
        ).sort_values("Date")
        benchmark = benchmark.dropna(
            subset=["Date", "Benchmark Value"],
        ).sort_values("Date")

        if not portfolio.empty:
            benchmark = benchmark[
                benchmark["Date"] <= portfolio["Date"].max()
            ]

        portfolio["Month"] = portfolio["Date"].dt.to_period("M")
        benchmark["Month"] = benchmark["Date"].dt.to_period("M")

        portfolio = portfolio.groupby(
            "Month",
            as_index=False,
        ).last()
        benchmark = benchmark.groupby(
            "Month",
            as_index=False,
        ).last()

        aligned = portfolio[
            ["Month", "Value"]
        ].merge(
            benchmark[["Month", "Benchmark Value"]],
            on="Month",
            how="inner",
        ).sort_values("Month")

        aligned["Portfolio Return"] = (
            aligned["Value"].pct_change().round(15)
        )
        aligned["Benchmark Return"] = (
            aligned["Benchmark Value"].pct_change().round(15)
        )
        aligned["Date"] = aligned["Month"].dt.to_timestamp(
            how="end",
        ).dt.normalize()

        aligned = aligned.dropna(
            subset=["Portfolio Return", "Benchmark Return"],
        )

        return aligned[
            ["Date", "Portfolio Return", "Benchmark Return"]
        ].reset_index(drop=True)

    @staticmethod
    def _empty_history() -> pd.DataFrame:
        """Return an empty canonical benchmark history."""

        return pd.DataFrame(
            columns=[
                "Date",
                "Benchmark Value",
            ]
        )


__all__ = [
    "BenchmarkHistoryService",
]