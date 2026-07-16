from services.portfolio_loader import PortfolioLoader

loader = PortfolioLoader()

df = loader.load()

print("Portfolio loaded successfully!")
print()

print(df.head())

print()

print("Columns:")
print(df.columns.tolist())