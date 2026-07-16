import pandas as pd

# Read the Excel file
portfolio = pd.read_excel("portfolio.xlsx")

print("=== MY PORTFOLIO ===")
print(portfolio)

# Calculate investment amount
portfolio["Investment"] = portfolio["Units"] * portfolio["Avg NAV"]

print("\n=== PORTFOLIO WITH INVESTMENT ===")
print(portfolio)

# Portfolio summary
total = portfolio["Investment"].sum()

print("\n===============================")
print(f"Total Investment = ₹{total:,.2f}")
print("===============================")