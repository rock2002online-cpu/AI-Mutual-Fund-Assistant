from services.portfolio_loader import PortfolioLoader
from services.nav_service import NAVService
from services.valuation_service import ValuationService

loader = PortfolioLoader()
nav_service = NAVService()
valuation = ValuationService()

portfolio = loader.load()
nav = nav_service.download_nav()

result = valuation.calculate(
    portfolio,
    nav
)

print(result.head())

print()

print(result.columns.tolist())