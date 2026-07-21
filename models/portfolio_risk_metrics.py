"""Portfolio risk metrics model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class PortfolioRiskMetrics:
    """Aggregate portfolio risk metrics."""

    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    treynor_ratio: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    jensens_alpha: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    value_at_risk: float = 0.0
    conditional_value_at_risk: float = 0.0
    upside_capture_ratio: float = 0.0
    downside_capture_ratio: float = 0.0
    max_drawdown: float = 0.0
    beta: float = 0.0

    def __post_init__(self) -> None:
        """Normalize all metric values to floats."""

        object.__setattr__(
            self,
            "volatility",
            float(self.volatility),
        )
        object.__setattr__(
            self,
            "sharpe_ratio",
            float(self.sharpe_ratio),
        )
        object.__setattr__(
            self,
            "sortino_ratio",
            float(self.sortino_ratio),
        )
        object.__setattr__(
            self,
            "treynor_ratio",
            float(self.treynor_ratio),
        )
        object.__setattr__(
            self,
            "tracking_error",
            float(self.tracking_error),
        )
        object.__setattr__(
            self,
            "information_ratio",
            float(self.information_ratio),
        )
        object.__setattr__(
            self,
            "jensens_alpha",
            float(self.jensens_alpha),
        )
        object.__setattr__(
            self,
            "calmar_ratio",
            float(self.calmar_ratio),
        )
        object.__setattr__(
            self,
            "omega_ratio",
            float(self.omega_ratio),
        )
        object.__setattr__(
            self,
            "value_at_risk",
            float(self.value_at_risk),
        )
        object.__setattr__(
            self,
            "conditional_value_at_risk",
            float(self.conditional_value_at_risk),
        )
        object.__setattr__(
            self,
            "upside_capture_ratio",
            float(self.upside_capture_ratio),
        )
        object.__setattr__(
            self,
            "downside_capture_ratio",
            float(self.downside_capture_ratio),
        )
        object.__setattr__(
            self,
            "max_drawdown",
            float(self.max_drawdown),
        )
        object.__setattr__(
            self,
            "beta",
            float(self.beta),
        )