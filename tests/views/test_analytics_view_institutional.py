"""Tests for institutional analytics-view integration."""

from unittest.mock import MagicMock, patch
from models.portfolio_risk_metrics import PortfolioRiskMetrics
from datetime import date
from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from views.analytics_view import (
    _render_advanced_kpi_section,
)
from views.analytics_view import (
    _render_advanced_kpi_section,
    _render_risk_chart_section,
)

@patch(
    "views.analytics_view.render_institutional_kpis",
    create=True,
)
@patch(
    "views.analytics_view.render_advanced_kpis",
)
def test_render_advanced_kpi_section_includes_institutional_kpis(
    mock_render_advanced_kpis,
    mock_render_institutional_kpis,
) -> None:
    """Render both advanced and institutional KPI sections."""

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(),
    )

    _render_advanced_kpi_section(
        service_result
    )

    mock_render_advanced_kpis.assert_called_once_with(
        service_result
    )

    mock_render_institutional_kpis.assert_called_once_with(
        service_result
    )
def test_render_advanced_kpi_section_includes_tail_risk_kpis() -> None:
    """Calculate and render institutional tail-risk metrics."""

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(),
    )

    metrics = PortfolioRiskMetrics(
        calmar_ratio=0.75,
        omega_ratio=1.80,
        value_at_risk=0.04,
        conditional_value_at_risk=0.06,
    )

    with (
        patch(
            "views.analytics_view.render_advanced_kpis",
        ),
        patch(
            "views.analytics_view.render_institutional_kpis",
        ),
        patch(
            "views.analytics_view."
            "calculate_institutional_risk_metrics",
            create=True,
            return_value=metrics,
        ) as mock_calculate,
        patch(
            "views.analytics_view."
            "render_institutional_risk_kpis",
            create=True,
        ) as mock_render_tail_risk,
    ):
        _render_advanced_kpi_section(
            service_result
        )

    mock_calculate.assert_called_once_with(
        service_result
    )

    mock_render_tail_risk.assert_called_once_with(
        metrics
    )

def test_render_risk_chart_section_includes_rolling_risk_chart() -> None:
    """Calculate and render institutional rolling risk trends."""

    service_result = AdvancedAnalyticsServiceResult(
        status="complete",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=(),
        failures=(),
    )

    rolling_metrics = (
        PortfolioRiskMetrics(
            volatility=8.0,
            sharpe_ratio=0.80,
            sortino_ratio=1.10,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
            sharpe_ratio=0.90,
            sortino_ratio=1.20,
        ),
    )

    with (
        patch(
            "views.analytics_view.render_risk_charts",
        ),
        patch(
            "views.analytics_view.calculate_rolling_risk_metrics",
            create=True,
            return_value=rolling_metrics,
        ) as mock_calculate,
        patch(
            "views.analytics_view.render_rolling_risk_chart",
            create=True,
        ) as mock_render,
    ):
        _render_risk_chart_section(
            service_result
        )

    mock_calculate.assert_called_once_with(
        service_result
    )

    mock_render.assert_called_once_with(
        rolling_metrics
    )
def test_tail_risk_uses_backtest_when_benchmark_is_unavailable() -> None:
    """Fall back to the labelled backtest for portfolio-only tail risk."""

    service_result = AdvancedAnalyticsServiceResult(
        status="unavailable",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=("benchmark",),
        failures=(),
    )

    backtest_history = MagicMock()

    metrics = PortfolioRiskMetrics(
        calmar_ratio=0.75,
        omega_ratio=1.80,
        value_at_risk=0.04,
        conditional_value_at_risk=0.06,
    )

    with (
        patch(
            "views.analytics_view.render_advanced_kpis",
        ),
        patch(
            "views.analytics_view.render_institutional_kpis",
        ),
        patch(
            "views.analytics_view."
            "calculate_institutional_risk_metrics",
            return_value=None,
        ),
        patch(
            "views.analytics_view.PortfolioBacktestService",
            create=True,
        ) as mock_backtest_service_class,
        patch(
            "views.analytics_view."
            "render_institutional_risk_kpis",
        ) as mock_render_tail_risk,
    ):
        backtest_service = (
            mock_backtest_service_class.return_value
        )

        backtest_service.load_default_backtest.return_value = (
            backtest_history
        )

        backtest_service.calculate_risk_metrics.return_value = (
            metrics
        )

        _render_advanced_kpi_section(
            service_result
        )

    backtest_service.load_default_backtest.assert_called_once_with()

    backtest_service.calculate_risk_metrics.assert_called_once_with(
        backtest_history
    )

    mock_render_tail_risk.assert_called_once_with(
        metrics,
        source_label=(
            "Current-holdings historical backtest"
        ),
    )
