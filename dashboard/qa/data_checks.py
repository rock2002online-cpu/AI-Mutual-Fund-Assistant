import pandas as pd


REQUIRED_COLUMNS = [
    "Fund",
    "Investment",
    "Current Value",
    "Profit/Loss",
    "Status",
]


def validate_portfolio(df: pd.DataFrame):
    """
    Validate the portfolio DataFrame.

    Returns
    -------
    dict
        {
            "passed": int,
            "failed": int,
            "checks": [(name, status), ...]
        }
    """

    checks = []

    # -------------------------------------------------
    # Portfolio Loaded
    # -------------------------------------------------

    checks.append((
        "Portfolio Loaded",
        not df.empty
    ))

    # -------------------------------------------------
    # Required Columns
    # -------------------------------------------------

    for column in REQUIRED_COLUMNS:

        checks.append((
            f"Column: {column}",
            column in df.columns
        ))

    # -------------------------------------------------
    # Missing Values
    # -------------------------------------------------

    checks.append((
        "Missing Values",
        not df.isnull().any().any()
    ))

    # -------------------------------------------------
    # Duplicate Funds
    # -------------------------------------------------

    if "Fund" in df.columns:

        duplicate_count = df["Fund"].duplicated().sum()

        checks.append((
            "Duplicate Funds",
            duplicate_count == 0
        ))

    # -------------------------------------------------
    # Negative Investment
    # -------------------------------------------------

    if "Investment" in df.columns:

        checks.append((
            "Negative Investment",
            (df["Investment"] >= 0).all()
        ))

    # -------------------------------------------------
    # Current Value
    # -------------------------------------------------

    if "Current Value" in df.columns:

        checks.append((
            "Negative Current Value",
            (df["Current Value"] >= 0).all()
        ))

    passed = sum(status for _, status in checks)
    failed = len(checks) - passed

    return {
        "passed": passed,
        "failed": failed,
        "checks": checks
    }