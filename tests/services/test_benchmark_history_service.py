"""Tests for normalized benchmark history loading."""
from services.benchmark_history_service import BenchmarkHistoryService
import importlib

import pandas as pd


def test_load_nifty_50_tri_history(
    tmp_path,
) -> None:
    """Load canonical Nifty 50 TRI values from a cached CSV."""

    benchmark_module = importlib.import_module(
        "services.benchmark_history_service"
    )

    cache_path = (
        tmp_path
        / "nifty_50_tri_history.csv"
    )

    pd.DataFrame(
        {
            "Date": [
                "31-Jan-2026",
                "28-Feb-2026",
                "31-Mar-2026",
            ],
            "Close": [
                36_000.0,
                37_800.0,
                37_044.0,
            ],
        }
    ).to_csv(
        cache_path,
        index=False,
    )

    result = (
        benchmark_module
        .BenchmarkHistoryService()
        .load_history(
            cache_path=cache_path,
        )
    )

    assert tuple(result.columns) == (
        "Date",
        "Benchmark Value",
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-31"),
        pd.Timestamp("2026-02-28"),
        pd.Timestamp("2026-03-31"),
    )

    assert tuple(result["Benchmark Value"]) == (
        36_000.0,
        37_800.0,
        37_044.0,
    )
def test_calculate_periodic_returns() -> None:
    history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2026-01-31", "2026-02-28", "2026-03-31"]
            ),
            "Benchmark Value": [36000.0, 37800.0, 37044.0],
        }
    )

    returns = BenchmarkHistoryService().calculate_periodic_returns(history)

    assert returns == (0.05, -0.02)
def test_align_monthly_returns_uses_calendar_month() -> None:
    portfolio_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-30",
                    "2026-02-27",
                    "2026-03-31",
                ]
            ),
            "Value": [
                100000.0,
                105000.0,
                102900.0,
            ],
        }
    )

    benchmark_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                    "2026-03-30",
                ]
            ),
            "Benchmark Value": [
                36000.0,
                37800.0,
                37044.0,
            ],
        }
    )

    aligned = BenchmarkHistoryService().align_monthly_returns(
        portfolio_history=portfolio_history,
        benchmark_history=benchmark_history,
    )

    assert list(aligned.columns) == [
        "Date",
        "Portfolio Return",
        "Benchmark Return",
    ]
    assert aligned["Date"].tolist() == [
        pd.Timestamp("2026-02-28"),
        pd.Timestamp("2026-03-31"),
    ]
    assert aligned["Portfolio Return"].tolist() == [
        0.05,
        -0.02,
    ]
    assert aligned["Benchmark Return"].tolist() == [
        0.05,
        -0.02,
    ]
def test_load_default_history(tmp_path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()

    cache_path = data_directory / "nifty_50_tri_history.csv"
    cache_path.write_text(
        "Date,Close\n"
        "31-Jan-2026,36000\n"
        "28-Feb-2026,37800\n",
        encoding="utf-8",
    )

    service = BenchmarkHistoryService(
        project_root=tmp_path,
    )

    result = service.load_default_history()

    assert result.to_dict("records") == [
        {
            "Date": pd.Timestamp("2026-01-31"),
            "Benchmark Value": 36000,
        },
        {
            "Date": pd.Timestamp("2026-02-28"),
            "Benchmark Value": 37800,
        },
    ]
def test_align_default_history_with_portfolio(tmp_path) -> None:
    data_directory = tmp_path / "data"
    data_directory.mkdir()

    (
        data_directory / "nifty_50_tri_history.csv"
    ).write_text(
        "Date,Close\n"
        "31-Jan-2026,36000\n"
        "28-Feb-2026,37800\n"
        "30-Mar-2026,37044\n",
        encoding="utf-8",
    )

    portfolio_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-30",
                    "2026-02-27",
                    "2026-03-31",
                ]
            ),
            "Value": [
                100000.0,
                105000.0,
                102900.0,
            ],
        }
    )

    service = BenchmarkHistoryService(
        project_root=tmp_path,
    )

    aligned = service.align_default_history(
        portfolio_history=portfolio_history,
    )

    assert aligned["Portfolio Return"].tolist() == [
        0.05,
        -0.02,
    ]
    assert aligned["Benchmark Return"].tolist() == [
        0.05,
        -0.02,
    ]
def test_load_official_nifty_tri_schema(tmp_path) -> None:
    cache_path = tmp_path / "nifty_50_tri_history.csv"

    cache_path.write_text(
        '"IndexName","Date","Total Returns Index",'
        '"Net Total Return Index"\n'
        '"NIFTY 50","31 Dec 2025","39333.55","34279.31"\n'
        '"NIFTY 50","30 Dec 2025","39046.40","34029.05"\n',
        encoding="utf-8",
    )

    result = BenchmarkHistoryService().load_history(
        cache_path=cache_path,
    )

    assert result.to_dict("records") == [
        {
            "Date": pd.Timestamp("2025-12-30"),
            "Benchmark Value": 39046.40,
        },
        {
            "Date": pd.Timestamp("2025-12-31"),
            "Benchmark Value": 39333.55,
        },
    ]
def test_align_monthly_returns_prevents_benchmark_lookahead() -> None:
    portfolio_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-06-30",
                    "2026-07-17",
                ]
            ),
            "Value": [
                100000.0,
                105000.0,
            ],
        }
    )

    benchmark_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-06-30",
                    "2026-07-17",
                    "2026-07-20",
                ]
            ),
            "Benchmark Value": [
                36000.0,
                37800.0,
                39600.0,
            ],
        }
    )

    aligned = BenchmarkHistoryService().align_monthly_returns(
        portfolio_history=portfolio_history,
        benchmark_history=benchmark_history,
    )

    assert aligned["Portfolio Return"].tolist() == [
        0.05,
    ]
    assert aligned["Benchmark Return"].tolist() == [
        0.05,
    ]