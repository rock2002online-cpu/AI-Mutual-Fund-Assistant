from models.portfolio_risk_metrics import PortfolioRiskMetrics


def test_model_creation() -> None:
    metrics = PortfolioRiskMetrics(
        volatility=12.5,
        sharpe_ratio=1.45,
        max_drawdown=-18.3,
        beta=0.92,
    )

    assert metrics.volatility == 12.5
    assert metrics.sharpe_ratio == 1.45
    assert metrics.max_drawdown == -18.3
    assert metrics.beta == 0.92


def test_model_is_frozen() -> None:
    metrics = PortfolioRiskMetrics(
        volatility=1,
        sharpe_ratio=2,
        max_drawdown=3,
        beta=4,
    )

    import pytest

    with pytest.raises(AttributeError):
        metrics.beta = 2


def test_slots_enabled() -> None:
    metrics = PortfolioRiskMetrics(
        volatility=1,
        sharpe_ratio=2,
        max_drawdown=3,
        beta=4,
    )

    assert hasattr(metrics, "__slots__")

def test_portfolio_risk_metrics_defaults_sharpe_ratio_to_zero() -> None:
    """Sharpe ratio should remain backward compatible."""

    metrics = PortfolioRiskMetrics(
        volatility=12.5,
    )

    assert metrics.sharpe_ratio == 0.0


def test_portfolio_risk_metrics_accepts_sharpe_ratio() -> None:
    """The model should store a supplied Sharpe ratio."""

    metrics = PortfolioRiskMetrics(
        volatility=12.5,
        sharpe_ratio=1.45,
    )

    assert metrics.sharpe_ratio == 1.45


def test_portfolio_risk_metrics_converts_sharpe_ratio_to_float() -> None:
    """Sharpe ratio should be normalized to float."""

    metrics = PortfolioRiskMetrics(
        volatility=12.5,
        sharpe_ratio=2,
    )

    assert metrics.sharpe_ratio == 2.0
    assert isinstance(metrics.sharpe_ratio, float)