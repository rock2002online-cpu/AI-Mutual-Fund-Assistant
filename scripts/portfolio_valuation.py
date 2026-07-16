import sys
from pathlib import Path
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



from nav_service import (
    download_nav_data,
)
from update_portfolio_history import (
    update_portfolio_history,
)

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Paths
portfolio_file = PROJECT_ROOT / "data" / "portfolio.xlsx"
reports_folder = PROJECT_ROOT / "reports"

# Read portfolio
portfolio = pd.read_excel(portfolio_file)

# Download latest NAV data
nav_data = download_nav_data()

# Merge portfolio with live NAV data
merged = portfolio.merge(
    nav_data[["Scheme Code", "Net Asset Value"]],
    on="Scheme Code",
    how="left"
)

# Rename column
merged.rename(columns={"Net Asset Value": "Latest NAV"}, inplace=True)

# Calculations
merged["Investment"] = merged["Units"] * merged["Avg NAV"]
merged["Current Value"] = merged["Units"] * merged["Latest NAV"]
merged["Profit/Loss"] = merged["Current Value"] - merged["Investment"]
merged["Return %"] = (
    merged["Profit/Loss"] / merged["Investment"]
) * 100

# Validation
merged["Status"] = "OK"

merged.loc[merged["Return %"] > 200, "Status"] = "CHECK SCHEME CODE"
merged.loc[merged["Return %"] < -90, "Status"] = "CHECK DATA"

print("\n===== PORTFOLIO VALUATION =====\n")

print(
    merged[
        [
            "Fund",
            "Units",
            "Avg NAV",
            "Latest NAV",
            "Investment",
            "Current Value",
            "Profit/Loss",
            "Return %",
            "Status"
        ]
    ].round(2)
)

print("\n===============================")
print(f"Total Investment : {merged['Investment'].sum():,.2f}")
print(f"Current Value    : {merged['Current Value'].sum():,.2f}")
print(f"Total Profit     : {merged['Profit/Loss'].sum():,.2f}")
from pathlib import Path

# Create reports folder if it doesn't exist
reports_folder.mkdir(exist_ok=True)

# Output file
output_file = reports_folder / "Portfolio_Report.xlsx"

# Save report
merged.round(2).to_excel(output_file, index=False)

print("\n[OK] Report saved successfully!")
print(f"Location: {output_file.resolve()}")
try:
    update_portfolio_history()
except Exception as error:
    print(
        "Portfolio history update skipped:",
        error,
    )
else:
    print(
        "Portfolio history updated successfully."
    )