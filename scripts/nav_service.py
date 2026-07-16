import requests
import pandas as pd
from io import StringIO

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def download_nav_data():
    """Download and clean the AMFI NAV data."""

    response = requests.get(AMFI_URL)
    response.raise_for_status()

    df = pd.read_csv(
        StringIO(response.text),
        sep=";",
        on_bad_lines="skip"
    )

    # Clean column names
    df.columns = df.columns.str.strip()

    # Keep only valid scheme rows
    df = df[pd.to_numeric(df["Scheme Code"], errors="coerce").notna()]

    # Convert data types
    df["Scheme Code"] = df["Scheme Code"].astype(int)
    df["Net Asset Value"] = pd.to_numeric(df["Net Asset Value"], errors="coerce")

    return df.reset_index(drop=True)


def search_fund(df, keyword):
    """Search mutual funds by name."""

    result = df[
        df["Scheme Name"].str.contains(
            keyword,
            case=False,
            na=False
        )
    ]

    return result[
        ["Scheme Code", "Scheme Name", "Net Asset Value", "Date"]
    ]


if __name__ == "__main__":

    nav_df = download_nav_data()

    keyword = input("Enter fund name: ")

    result = search_fund(nav_df, keyword)

    if result.empty:
        print("\nNo matching fund found.")
    else:
        print("\nMatching Funds:\n")
        print(result.to_string(index=False))