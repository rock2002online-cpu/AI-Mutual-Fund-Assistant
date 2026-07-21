"""Current-holdings historical portfolio backtest service."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from models.portfolio_risk_metrics import PortfolioRiskMetrics
from services.nav_service import NAVService
from services.portfolio_risk_service import PortfolioRiskService


class PortfolioBacktestService:
    """Value current portfolio units using historical scheme NAVs."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
    ) -> None:
        """Initialize canonical project and cache paths."""

        self.project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parent.parent
        )

        self.data_folder = (
            self.project_root
            / "data"
        )

        self.backtest_cache_path = (
            self.data_folder
            / "portfolio_backtest.csv"
        )

    def build_value_history(
        self,
        *,
        portfolio: pd.DataFrame,
        nav_history: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build complete-date historical values for current holdings."""

        if not isinstance(portfolio, pd.DataFrame):
            raise TypeError(
                "portfolio must be a pandas DataFrame"
            )

        if not isinstance(nav_history, pd.DataFrame):
            raise TypeError(
                "nav_history must be a pandas DataFrame"
            )

        self._require_columns(
            portfolio,
            required=(
                "Scheme Code",
                "Units",
            ),
            source_name="portfolio",
        )

        self._require_columns(
            nav_history,
            required=(
                "Scheme Code",
                "NAV",
                "Date",
            ),
            source_name="nav_history",
        )

        holdings = portfolio[
            [
                "Scheme Code",
                "Units",
            ]
        ].copy()

        holdings["Scheme Code"] = (
            holdings["Scheme Code"]
            .astype(str)
            .str.strip()
        )

        holdings["Units"] = pd.to_numeric(
            holdings["Units"],
            errors="coerce",
        )

        holdings = holdings.dropna(
            subset=[
                "Scheme Code",
                "Units",
            ]
        )

        holdings = holdings[
            holdings["Scheme Code"] != ""
        ]

        holdings = holdings.drop_duplicates(
            subset=[
                "Scheme Code",
            ],
            keep="last",
        )

        if holdings.empty:
            return self._empty_value_history()

        history = nav_history[
            [
                "Scheme Code",
                "NAV",
                "Date",
            ]
        ].copy()

        history["Scheme Code"] = (
            history["Scheme Code"]
            .astype(str)
            .str.strip()
        )

        history["NAV"] = pd.to_numeric(
            history["NAV"],
            errors="coerce",
        )

        history["Date"] = pd.to_datetime(
            history["Date"],
            errors="coerce",
        )

        history = history.dropna(
            subset=[
                "Scheme Code",
                "NAV",
                "Date",
            ]
        )

        history = history.drop_duplicates(
            subset=[
                "Scheme Code",
                "Date",
            ],
            keep="last",
        )

        valued_holdings = history.merge(
            holdings,
            on="Scheme Code",
            how="inner",
            validate="many_to_one",
        )

        if valued_holdings.empty:
            return self._empty_value_history()

        valued_holdings["Holding Value"] = (
            valued_holdings["NAV"]
            * valued_holdings["Units"]
        )

        required_holding_count = len(
            holdings
        )

        grouped = valued_holdings.groupby(
            "Date",
            as_index=False,
        ).agg(
            Value=(
                "Holding Value",
                "sum",
            ),
            Holding_Count=(
                "Scheme Code",
                "nunique",
            ),
        )

        complete_dates = grouped[
            grouped["Holding_Count"]
            == required_holding_count
        ]

        result = complete_dates[
            [
                "Date",
                "Value",
            ]
        ].sort_values(
            "Date"
        )

        return result.reset_index(
            drop=True,
        )

    def sample_month_end(
        self,
        value_history: pd.DataFrame,
    ) -> pd.DataFrame:
        """Keep the final valid portfolio value in each calendar month."""

        if not isinstance(value_history, pd.DataFrame):
            raise TypeError(
                "value_history must be a pandas DataFrame"
            )

        self._require_columns(
            value_history,
            required=(
                "Date",
                "Value",
            ),
            source_name="value_history",
        )

        normalized = value_history[
            [
                "Date",
                "Value",
            ]
        ].copy()

        normalized["Date"] = pd.to_datetime(
            normalized["Date"],
            errors="coerce",
        )

        normalized["Value"] = pd.to_numeric(
            normalized["Value"],
            errors="coerce",
        )

        normalized = normalized.dropna(
            subset=[
                "Date",
                "Value",
            ]
        )

        if normalized.empty:
            return self._empty_value_history()

        normalized = normalized.sort_values(
            "Date"
        )

        normalized["Month"] = (
            normalized["Date"]
            .dt.to_period("M")
        )

        month_end = normalized.groupby(
            "Month",
            as_index=False,
            sort=True,
        ).tail(1)

        result = month_end[
            [
                "Date",
                "Value",
            ]
        ].sort_values(
            "Date"
        )

        return result.reset_index(
            drop=True,
        )

    def create_monthly_backtest(
        self,
        *,
        portfolio: pd.DataFrame,
        from_date: date,
        to_date: date,
        nav_service: NAVService | None = None,
    ) -> pd.DataFrame:
        """Download held-scheme NAVs and build a monthly backtest."""

        if not isinstance(portfolio, pd.DataFrame):
            raise TypeError(
                "portfolio must be a pandas DataFrame"
            )

        self._require_columns(
            portfolio,
            required=(
                "Scheme Code",
                "Units",
            ),
            source_name="portfolio",
        )

        scheme_codes = tuple(
            dict.fromkeys(
                scheme_code
                for scheme_code in (
                    portfolio["Scheme Code"]
                    .astype(str)
                    .str.strip()
                )
                if scheme_code
            )
        )

        if not scheme_codes:
            return self._empty_value_history()

        resolved_nav_service = (
            nav_service
            if nav_service is not None
            else NAVService()
        )

        nav_history = resolved_nav_service.get_historical_nav(
            scheme_codes=scheme_codes,
            from_date=from_date,
            to_date=to_date,
        )

        value_history = self.build_value_history(
            portfolio=portfolio,
            nav_history=nav_history,
        )

        return self.sample_month_end(
            value_history
        )

    def save_backtest(
        self,
        backtest: pd.DataFrame,
        *,
        cache_path: Path,
    ) -> Path:
        """Persist a labelled current-holdings backtest cache."""

        if not isinstance(backtest, pd.DataFrame):
            raise TypeError(
                "backtest must be a pandas DataFrame"
            )

        self._require_columns(
            backtest,
            required=(
                "Date",
                "Value",
            ),
            source_name="backtest",
        )

        resolved_cache_path = Path(
            cache_path
        )

        cached = backtest[
            [
                "Date",
                "Value",
            ]
        ].copy()

        cached["Date"] = pd.to_datetime(
            cached["Date"],
            errors="coerce",
        )

        cached["Value"] = pd.to_numeric(
            cached["Value"],
            errors="coerce",
        )

        cached = cached.dropna(
            subset=[
                "Date",
                "Value",
            ]
        )

        cached = cached.sort_values(
            "Date"
        ).reset_index(
            drop=True,
        )

        cached["Source"] = (
            "current_holdings_backtest"
        )

        resolved_cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cached.to_csv(
            resolved_cache_path,
            index=False,
            date_format="%Y-%m-%d",
        )

        return resolved_cache_path

    def load_backtest(
        self,
        *,
        cache_path: Path,
    ) -> pd.DataFrame:
        """Load a validated current-holdings backtest cache."""

        resolved_cache_path = Path(
            cache_path
        )

        if not resolved_cache_path.exists():
            return self._empty_value_history()

        cached = pd.read_csv(
            resolved_cache_path
        )

        self._require_columns(
            cached,
            required=(
                "Date",
                "Value",
                "Source",
            ),
            source_name="backtest cache",
        )

        valid_source = (
            cached["Source"]
            == "current_holdings_backtest"
        )

        if not valid_source.all():
            raise ValueError(
                "backtest cache contains an unsupported Source"
            )

        result = cached[
            [
                "Date",
                "Value",
            ]
        ].copy()

        result["Date"] = pd.to_datetime(
            result["Date"],
            errors="coerce",
        )

        result["Value"] = pd.to_numeric(
            result["Value"],
            errors="coerce",
        )

        result = result.dropna(
            subset=[
                "Date",
                "Value",
            ]
        )

        result = result.drop_duplicates(
            subset=[
                "Date",
            ],
            keep="last",
        )

        result = result.sort_values(
            "Date"
        )

        return result.reset_index(
            drop=True,
        )

    def load_default_backtest(
        self,
    ) -> pd.DataFrame:
        """Load the canonical project backtest cache."""

        return self.load_backtest(
            cache_path=self.backtest_cache_path,
        )

    def calculate_periodic_returns(
        self,
        value_history: pd.DataFrame,
    ) -> tuple[float, ...]:
        """Convert chronological portfolio values into decimal returns."""

        if not isinstance(value_history, pd.DataFrame):
            raise TypeError(
                "value_history must be a pandas DataFrame"
            )

        self._require_columns(
            value_history,
            required=(
                "Date",
                "Value",
            ),
            source_name="value_history",
        )

        normalized = value_history[
            [
                "Date",
                "Value",
            ]
        ].copy()

        normalized["Date"] = pd.to_datetime(
            normalized["Date"],
            errors="coerce",
        )

        normalized["Value"] = pd.to_numeric(
            normalized["Value"],
            errors="coerce",
        )

        normalized = normalized.dropna(
            subset=[
                "Date",
                "Value",
            ]
        ).sort_values(
            "Date"
        )

        normalized = normalized[
            normalized["Value"] > 0.0
        ]

        values = tuple(
            float(value)
            for value in normalized["Value"]
        )

        if len(values) < 2:
            return ()

        return tuple(
            round(
                current_value
                / previous_value
                - 1.0,
                15,
            )
            for previous_value, current_value in zip(
                values[:-1],
                values[1:],
                strict=True,
            )
        )

    def calculate_risk_metrics(
        self,
        value_history: pd.DataFrame,
        *,
        periods_per_year: int = 12,
        risk_free_rate: float = 0.0,
        risk_service: PortfolioRiskService | None = None,
    ) -> PortfolioRiskMetrics:
        """Calculate portfolio-only risk metrics from a backtest."""

        periodic_returns = self.calculate_periodic_returns(
            value_history
        )

        resolved_risk_service = (
            risk_service
            if risk_service is not None
            else PortfolioRiskService()
        )

        return resolved_risk_service.calculate(
            portfolio_returns=periodic_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )

    def calculate_rolling_risk_metrics(
        self,
        value_history: pd.DataFrame,
        *,
        window_size: int = 12,
        periods_per_year: int = 12,
        risk_free_rate: float = 0.0,
        risk_service: PortfolioRiskService | None = None,
    ) -> tuple[PortfolioRiskMetrics, ...]:
        """Calculate rolling portfolio-only metrics from a backtest."""

        periodic_returns = self.calculate_periodic_returns(
            value_history
        )

        resolved_risk_service = (
            risk_service
            if risk_service is not None
            else PortfolioRiskService()
        )

        return resolved_risk_service.calculate_rolling_risk_metrics(
            portfolio_returns=periodic_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
            window_size=window_size,
        )

    @staticmethod
    def _require_columns(
        data: pd.DataFrame,
        *,
        required: tuple[str, ...],
        source_name: str,
    ) -> None:
        """Validate required dataframe columns."""

        missing = [
            column
            for column in required
            if column not in data.columns
        ]

        if missing:
            raise ValueError(
                f"{source_name} is missing required columns: "
                + ", ".join(missing)
            )

    @staticmethod
    def _empty_value_history() -> pd.DataFrame:
        """Return an empty canonical backtest dataframe."""

        return pd.DataFrame(
            columns=[
                "Date",
                "Value",
            ]
        )


__all__ = [
    "PortfolioBacktestService",
]