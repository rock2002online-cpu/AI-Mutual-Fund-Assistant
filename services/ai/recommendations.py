from services.ai.insights import PortfolioInsights


class PortfolioRecommendations:
    """
    Generates rule-based portfolio recommendations.
    """

    def __init__(self, df):
        self.insights = PortfolioInsights(df)
        self.summary = self.insights.summary()

    def generate(self):
        recommendations = []

        gain = self.summary["gain_percent"]
        concentration = self.summary["concentration"]

        # Portfolio performance
        if gain >= 20:
            recommendations.append(
                "✅ Your portfolio has delivered excellent returns. Consider periodic rebalancing."
            )
        elif gain >= 10:
            recommendations.append(
                "📈 Your portfolio is performing well. Continue your SIPs and review allocations periodically."
            )
        elif gain >= 0:
            recommendations.append(
                "🙂 Your portfolio is in positive territory. Monitor your investments regularly."
            )
        else:
            recommendations.append(
                "⚠️ Your portfolio is currently showing a loss. Stay focused on your long-term investment strategy."
            )

        # Concentration risk
        if concentration > 40:
            recommendations.append(
                "⚠️ High concentration risk detected. One fund accounts for more than 40% of your portfolio."
            )
        elif concentration > 30:
            recommendations.append(
                "ℹ️ Moderate concentration risk detected. Diversification may improve stability."
            )
        else:
            recommendations.append(
                "✅ Your portfolio appears reasonably diversified."
            )

        # Top holding
        top = self.summary.get("top_holding")

        if top is not None:
            fund_name = top.get("Fund", "Unknown Fund")
            recommendations.append(
                f"🏆 Largest holding: {fund_name}"
            )

        # Weakest holding
        worst = self.summary.get("worst_holding")

        if worst is not None:
            fund_name = worst.get("Fund", "Unknown Fund")
            recommendations.append(
                f"🔍 Review this fund: {fund_name}"
            )

        return recommendations