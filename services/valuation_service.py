import pandas as pd


class ValuationService:
    """
    Calculates portfolio valuation using
    portfolio holdings and latest NAV.
    """

    def calculate(self, portfolio_df, nav_df):

        # Copy to avoid modifying original dataframe
        portfolio = portfolio_df.copy()

        nav = nav_df.copy()

        # Convert Scheme Code to string for merge
        portfolio["Scheme Code"] = portfolio["Scheme Code"].astype(str)
        nav["Scheme Code"] = nav["Scheme Code"].astype(str)

        # Merge latest NAV
        portfolio = portfolio.merge(
            nav[["Scheme Code", "NAV"]],
            on="Scheme Code",
            how="left"
        )

        portfolio.rename(
            columns={"NAV": "Latest NAV"},
            inplace=True
        )

        # Convert numeric columns
        portfolio["Latest NAV"] = pd.to_numeric(
            portfolio["Latest NAV"],
            errors="coerce"
        )

        portfolio["Units"] = pd.to_numeric(
            portfolio["Units"],
            errors="coerce"
        )

        portfolio["Avg NAV"] = pd.to_numeric(
            portfolio["Avg NAV"],
            errors="coerce"
        )

        # Portfolio calculations
        portfolio["Investment"] = (
            portfolio["Units"] * portfolio["Avg NAV"]
        )

        portfolio["Current Value"] = (
            portfolio["Units"] * portfolio["Latest NAV"]
        )

        portfolio["Profit/Loss"] = (
            portfolio["Current Value"] -
            portfolio["Investment"]
        )

        portfolio["Return %"] = (
            portfolio["Profit/Loss"] /
            portfolio["Investment"]
        ) * 100

        # Health Status
        portfolio["Status"] = portfolio["Return %"].apply(
            lambda x: (
                "OK"
                if x >= 0
                else "Warning"
            )
        )

        return portfolio