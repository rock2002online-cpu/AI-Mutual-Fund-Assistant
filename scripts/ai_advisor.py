import pandas as pd


def generate_advice(df):

    advice = []

    # -----------------------------
    # Portfolio Size
    # -----------------------------
    if len(df) < 4:
        advice.append(
            "Portfolio has only a few funds. Consider diversifying."
        )
    else:
        advice.append(
            "Portfolio diversification looks good."
        )

    # -----------------------------
    # Concentration Risk
    # -----------------------------
    total = df["Current Value"].sum()

    largest = df["Current Value"].max()

    allocation = (largest / total) * 100

    if allocation > 40:
        advice.append(
            f"Largest holding is {allocation:.1f}% of portfolio. Consider reducing concentration."
        )
    else:
        advice.append(
            "No concentration risk detected."
        )

    # -----------------------------
    # Average Return
    # -----------------------------
    avg_return = df["Return %"].mean()

    if avg_return > 15:
        advice.append(
            "Excellent portfolio performance."
        )

    elif avg_return > 10:
        advice.append(
            "Portfolio is performing well."
        )

    elif avg_return > 5:
        advice.append(
            "Moderate performance."
        )

    else:
        advice.append(
            "Review underperforming investments."
        )

    # -----------------------------
    # Flagged Funds
    # -----------------------------
    bad = df[df["Status"] != "OK"]

    if len(bad):

        advice.append(
            f"{len(bad)} fund(s) require attention."
        )

    else:

        advice.append(
            "All portfolio data looks healthy."
        )

    return advice