"""Tests for current-holdings historical portfolio backtesting."""
from datetime import date
from unittest.mock import MagicMock
from pathlib import Path
from models.portfolio_risk_metrics import PortfolioRiskMetrics
from services.portfolio_risk_service import PortfolioRiskService
import importlib

import pandas as pd


def test_build_portfolio_value_history() -> None:
    """Value current units using historical NAV observations."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    portfolio = pd.DataFrame(
        {
            "Scheme Code": [
                "100001",
                "100002",
            ],
            "Units": [
                2.0,
                3.0,
            ],
        }
    )

    nav_history = pd.DataFrame(
        {
            "Scheme Code": [
                "100001",
                "100002",
                "100001",
                "100002",
            ],
            "NAV": [
                10.0,
                20.0,
                11.0,
                19.0,
            ],
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-01-31",
                    "2026-02-28",
                    "2026-02-28",
                ]
            ),
        }
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .build_value_history(
            portfolio=portfolio,
            nav_history=nav_history,
        )
    )

    assert tuple(result.columns) == (
        "Date",
        "Value",
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-28"),
    )

    assert tuple(result["Value"]) == (
        80.0,
        79.0,
    )
def test_sample_month_end_values() -> None:
    """Keep the final available portfolio value in each calendar month."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    value_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-30",
                    "2026-01-31",
                    "2026-02-27",
                    "2026-02-28",
                ]
            ),
            "Value": [
                78.0,
                80.0,
                77.0,
                79.0,
            ],
        }
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .sample_month_end(
            value_history
        )
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-28"),
    )

    assert tuple(result["Value"]) == (
        80.0,
        79.0,
    )
def test_create_monthly_backtest_downloads_held_schemes() -> None:
    """Download held schemes and build a month-end value backtest."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    portfolio = pd.DataFrame(
        {
            "Scheme Code": [
                "100001",
                "100002",
            ],
            "Units": [
                2.0,
                3.0,
            ],
        }
    )

    nav_history = pd.DataFrame(
        {
            "Scheme Code": [
                "100001",
                "100002",
                "100001",
                "100002",
                "100001",
                "100002",
            ],
            "NAV": [
                10.0,
                20.0,
                11.0,
                19.0,
                12.0,
                18.0,
            ],
            "Date": pd.to_datetime(
                [
                    "2026-01-30",
                    "2026-01-30",
                    "2026-01-31",
                    "2026-01-31",
                    "2026-02-28",
                    "2026-02-28",
                ]
            ),
        }
    )

    nav_service = MagicMock()
    nav_service.get_historical_nav.return_value = (
        nav_history
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .create_monthly_backtest(
            portfolio=portfolio,
            from_date=date(2026, 1, 1),
            to_date=date(2026, 2, 28),
            nav_service=nav_service,
        )
    )

    nav_service.get_historical_nav.assert_called_once_with(
        scheme_codes=(
            "100001",
            "100002",
        ),
        from_date=date(2026, 1, 1),
        to_date=date(2026, 2, 28),
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-28"),
    )

    assert tuple(result["Value"]) == (
        79.0,
        78.0,
    )
def test_save_backtest_cache(
    tmp_path,
) -> None:
    """Persist a labelled current-holdings backtest cache."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    backtest = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                ]
            ),
            "Value": [
                80.0,
                79.0,
            ],
        }
    )

    cache_path = (
        tmp_path
        / "portfolio_backtest.csv"
    )

    result_path = (
        backtest_module
        .PortfolioBacktestService()
        .save_backtest(
            backtest,
            cache_path=cache_path,
        )
    )

    assert result_path == cache_path
    assert cache_path.exists()

    saved = pd.read_csv(
        cache_path
    )

    assert tuple(saved.columns) == (
        "Date",
        "Value",
        "Source",
    )

    assert tuple(saved["Source"]) == (
        "current_holdings_backtest",
        "current_holdings_backtest",
    )
