"""Portfolio risk analytics application service."""

from __future__ import annotations

import math
from collections.abc import Iterable
from statistics import covariance, mean, stdev, variance

from models.portfolio_risk_metrics import PortfolioRiskMetrics


class PortfolioRiskService:
    """Calculate portfolio risk metrics from periodic returns."""

    def calculate(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float] | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> PortfolioRiskMetrics:
        """
        Calculate aggregate portfolio risk metrics.

        Volatility is returned as a percentage.

        Sharpe ratio, Sortino ratio, Treynor ratio, beta, tracking
        error, and Information Ratio are returned as floating-point
        values.

        Maximum drawdown is returned as a negative decimal. For example,
        a 20% drawdown is represented as -0.20.
        """

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = (
            self._normalize_returns(
                benchmark_returns,
            )
            if benchmark_returns is not None
            else None
        )

        volatility = self.calculate_annualized_volatility(
            periodic_returns=normalized_portfolio_returns,
            periods_per_year=periods_per_year,
        )

        sharpe_ratio = self.calculate_sharpe_ratio(
            periodic_returns=normalized_portfolio_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )

        sortino_ratio = self.calculate_sortino_ratio(
            periodic_returns=normalized_portfolio_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )

        maximum_drawdown = self.calculate_maximum_drawdown(
            periodic_returns=normalized_portfolio_returns,
        )

        calmar_ratio = self.calculate_calmar_ratio(
            periodic_returns=normalized_portfolio_returns,
            periods_per_year=periods_per_year,
        )

        omega_ratio = self.calculate_omega_ratio(
            periodic_returns=normalized_portfolio_returns,
        )

        value_at_risk = self.calculate_value_at_risk(
            periodic_returns=normalized_portfolio_returns,
        )

        conditional_value_at_risk = (
            self.calculate_conditional_value_at_risk(
                periodic_returns=normalized_portfolio_returns,
            )
        )

        if normalized_benchmark_returns is not None:
            beta = self.calculate_beta(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
            )

            treynor_ratio = self.calculate_treynor_ratio(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
            )

            tracking_error = self.calculate_tracking_error(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                periods_per_year=periods_per_year,
            )

            information_ratio = self.calculate_information_ratio(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                periods_per_year=periods_per_year,
            )

            jensens_alpha = self.calculate_jensens_alpha(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
            )

            upside_capture_ratio = self.calculate_upside_capture_ratio(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                periods_per_year=periods_per_year,
            )

            downside_capture_ratio = self.calculate_downside_capture_ratio(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
                periods_per_year=periods_per_year,
            )
        else:
            beta = 0.0
            treynor_ratio = 0.0
            tracking_error = 0.0
            information_ratio = 0.0
            jensens_alpha = 0.0
            upside_capture_ratio = 0.0
            downside_capture_ratio = 0.0

        return PortfolioRiskMetrics(
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            treynor_ratio=treynor_ratio,
            tracking_error=tracking_error,
            information_ratio=information_ratio,
            jensens_alpha=jensens_alpha,
            calmar_ratio=calmar_ratio,
            omega_ratio=omega_ratio,
            value_at_risk=value_at_risk,
            conditional_value_at_risk=conditional_value_at_risk,
            upside_capture_ratio=upside_capture_ratio,
            downside_capture_ratio=downside_capture_ratio,
            max_drawdown=maximum_drawdown,
            beta=beta,
        )

    def calculate_rolling_risk_metrics(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float] | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
        window_size: int = 20,
    ) -> tuple[PortfolioRiskMetrics, ...]:
        """Calculate aggregate risk metrics for each rolling window."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero"
            )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = (
            self._normalize_returns(
                benchmark_returns,
            )
            if benchmark_returns is not None
            else None
        )

        if normalized_benchmark_returns is not None:
            self._validate_matching_return_lengths(
                portfolio_returns=normalized_portfolio_returns,
                benchmark_returns=normalized_benchmark_returns,
            )

        if len(normalized_portfolio_returns) < window_size:
            return ()

        rolling_metrics: list[PortfolioRiskMetrics] = []

        for window_end in range(
            window_size,
            len(normalized_portfolio_returns) + 1,
        ):
            window_start = (
                window_end
                - window_size
            )

            portfolio_window = normalized_portfolio_returns[
                window_start:window_end
            ]

            benchmark_window = (
                normalized_benchmark_returns[
                    window_start:window_end
                ]
                if normalized_benchmark_returns is not None
                else None
            )

            rolling_metrics.append(
                self.calculate(
                    portfolio_returns=portfolio_window,
                    benchmark_returns=benchmark_window,
                    risk_free_rate=risk_free_rate,
                    periods_per_year=periods_per_year,
                )
            )

        return tuple(
            rolling_metrics,
        )

    def calculate_annualized_volatility(
        self,
        *,
        periodic_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate annualized volatility as a percentage."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if len(normalized_returns) < 2:
            return 0.0

        periodic_volatility = stdev(
            normalized_returns,
        )

        annualized_volatility = (
            periodic_volatility
            * math.sqrt(periods_per_year)
            * 100.0
        )

        if not math.isfinite(
            annualized_volatility,
        ):
            return 0.0

        return float(
            annualized_volatility,
        )

    def calculate_sharpe_ratio(
        self,
        *,
        periodic_returns: Iterable[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate the annualized Sharpe ratio."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if len(normalized_returns) < 2:
            return 0.0

        periodic_volatility = stdev(
            normalized_returns,
        )

        if math.isclose(
            periodic_volatility,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        periodic_risk_free_rate = (
            float(risk_free_rate)
            / periods_per_year
        )

        average_excess_return = (
            mean(normalized_returns)
            - periodic_risk_free_rate
        )

        sharpe_ratio = (
            average_excess_return
            / periodic_volatility
            * math.sqrt(periods_per_year)
        )

        if not math.isfinite(
            sharpe_ratio,
        ):
            return 0.0

        return float(
            sharpe_ratio,
        )

    def calculate_sortino_ratio(
        self,
        *,
        periodic_returns: Iterable[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate the annualized Sortino ratio."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if len(normalized_returns) < 2:
            return 0.0

        periodic_risk_free_rate = (
            float(risk_free_rate)
            / periods_per_year
        )

        excess_returns = [
            periodic_return - periodic_risk_free_rate
            for periodic_return in normalized_returns
        ]

        downside_returns = [
            min(
                excess_return,
                0.0,
            )
            for excess_return in excess_returns
        ]

        downside_variance = mean(
            downside_return**2
            for downside_return in downside_returns
        )

        downside_deviation = math.sqrt(
            downside_variance,
        )

        if math.isclose(
            downside_deviation,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        average_excess_return = mean(
            excess_returns,
        )

        sortino_ratio = (
            average_excess_return
            / downside_deviation
            * math.sqrt(periods_per_year)
        )

        if not math.isfinite(
            sortino_ratio,
        ):
            return 0.0

        return float(
            sortino_ratio,
        )

    def calculate_treynor_ratio(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate the annualized Treynor ratio."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if len(normalized_portfolio_returns) < 2:
            return 0.0

        beta = self.calculate_beta(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if math.isclose(
            beta,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        periodic_risk_free_rate = (
            float(risk_free_rate)
            / periods_per_year
        )

        average_excess_return = (
            mean(normalized_portfolio_returns)
            - periodic_risk_free_rate
        )

        annualized_excess_return = (
            average_excess_return
            * periods_per_year
        )

        treynor_ratio = (
            annualized_excess_return
            / beta
        )

        if not math.isfinite(
            treynor_ratio,
        ):
            return 0.0

        return float(
            treynor_ratio,
        )

    def calculate_tracking_error(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """
        Calculate annualized tracking error.

        Tracking error is the annualized standard deviation of active
        returns. Active return is the portfolio return minus the
        benchmark return.
        """

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if len(normalized_portfolio_returns) < 2:
            return 0.0

        active_returns = [
            portfolio_return - benchmark_return
            for portfolio_return, benchmark_return in zip(
                normalized_portfolio_returns,
                normalized_benchmark_returns,
                strict=True,
            )
        ]

        periodic_tracking_error = stdev(
            active_returns,
        )

        if math.isclose(
            periodic_tracking_error,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        annualized_tracking_error = (
            periodic_tracking_error
            * math.sqrt(periods_per_year)
        )

        if not math.isfinite(
            annualized_tracking_error,
        ):
            return 0.0

        return float(
            annualized_tracking_error,
        )

    def calculate_information_ratio(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """
        Calculate the annualized Information Ratio.

        Information Ratio is annualized active return divided by
        annualized tracking error.
        """

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if len(normalized_portfolio_returns) < 2:
            return 0.0

        tracking_error = self.calculate_tracking_error(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
            periods_per_year=periods_per_year,
        )

        if math.isclose(
            tracking_error,
            0.0,
            abs_tol=1e-12,
        ):
            return 0.0

        active_returns = [
            portfolio_return - benchmark_return
            for portfolio_return, benchmark_return in zip(
                normalized_portfolio_returns,
                normalized_benchmark_returns,
                strict=True,
            )
        ]

        annualized_active_return = (
            mean(active_returns)
            * periods_per_year
        )

        information_ratio = (
            annualized_active_return
            / tracking_error
        )

        if not math.isfinite(
            information_ratio,
        ):
            return 0.0

        return float(
            information_ratio,
        )

    def calculate_jensens_alpha(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate annualized Jensen's Alpha."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if len(normalized_portfolio_returns) < 2:
            return 0.0

        beta = self.calculate_beta(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        periodic_risk_free_rate = (
            float(risk_free_rate)
            / periods_per_year
        )

        periodic_alpha = (
            mean(normalized_portfolio_returns)
            - periodic_risk_free_rate
            - beta
            * (
                mean(normalized_benchmark_returns)
                - periodic_risk_free_rate
            )
        )

        annualized_alpha = (
            periodic_alpha
            * periods_per_year
        )

        if not math.isfinite(
            annualized_alpha,
        ):
            return 0.0

        return float(
            annualized_alpha,
        )

    def calculate_calmar_ratio(
        self,
        *,
        periodic_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate the Calmar ratio using annualized compounded return."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if not normalized_returns:
            return 0.0

        maximum_drawdown = self.calculate_maximum_drawdown(
            periodic_returns=normalized_returns,
        )

        if math.isclose(
            maximum_drawdown,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        cumulative_return_factor = math.prod(
            1.0 + periodic_return
            for periodic_return in normalized_returns
        )

        annualized_return = (
            cumulative_return_factor
            ** (
                periods_per_year
                / len(normalized_returns)
            )
            - 1.0
        )

        calmar_ratio = (
            annualized_return
            / abs(maximum_drawdown)
        )

        if not math.isfinite(
            calmar_ratio,
        ):
            return 0.0

        return float(
            calmar_ratio,
        )

    def calculate_omega_ratio(
        self,
        *,
        periodic_returns: Iterable[float],
        threshold_return: float = 0.0,
    ) -> float:
        """Calculate gains relative to losses above a return threshold."""

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if not normalized_returns:
            return 0.0

        normalized_threshold = float(
            threshold_return,
        )

        total_gain = sum(
            max(
                periodic_return - normalized_threshold,
                0.0,
            )
            for periodic_return in normalized_returns
        )

        total_loss = sum(
            max(
                normalized_threshold - periodic_return,
                0.0,
            )
            for periodic_return in normalized_returns
        )

        if math.isclose(
            total_loss,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        omega_ratio = (
            total_gain
            / total_loss
        )

        if not math.isfinite(
            omega_ratio,
        ):
            return 0.0

        return float(
            omega_ratio,
        )

    def calculate_value_at_risk(
        self,
        *,
        periodic_returns: Iterable[float],
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate historical Value at Risk as a positive loss value."""

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if not normalized_returns:
            return 0.0

        normalized_confidence_level = float(
            confidence_level,
        )

        if not 0.0 < normalized_confidence_level < 1.0:
            raise ValueError(
                "confidence_level must be greater than zero "
                "and less than one"
            )

        sorted_returns = sorted(
            normalized_returns,
        )

        lower_tail_count = max(
            1,
            math.ceil(
                (1.0 - normalized_confidence_level)
                * len(sorted_returns)
            ),
        )

        value_at_risk_return = sorted_returns[
            lower_tail_count - 1
        ]

        value_at_risk = max(
            -value_at_risk_return,
            0.0,
        )

        if not math.isfinite(
            value_at_risk,
        ):
            return 0.0

        return float(
            value_at_risk,
        )

    def calculate_conditional_value_at_risk(
        self,
        *,
        periodic_returns: Iterable[float],
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate historical CVaR as a positive average tail loss."""

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if not normalized_returns:
            return 0.0

        normalized_confidence_level = float(
            confidence_level,
        )

        if not 0.0 < normalized_confidence_level < 1.0:
            raise ValueError(
                "confidence_level must be greater than zero "
                "and less than one"
            )

        sorted_returns = sorted(
            normalized_returns,
        )

        lower_tail_count = max(
            1,
            math.ceil(
                (1.0 - normalized_confidence_level)
                * len(sorted_returns)
            ),
        )

        lower_tail_returns = sorted_returns[
            :lower_tail_count
        ]

        conditional_value_at_risk = max(
            -mean(lower_tail_returns),
            0.0,
        )

        if not math.isfinite(
            conditional_value_at_risk,
        ):
            return 0.0

        return float(
            conditional_value_at_risk,
        )

    def calculate_upside_capture_ratio(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate capture during positive benchmark-return periods."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        upside_periods = [
            (portfolio_return, benchmark_return)
            for portfolio_return, benchmark_return in zip(
                normalized_portfolio_returns,
                normalized_benchmark_returns,
                strict=True,
            )
            if benchmark_return > 0.0
        ]

        if not upside_periods:
            return 0.0

        annualization_exponent = (
            periods_per_year
            / len(upside_periods)
        )

        portfolio_upside_return = (
            math.prod(
                1.0 + portfolio_return
                for portfolio_return, _ in upside_periods
            )
            ** annualization_exponent
            - 1.0
        )

        benchmark_upside_return = (
            math.prod(
                1.0 + benchmark_return
                for _, benchmark_return in upside_periods
            )
            ** annualization_exponent
            - 1.0
        )

        if math.isclose(
            benchmark_upside_return,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        upside_capture_ratio = (
            portfolio_upside_return
            / benchmark_upside_return
            * 100.0
        )

        if not math.isfinite(
            upside_capture_ratio,
        ):
            return 0.0

        return float(
            upside_capture_ratio,
        )

    def calculate_downside_capture_ratio(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate capture during negative benchmark-return periods."""

        self._validate_periods_per_year(
            periods_per_year,
        )

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        downside_periods = [
            (portfolio_return, benchmark_return)
            for portfolio_return, benchmark_return in zip(
                normalized_portfolio_returns,
                normalized_benchmark_returns,
                strict=True,
            )
            if benchmark_return < 0.0
        ]

        if not downside_periods:
            return 0.0

        annualization_exponent = (
            periods_per_year
            / len(downside_periods)
        )

        portfolio_downside_return = (
            math.prod(
                1.0 + portfolio_return
                for portfolio_return, _ in downside_periods
            )
            ** annualization_exponent
            - 1.0
        )

        benchmark_downside_return = (
            math.prod(
                1.0 + benchmark_return
                for _, benchmark_return in downside_periods
            )
            ** annualization_exponent
            - 1.0
        )

        if math.isclose(
            benchmark_downside_return,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        downside_capture_ratio = (
            portfolio_downside_return
            / benchmark_downside_return
            * 100.0
        )

        if not math.isfinite(
            downside_capture_ratio,
        ):
            return 0.0

        return float(
            downside_capture_ratio,
        )

    def calculate_maximum_drawdown(
        self,
        *,
        periodic_returns: Iterable[float],
    ) -> float:
        """Calculate maximum peak-to-trough portfolio drawdown."""

        normalized_returns = self._normalize_returns(
            periodic_returns,
        )

        if not normalized_returns:
            return 0.0

        cumulative_value = 1.0
        peak_value = 1.0
        maximum_drawdown = 0.0

        for periodic_return in normalized_returns:
            cumulative_value *= (
                1.0
                + periodic_return
            )

            if cumulative_value > peak_value:
                peak_value = cumulative_value

            current_drawdown = (
                cumulative_value - peak_value
            ) / peak_value

            if current_drawdown < maximum_drawdown:
                maximum_drawdown = current_drawdown

        if not math.isfinite(
            maximum_drawdown,
        ):
            return 0.0

        return float(
            maximum_drawdown,
        )

    def calculate_beta(
        self,
        *,
        portfolio_returns: Iterable[float],
        benchmark_returns: Iterable[float],
    ) -> float:
        """Calculate portfolio beta relative to benchmark returns."""

        normalized_portfolio_returns = self._normalize_returns(
            portfolio_returns,
        )

        normalized_benchmark_returns = self._normalize_returns(
            benchmark_returns,
        )

        self._validate_matching_return_lengths(
            portfolio_returns=normalized_portfolio_returns,
            benchmark_returns=normalized_benchmark_returns,
        )

        if len(normalized_portfolio_returns) < 2:
            return 0.0

        benchmark_variance = variance(
            normalized_benchmark_returns,
        )

        if math.isclose(
            benchmark_variance,
            0.0,
            abs_tol=1e-15,
        ):
            return 0.0

        portfolio_benchmark_covariance = covariance(
            normalized_portfolio_returns,
            normalized_benchmark_returns,
        )

        beta = (
            portfolio_benchmark_covariance
            / benchmark_variance
        )

        if not math.isfinite(
            beta,
        ):
            return 0.0

        return float(
            beta,
        )

    @staticmethod
    def _normalize_returns(
        periodic_returns: Iterable[float],
    ) -> list[float]:
        """Convert a return iterable into a reusable list of floats."""

        return [
            float(periodic_return)
            for periodic_return in periodic_returns
        ]

    @staticmethod
    def _validate_periods_per_year(
        periods_per_year: int,
    ) -> None:
        """Validate the annualization period."""

        if periods_per_year <= 0:
            raise ValueError(
                "periods_per_year must be greater than zero"
            )

    @staticmethod
    def _validate_matching_return_lengths(
        *,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> None:
        """Ensure portfolio and benchmark return series have equal lengths."""

        if len(portfolio_returns) != len(
            benchmark_returns
        ):
            raise ValueError(
                "portfolio_returns and benchmark_returns "
                "must have the same length"
            )