def test_rolling_risk_uses_backtest_when_benchmark_is_unavailable() -> None:
    """Fall back to the labelled backtest for rolling risk trends."""

    service_result = AdvancedAnalyticsServiceResult(
        status="unavailable",
        portfolio=(),
        portfolio_totals=None,
        adapter_result=None,
        analytics=None,
        available_metrics=(),
        unavailable_metrics=("benchmark",),
        failures=(),
    )

    backtest_history = MagicMock()

    rolling_metrics = (
        PortfolioRiskMetrics(
            volatility=8.0,
            sharpe_ratio=0.80,
            sortino_ratio=1.10,
        ),
        PortfolioRiskMetrics(
            volatility=9.0,
            sharpe_ratio=0.90,
            sortino_ratio=1.20,
        ),
    )

    with (
        patch(
            "views.analytics_view.render_risk_charts",
        ),
        patch(
            "views.analytics_view."
            "calculate_rolling_risk_metrics",
            return_value=(),
        ),
        patch(
            "views.analytics_view.PortfolioBacktestService",
        ) as mock_backtest_service_class,
        patch(
            "views.analytics_view.render_rolling_risk_chart",
        ) as mock_render_rolling,
    ):
        backtest_service = (
            mock_backtest_service_class.return_value
        )

        backtest_service.load_default_backtest.return_value = (
            backtest_history
        )

        backtest_service.calculate_rolling_risk_metrics.return_value = (
            rolling_metrics
        )

        _render_risk_chart_section(
            service_result
        )

    backtest_service.load_default_backtest.assert_called_once_with()

    backtest_service.calculate_rolling_risk_metrics.assert_called_once_with(
        backtest_history
    )

    mock_render_rolling.assert_called_once_with(
        rolling_metrics,
        source_label=(
            "Current-holdings historical backtest"
        ),
    )
def test_advanced_analytics_uses_default_benchmark_returns(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import pandas as pd

    import views.analytics_view as analytics_view

    portfolio = pd.DataFrame(
        {
            "Fund": ["Example Fund"],
            "Current Value": [100000.0],
        }
    )

    backtest_history = pd.DataFrame(
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

    aligned_returns = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-02-28",
                    "2026-03-31",
                ]
            ),
            "Portfolio Return": [
                0.05,
                -0.02,
            ],
            "Benchmark Return": [
                0.05,
                -0.02,
            ],
        }
    )

    backtest_service = Mock()
    backtest_service.load_default_backtest.return_value = (
        backtest_history
    )

    benchmark_service = Mock()
    benchmark_service.align_default_history.return_value = (
        aligned_returns
    )

    advanced_service = Mock()
    expected_result = Mock()
    advanced_service.calculate.return_value = expected_result

    monkeypatch.setattr(
        analytics_view,
        "PortfolioBacktestService",
        lambda: backtest_service,
    )
    monkeypatch.setattr(
        analytics_view,
        "BenchmarkHistoryService",
        lambda: benchmark_service,
        raising=False,
    )
    monkeypatch.setattr(
        analytics_view,
        "AdvancedAnalyticsService",
        lambda **kwargs: advanced_service,
    )

    result = analytics_view._calculate_advanced_analytics(
        portfolio
    )

    backtest_service.load_default_backtest.assert_called_once_with()

    benchmark_service.align_default_history.assert_called_once_with(
        portfolio_history=backtest_history,
    )

    service_input = advanced_service.calculate.call_args.args[0]
    assert service_input.portfolio_history is backtest_history
    assert (
        service_input.aligned_benchmark_returns
        is aligned_returns
    )
    assert service_input.benchmark_name == "Nifty 50 TRI"
    assert service_input.periods_per_year == 12
    assert result is expected_result
