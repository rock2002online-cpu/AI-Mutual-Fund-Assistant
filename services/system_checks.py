from services.portfolio_loader import PortfolioLoader
from services.nav_service import NAVService
from services.valuation_service import ValuationService


class SystemChecks:
    """
    Backend system health validation.
    """

    def __init__(self):
        self.results = []

    def _check(self, name, func):
        try:
            func()
            self.results.append((name, True))
        except Exception:
            self.results.append((name, False))

    def run(self):

        self.results = []

        loader = PortfolioLoader()
        nav = NAVService()
        valuation = ValuationService()

        portfolio = None
        nav_data = None

        # Portfolio Loader
        try:
            portfolio = loader.load()
            self.results.append(("Portfolio Loader", not portfolio.empty))
        except Exception:
            self.results.append(("Portfolio Loader", False))

        # NAV Service
        try:
            nav_data = nav.get_nav()
            self.results.append(("NAV Service", not nav_data.empty))
        except Exception:
            self.results.append(("NAV Service", False))

        # Valuation Engine
        try:
            if portfolio is not None and nav_data is not None:
                result = valuation.calculate(portfolio, nav_data)
                self.results.append(("Valuation Engine", not result.empty))
            else:
                self.results.append(("Valuation Engine", False))
        except Exception:
            self.results.append(("Valuation Engine", False))

        return self.results

    def summary(self):

        passed = sum(status for _, status in self.results)
        failed = len(self.results) - passed

        score = round(
            (passed / len(self.results)) * 100,
            2
        ) if self.results else 0

        return {
            "passed": passed,
            "failed": failed,
            "score": score,
            "checks": self.results
        }