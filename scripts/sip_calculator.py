import pandas as pd


def calculate_sip(monthly_investment, annual_return, years):

    r = annual_return / 12 / 100
    n = years * 12

    future_value = (
        monthly_investment
        * (((1 + r) ** n - 1) / r)
        * (1 + r)
    )

    total_investment = monthly_investment * n

    wealth = future_value - total_investment

    return {
        "Monthly SIP": monthly_investment,
        "Years": years,
        "Expected Return": annual_return,
        "Investment": total_investment,
        "Corpus": future_value,
        "Wealth": wealth
    }