def test_advanced_analytics_handles_empty_benchmark_history(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import pandas as pd

    import views.analytics_view as analytics_view

    portfolio = pd.DataFrame(
        {
            "Fund": ["Example Fund"],
            "Current Value": [100000.0],
        }
    )

    backtest_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                ]
            ),
            "Value": [
                100000.0,
                105000.0,
            ],
        }
    )

    backtest_service = Mock()
    backtest_service.load_default_backtest.return_value = (
        backtest_history
    )

    benchmark_service = Mock()
    benchmark_service.align_default_history.return_value = (
        pd.DataFrame(
            columns=[
                "Date",
                "Portfolio Return",
                "Benchmark Return",
            ]
        )
    )

    advanced_service = Mock()
    expected_result = Mock()
    advanced_service.calculate.return_value = expected_result

    monkeypatch.setattr(
        analytics_view,
        "PortfolioBacktestService",
        lambda: backtest_service,
    )
    monkeypatch.setattr(
        analytics_view,
        "BenchmarkHistoryService",
        lambda: benchmark_service,
    )
    monkeypatch.setattr(
        analytics_view,
        "AdvancedAnalyticsService",
        lambda **kwargs: advanced_service,
    )

    result = analytics_view._calculate_advanced_analytics(
        portfolio
    )

    service_input = advanced_service.calculate.call_args.args[0]

    assert service_input.aligned_benchmark_returns is None
    assert service_input.benchmark_name is None
    assert result is expected_result
