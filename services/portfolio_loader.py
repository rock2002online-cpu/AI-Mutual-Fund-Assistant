from pathlib import Path
import pandas as pd


class PortfolioLoader:
    """
    Loads the raw portfolio exported from Fyers.
    """

    def __init__(self):

        self.project_root = Path(__file__).resolve().parent.parent

        self.portfolio_file = (
            self.project_root / "data" / "portfolio.xlsx"
        )

    def load(self):

        if not self.portfolio_file.exists():
            raise FileNotFoundError(
                f"Portfolio file not found:\n{self.portfolio_file}"
            )

        df = pd.read_excel(self.portfolio_file)

        return df