from services.portfolio_loader import PortfolioLoader
from services.nav_service import NAVService
from services.valuation_service import ValuationService


class PortfolioService:
    """
    Coordinates portfolio loading, NAV download,
    and portfolio valuation.
    """

    def __init__(self):

        self.loader = PortfolioLoader()
        self.nav_service = NAVService()
        self.valuation = ValuationService()

    def get_portfolio(self):

        portfolio = self.loader.load()

        nav = self.nav_service.get_nav()

        result = self.valuation.calculate(
            portfolio,
            nav
        )

        return result