def test_tail_risk_preserves_explicit_backtest_source(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import views.analytics_view as analytics_view

    service_result = Mock()
    risk_metrics = Mock()

    calculate_metrics = Mock(
        return_value=risk_metrics,
    )
    render_metrics = Mock()

    monkeypatch.setattr(
        analytics_view,
        "render_advanced_kpis",
        Mock(),
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_kpis",
        Mock(),
    )
    monkeypatch.setattr(
        analytics_view,
        "calculate_institutional_risk_metrics",
        calculate_metrics,
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_risk_kpis",
        render_metrics,
    )

    analytics_view._render_advanced_kpi_section(
        service_result,
        source_label="Current-holdings historical backtest",
    )

    render_metrics.assert_called_once_with(
        risk_metrics,
        source_label="Current-holdings historical backtest",
    )
def test_rolling_risk_preserves_explicit_backtest_source(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import views.analytics_view as analytics_view

    service_result = Mock()
    rolling_metrics = (Mock(),)

    calculate_metrics = Mock(
        return_value=rolling_metrics,
    )
    render_chart = Mock()

    monkeypatch.setattr(
        analytics_view,
        "render_risk_charts",
        Mock(),
    )
    monkeypatch.setattr(
        analytics_view,
        "calculate_rolling_risk_metrics",
        calculate_metrics,
    )
    monkeypatch.setattr(
        analytics_view,
        "render_rolling_risk_chart",
        render_chart,
    )

    analytics_view._render_risk_chart_section(
        service_result,
        source_label="Current-holdings historical backtest",
    )

    render_chart.assert_called_once_with(
        rolling_metrics,
        source_label="Current-holdings historical backtest",
    )
def test_advanced_section_labels_backtest_derived_analytics(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import pandas as pd

    import views.analytics_view as analytics_view

    portfolio = pd.DataFrame(
        {
            "Fund": ["Example Fund"],
            "Current Value": [100000.0],
        }
    )

    service_result = Mock()
    render_kpis = Mock()
    render_charts = Mock()

    monkeypatch.setattr(
        analytics_view,
        "_calculate_advanced_analytics",
        Mock(return_value=service_result),
    )
    monkeypatch.setattr(
        analytics_view,
        "_render_advanced_kpi_section",
        render_kpis,
    )
    monkeypatch.setattr(
        analytics_view,
        "_render_risk_chart_section",
        render_charts,
    )
    monkeypatch.setattr(
        analytics_view.st,
        "divider",
        Mock(),
    )

    analytics_view._render_advanced_analytics_section(
        portfolio
    )

    source_label = "Current-holdings historical backtest"

    render_kpis.assert_called_once_with(
        service_result,
        source_label=source_label,
    )

    render_charts.assert_called_once_with(
        service_result,
        source_label=source_label,
    )
def test_advanced_kpis_receive_backtest_source(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import views.analytics_view as analytics_view

    service_result = Mock()
    risk_metrics = Mock()
    render_advanced = Mock()

    monkeypatch.setattr(
        analytics_view,
        "render_advanced_kpis",
        render_advanced,
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_kpis",
        Mock(),
    )
    monkeypatch.setattr(
        analytics_view,
        "calculate_institutional_risk_metrics",
        Mock(return_value=risk_metrics),
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_risk_kpis",
        Mock(),
    )

    source_label = "Current-holdings historical backtest"

    analytics_view._render_advanced_kpi_section(
        service_result,
        source_label=source_label,
    )

    render_advanced.assert_called_once_with(
        service_result,
        source_label=source_label,
    )
def test_institutional_kpis_receive_backtest_source(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import views.analytics_view as analytics_view

    service_result = Mock()
    risk_metrics = Mock()
    render_institutional = Mock()

    monkeypatch.setattr(
        analytics_view,
        "render_advanced_kpis",
        Mock(),
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_kpis",
        render_institutional,
    )
    monkeypatch.setattr(
        analytics_view,
        "calculate_institutional_risk_metrics",
        Mock(return_value=risk_metrics),
    )
    monkeypatch.setattr(
        analytics_view,
        "render_institutional_risk_kpis",
        Mock(),
    )

    source_label = "Current-holdings historical backtest"

    analytics_view._render_advanced_kpi_section(
        service_result,
        source_label=source_label,
    )

    render_institutional.assert_called_once_with(
        service_result,
        source_label=source_label,
    )

def test_risk_charts_receive_backtest_source(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import views.analytics_view as analytics_view

    service_result = Mock()
    rolling_metrics = (Mock(),)
    render_charts = Mock()

    monkeypatch.setattr(
        analytics_view,
        "render_risk_charts",
        render_charts,
    )
    monkeypatch.setattr(
        analytics_view,
        "calculate_rolling_risk_metrics",
        Mock(return_value=rolling_metrics),
    )
    monkeypatch.setattr(
        analytics_view,
        "render_rolling_risk_chart",
        Mock(),
    )

    source_label = "Current-holdings historical backtest"

    analytics_view._render_risk_chart_section(
        service_result,
        source_label=source_label,
    )

    render_charts.assert_called_once_with(
        service_result,
        source_label=source_label,
    )

def test_advanced_analytics_uses_transaction_cash_flows(
    monkeypatch,
) -> None:
    from unittest.mock import Mock

    import pandas as pd

    import views.analytics_view as analytics_view

    portfolio = pd.DataFrame(
        {
            "Fund": ["Example Fund"],
            "Current Value": [100000.0],
        }
    )

    backtest_history = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2026-01-31", "2026-02-28"]
            ),
            "Value": [95000.0, 100000.0],
        }
    )

    cash_flow_history = pd.DataFrame(
        {
            "Date": [
                date(2025, 1, 10),
                date(2025, 6, 15),
            ],
            "Amount": [
                -80000.0,
                -5000.0,
            ],
        }
    )

    backtest_service = Mock()
    backtest_service.load_default_backtest.return_value = (
        backtest_history
    )

    benchmark_service = Mock()
    benchmark_service.align_default_history.return_value = (
        pd.DataFrame(
            columns=[
                "Date",
                "Portfolio Return",
                "Benchmark Return",
            ]
        )
    )

    transaction_service = Mock()
    transaction_service.get_cash_flow_history.return_value = (
        cash_flow_history
    )

    advanced_service = Mock()
    expected_result = Mock()
    advanced_service.calculate.return_value = expected_result

    monkeypatch.setattr(
        analytics_view,
        "PortfolioBacktestService",
        lambda: backtest_service,
    )
    monkeypatch.setattr(
        analytics_view,
        "BenchmarkHistoryService",
        lambda: benchmark_service,
    )
    monkeypatch.setattr(
        analytics_view,
        "TransactionService",
        lambda: transaction_service,
        raising=False,
    )
    monkeypatch.setattr(
        analytics_view,
        "AdvancedAnalyticsService",
        lambda **kwargs: advanced_service,
    )

    result = analytics_view._calculate_advanced_analytics(
        portfolio
    )

    transaction_service.get_cash_flow_history.assert_called_once_with(
        portfolio_id=1,
    )

    service_input = advanced_service.calculate.call_args.args[0]

    assert service_input.cash_flow_history is cash_flow_history
    assert result is expected_result