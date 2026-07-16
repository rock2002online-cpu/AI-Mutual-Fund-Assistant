from __future__ import annotations

from typing import Any

import pandas as pd


class PortfolioInsights:
    """
    Portfolio analysis engine.

    Calculates portfolio metrics, health indicators,
    diversification, risk and portfolio recommendations.
    """

    def __init__(self, df: pd.DataFrame | None):
        if df is None:
            self.df = pd.DataFrame()
        else:
            self.df = df.copy()

        self._prepare_numeric_columns()

    # ========================================================
    # DATA PREPARATION
    # ========================================================

    def _prepare_numeric_columns(self) -> None:
        """
        Convert supported portfolio columns to numeric values.

        Invalid values are converted to zero.
        """

        numeric_columns = [
            "Investment",
            "Invested Amount",
            "Current Value",
            "Profit/Loss",
            "Return %",
            "P/L %",
        ]

        for column in numeric_columns:
            if column in self.df.columns:
                self.df[column] = pd.to_numeric(
                    self.df[column],
                    errors="coerce",
                ).fillna(0.0)

    # ========================================================
    # BASIC PORTFOLIO METRICS
    # ========================================================

    def portfolio_value(self) -> float:
        """
        Return total current portfolio value.
        """

        if "Current Value" not in self.df.columns:
            return 0.0

        return float(self.df["Current Value"].sum())

    def invested_value(self) -> float:
        """
        Return total invested amount.
        """

        if "Investment" in self.df.columns:
            return float(self.df["Investment"].sum())

        if "Invested Amount" in self.df.columns:
            return float(self.df["Invested Amount"].sum())

        return 0.0

    def gain_loss(self) -> float:
        """
        Return total portfolio profit or loss.
        """

        if "Profit/Loss" in self.df.columns:
            return float(self.df["Profit/Loss"].sum())

        return self.portfolio_value() - self.invested_value()

    def gain_percent(self) -> float:
        """
        Return overall portfolio return percentage.
        """

        invested = self.invested_value()

        if invested <= 0:
            return 0.0

        return float(
            (self.gain_loss() / invested) * 100
        )

    # ========================================================
    # HOLDING ANALYSIS
    # ========================================================

    def top_holding(self) -> pd.Series | None:
        """
        Return the fund with the largest current value.
        """

        if (
            self.df.empty
            or "Current Value" not in self.df.columns
        ):
            return None

        valid_df = self.df[
            self.df["Current Value"].notna()
        ]

        if valid_df.empty:
            return None

        index = valid_df["Current Value"].idxmax()

        return valid_df.loc[index]

    def worst_holding(self) -> pd.Series | None:
        """
        Return the weakest-performing fund.

        Priority:
        1. Return %
        2. P/L %
        3. Profit/Loss
        """

        if self.df.empty:
            return None

        performance_columns = [
            "Return %",
            "P/L %",
            "Profit/Loss",
        ]

        for column in performance_columns:
            if column not in self.df.columns:
                continue

            valid_df = self.df[
                self.df[column].notna()
            ]

            if valid_df.empty:
                continue

            index = valid_df[column].idxmin()

            return valid_df.loc[index]

        return None

    def concentration(self) -> float:
        """
        Return the percentage represented by the largest holding.
        """

        if (
            self.df.empty
            or "Current Value" not in self.df.columns
        ):
            return 0.0

        total_value = self.portfolio_value()

        if total_value <= 0:
            return 0.0

        largest_value = float(
            self.df["Current Value"].max()
        )

        concentration_value = (
            largest_value / total_value
        ) * 100

        return float(concentration_value)

    # ========================================================
    # PORTFOLIO SCORING
    # ========================================================

    def health_score(self) -> float:
        """
        Calculate an overall portfolio health score from 0 to 100.
        """

        score = 50.0
        gain = self.gain_percent()
        concentration = self.concentration()

        if gain >= 20:
            score += 20
        elif gain >= 10:
            score += 15
        elif gain >= 0:
            score += 10
        else:
            score -= 10

        if concentration > 50:
            score -= 20
        elif concentration > 40:
            score -= 10
        elif concentration > 30:
            score -= 5
        else:
            score += 10

        return float(
            max(0.0, min(100.0, score))
        )

    def risk_level(self) -> str:
        """
        Determine the portfolio risk level.
        """

        concentration = self.concentration()
        gain = self.gain_percent()

        if concentration >= 50:
            return "🔴 High"

        if concentration >= 35:
            return "🟡 Moderate"

        if gain < 0:
            return "🟡 Moderate"

        return "🟢 Low"

    def diversification_score(self) -> float:
        """
        Calculate a diversification score from 0 to 100.

        A higher concentration produces a lower score.
        """

        concentration = self.concentration()

        score = 100.0 - concentration

        return round(
            max(0.0, min(100.0, score)),
            1,
        )

    # ========================================================
    # TEXT INSIGHTS
    # ========================================================

    @staticmethod
    def _fund_name(
        holding: pd.Series | None,
    ) -> str:
        """
        Safely extract a fund name from a holding row.
        """

        if holding is None:
            return "N/A"

        if "Fund" not in holding.index:
            return "N/A"

        fund_name = str(
            holding.get("Fund", "N/A")
        ).strip()

        return fund_name or "N/A"

    def executive_summary(self) -> str:
        """
        Generate an executive portfolio summary.
        """

        return_percentage = self.gain_percent()
        health = self.health_score()
        risk = self.risk_level()
        concentration = self.concentration()

        summary_text = (
            f"Your portfolio has generated an overall return of "
            f"{return_percentage:.2f}% with a Portfolio Health "
            f"Score of {health:.0f}/100. The current portfolio "
            f"risk is assessed as {risk}. The largest holding "
            f"represents {concentration:.2f}% of the portfolio. "
        )

        if health >= 75:
            summary_text += (
                "Overall, the portfolio appears healthy. "
                "Periodic rebalancing can help protect gains "
                "and maintain diversification."
            )

        elif health >= 50:
            summary_text += (
                "Overall, the portfolio is performing well, "
                "although periodic rebalancing may improve "
                "long-term diversification."
            )

        else:
            summary_text += (
                "The portfolio may benefit from closer review, "
                "improved diversification and disciplined "
                "rebalancing."
            )

        return summary_text

    def recommendations(self) -> list[dict[str, str]]:
        """
        Generate portfolio recommendations.
        """

        recommendations: list[dict[str, str]] = []

        gain = self.gain_percent()
        concentration = self.concentration()
        diversification = self.diversification_score()

        if gain >= 20:
            recommendations.append(
                {
                    "type": "success",
                    "message": (
                        "Your portfolio has delivered excellent "
                        "returns. Consider periodic rebalancing "
                        "to protect gains."
                    ),
                }
            )

        elif gain >= 0:
            recommendations.append(
                {
                    "type": "info",
                    "message": (
                        "Your portfolio is generating positive "
                        "returns. Continue monitoring individual "
                        "fund performance."
                    ),
                }
            )

        else:
            recommendations.append(
                {
                    "type": "warning",
                    "message": (
                        "Your portfolio currently has a negative "
                        "return. Review underperforming holdings "
                        "before making changes."
                    ),
                }
            )

        if concentration >= 50:
            recommendations.append(
                {
                    "type": "error",
                    "message": (
                        "High concentration risk detected. The "
                        "largest holding represents at least half "
                        "of the portfolio."
                    ),
                }
            )

        elif concentration >= 35:
            recommendations.append(
                {
                    "type": "warning",
                    "message": (
                        "Moderate concentration risk detected. "
                        "Diversification may improve stability."
                    ),
                }
            )

        else:
            recommendations.append(
                {
                    "type": "success",
                    "message": (
                        "Portfolio concentration appears reasonably "
                        "balanced."
                    ),
                }
            )

        if diversification < 60:
            recommendations.append(
                {
                    "type": "warning",
                    "message": (
                        "The diversification score is below the "
                        "preferred level. Consider spreading "
                        "investments across more suitable categories."
                    ),
                }
            )

        else:
            recommendations.append(
                {
                    "type": "info",
                    "message": (
                        "Diversification is acceptable but should "
                        "be reviewed periodically as fund values "
                        "change."
                    ),
                }
            )

        return recommendations

    # ========================================================
    # DASHBOARD OUTPUT
    # ========================================================

    def portfolio_insights(self) -> dict[str, Any]:
        """
        Return portfolio values and important holdings.
        """

        top = self.top_holding()
        worst = self.worst_holding()

        return {
            "investment": self.invested_value(),
            "current_value": self.portfolio_value(),
            "profit": self.gain_loss(),
            "best_fund": self._fund_name(top),
            "worst_fund": self._fund_name(worst),
        }

    def summary(self) -> dict[str, Any]:
        """
        Return all calculated portfolio information.
        """

        return {
            "portfolio_value": self.portfolio_value(),
            "invested_value": self.invested_value(),
            "gain_loss": self.gain_loss(),
            "gain_percent": self.gain_percent(),
            "health_score": self.health_score(),
            "risk_level": self.risk_level(),
            "diversification_score": (
                self.diversification_score()
            ),
            "concentration": self.concentration(),
            "top_holding": self.top_holding(),
            "worst_holding": self.worst_holding(),
            "executive_summary": (
                self.executive_summary()
            ),
            "recommendations": self.recommendations(),
        }