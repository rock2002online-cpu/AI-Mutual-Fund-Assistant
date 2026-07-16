from services.ai.insights import PortfolioInsights
from services.ai.recommendations import PortfolioRecommendations


class PortfolioAdvisor:
    """
    Main AI Portfolio Advisor.

    Combines portfolio insights, recommendations,
    and executive summary.
    """

    def __init__(self, df):
        self.df = df

    def executive_summary(self, summary):
        """
        Generate a professional portfolio summary.
        """

        health = summary["health_score"]
        returns = summary["gain_percent"]
        concentration = summary["concentration"]
        risk = summary["risk_level"]

        return (
            f"Your portfolio has generated an overall return of "
            f"{returns:.2f}% with a Portfolio Health Score of "
            f"{health:.0f}/100. "
            f"The current portfolio risk is assessed as "
            f"{risk}. "
            f"The largest holding represents "
            f"{concentration:.2f}% of the portfolio. "
            f"Overall, the portfolio is performing well, although "
            f"periodic portfolio rebalancing can further improve "
            f"long-term diversification."
        )

    def analyze(self):

        insights = PortfolioInsights(self.df).summary()

        recommendations = PortfolioRecommendations(
            self.df
        ).generate()

        summary = self.executive_summary(insights)

        return {
            "summary": insights,
            "insights": PortfolioInsights(self.df).portfolio_insights(),
            "recommendations": recommendations,
            "executive_summary": summary,
        }