def test_load_backtest_cache(
    tmp_path,
) -> None:
    """Load and validate a labelled current-holdings backtest."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    cache_path = (
        tmp_path
        / "portfolio_backtest.csv"
    )

    pd.DataFrame(
        {
            "Date": [
                "2026-01-31",
                "2026-02-28",
            ],
            "Value": [
                80.0,
                79.0,
            ],
            "Source": [
                "current_holdings_backtest",
                "current_holdings_backtest",
            ],
        }
    ).to_csv(
        cache_path,
        index=False,
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .load_backtest(
            cache_path=cache_path,
        )
    )

    assert tuple(result.columns) == (
        "Date",
        "Value",
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-28"),
    )

    assert tuple(result["Value"]) == (
        80.0,
        79.0,
    )
def test_calculate_periodic_returns() -> None:
    """Convert monthly backtest values into decimal returns."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    value_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                    "2026-03-31",
                ]
            ),
            "Value": [
                100.0,
                110.0,
                99.0,
            ],
        }
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .calculate_periodic_returns(
            value_history
        )
    )

    assert result == (
        0.10,
        -0.10,
    )
def test_calculate_risk_metrics_from_backtest() -> None:
    """Calculate institutional risk metrics from monthly backtest returns."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    value_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                    "2026-03-31",
                ]
            ),
            "Value": [
                100.0,
                110.0,
                99.0,
            ],
        }
    )

    expected = PortfolioRiskMetrics(
        calmar_ratio=0.75,
        omega_ratio=1.80,
        value_at_risk=0.10,
        conditional_value_at_risk=0.10,
    )

    risk_service = MagicMock(
        spec=PortfolioRiskService,
    )

    risk_service.calculate.return_value = expected

    result = (
        backtest_module
        .PortfolioBacktestService()
        .calculate_risk_metrics(
            value_history,
            periods_per_year=12,
            risk_service=risk_service,
        )
    )

    assert result is expected

    risk_service.calculate.assert_called_once_with(
        portfolio_returns=(
            0.10,
            -0.10,
        ),
        risk_free_rate=0.0,
        periods_per_year=12,
    )
def test_calculate_rolling_risk_metrics_from_backtest() -> None:
    """Calculate rolling institutional metrics from backtest returns."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    value_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                    "2026-03-31",
                    "2026-04-30",
                ]
            ),
            "Value": [
                100.0,
                110.0,
                99.0,
                108.9,
            ],
        }
    )

    expected = (
        PortfolioRiskMetrics(
            volatility=8.0,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
        ),
    )

    risk_service = MagicMock(
        spec=PortfolioRiskService,
    )

    risk_service.calculate_rolling_risk_metrics.return_value = (
        expected
    )

    result = (
        backtest_module
        .PortfolioBacktestService()
        .calculate_rolling_risk_metrics(
            value_history,
            window_size=2,
            periods_per_year=12,
            risk_service=risk_service,
        )
    )

    assert result == expected

    risk_service.calculate_rolling_risk_metrics.assert_called_once_with(
        portfolio_returns=(
            0.10,
            -0.10,
            0.10,
        ),
        risk_free_rate=0.0,
        periods_per_year=12,
        window_size=2,
    )
def test_load_default_backtest_cache(
    tmp_path,
) -> None:
    """Load the canonical project backtest cache."""

    backtest_module = importlib.import_module(
        "services.portfolio_backtest_service"
    )

    data_folder = (
        tmp_path
        / "data"
    )

    data_folder.mkdir()

    cache_path = (
        data_folder
        / "portfolio_backtest.csv"
    )

    pd.DataFrame(
        {
            "Date": [
                "2026-01-31",
                "2026-02-28",
            ],
            "Value": [
                80.0,
                79.0,
            ],
            "Source": [
                "current_holdings_backtest",
                "current_holdings_backtest",
            ],
        }
    ).to_csv(
        cache_path,
        index=False,
    )

    service = (
        backtest_module
        .PortfolioBacktestService(
            project_root=tmp_path,
        )
    )

    result = service.load_default_backtest()

    assert service.backtest_cache_path == cache_path

    assert len(result) == 2

    assert tuple(result["Value"]) == (
        80.0,
        79.0,
    )