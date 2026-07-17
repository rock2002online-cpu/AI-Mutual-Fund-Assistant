from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from services.nav_service import NAVService
from services.portfolio_loader import PortfolioLoader
from services.valuation_service import ValuationService


class PortfolioService:
    """
    Coordinate portfolio loading, NAV retrieval, and portfolio valuation.

    Repository-backed loading is preferred when a UnitOfWork factory is
    configured. Existing callers without persistence configuration continue
    to use the legacy Excel-backed PortfolioLoader.
    """

    PORTFOLIO_SOURCE_COLUMNS = [
        "Scheme Code",
        "Fund",
        "Units",
        "Avg NAV",
    ]

    def __init__(
        self,
        unit_of_work_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        """
        Initialize the portfolio service.

        Parameters
        ----------
        unit_of_work_factory:
            Optional callable that creates a UnitOfWork instance.
            When omitted, get_portfolio() uses PortfolioLoader.
        """

        self.loader = PortfolioLoader()
        self.nav_service = NAVService()
        self.valuation = ValuationService()

        self._unit_of_work_factory = unit_of_work_factory

    def get_portfolio(self) -> pd.DataFrame:
        """
        Load portfolio holdings, retrieve NAV data, and calculate valuation.

        Repository-backed loading is used when a UnitOfWork factory has been
        configured. Otherwise the existing Excel loader is used.

        Returns
        -------
        pd.DataFrame
            Valuated portfolio data.
        """

        if self._unit_of_work_factory is not None:
            portfolio = self._load_portfolio_from_repository()
        else:
            portfolio = self.loader.load()

        nav = self.nav_service.get_nav()

        return self.valuation.calculate(
            portfolio,
            nav,
        )

    def _load_portfolio_from_repository(self) -> pd.DataFrame:
        """
        Load active portfolio holdings from repository transactions.

        Transactions are aggregated by fund and converted into the same
        four-column structure produced by PortfolioLoader:

        - Scheme Code
        - Fund
        - Units
        - Avg NAV

        ValuationService remains responsible for adding valuation columns.

        Returns
        -------
        pd.DataFrame
            Raw portfolio holdings matching PortfolioLoader output.
        """

        unit_of_work = self._create_unit_of_work()

        with unit_of_work as uow:
            portfolio_repository = getattr(
                uow,
                "portfolios",
                None,
            )
            transaction_repository = getattr(
                uow,
                "transactions",
                None,
            )

            if portfolio_repository is None:
                raise RuntimeError(
                    "UnitOfWork does not provide a portfolio repository."
                )

            if transaction_repository is None:
                raise RuntimeError(
                    "UnitOfWork does not provide a transaction repository."
                )

            active_portfolios = portfolio_repository.get_active()

            if not active_portfolios:
                return self._empty_repository_portfolio()

            holdings: dict[object, dict[str, object]] = {}

            for portfolio in active_portfolios:
                portfolio_id = getattr(
                    portfolio,
                    "id",
                    None,
                )

                if portfolio_id is None:
                    continue

                transactions = (
                    transaction_repository.get_for_portfolio(
                        portfolio_id
                    )
                )

                for transaction in transactions:
                    fund = getattr(
                        transaction,
                        "fund",
                        None,
                    )

                    if fund is None:
                        continue

                    fund_id = getattr(
                        transaction,
                        "fund_id",
                        None,
                    )

                    if fund_id is None:
                        fund_id = getattr(
                            fund,
                            "id",
                            None,
                        )

                    if fund_id is None:
                        continue

                    scheme_code = str(
                        getattr(
                            fund,
                            "scheme_code",
                            "",
                        )
                        or ""
                    ).strip()

                    fund_name = str(
                        getattr(
                            fund,
                            "name",
                            "",
                        )
                        or ""
                    ).strip()

                    if not scheme_code or not fund_name:
                        continue

                    units = self._to_float(
                        getattr(
                            transaction,
                            "units",
                            0,
                        )
                    )

                    amount = self._to_float(
                        getattr(
                            transaction,
                            "amount",
                            0,
                        )
                    )

                    if fund_id not in holdings:
                        holdings[fund_id] = {
                            "Scheme Code": scheme_code,
                            "Fund": fund_name,
                            "Units": 0.0,
                            "Amount": 0.0,
                        }

                    holding = holdings[fund_id]

                    holding["Units"] = (
                        self._to_float(
                            holding["Units"]
                        )
                        + units
                    )

                    holding["Amount"] = (
                        self._to_float(
                            holding["Amount"]
                        )
                        + amount
                    )

            rows: list[dict[str, object]] = []

            for holding in holdings.values():
                total_units = self._to_float(
                    holding["Units"]
                )
                total_amount = self._to_float(
                    holding["Amount"]
                )

                if total_units <= 0:
                    continue

                average_nav = total_amount / total_units

                rows.append(
                    {
                        "Scheme Code": holding[
                            "Scheme Code"
                        ],
                        "Fund": holding["Fund"],
                        "Units": total_units,
                        "Avg NAV": average_nav,
                    }
                )

        return pd.DataFrame(
            rows,
            columns=self.PORTFOLIO_SOURCE_COLUMNS,
        )

    def _empty_repository_portfolio(self) -> pd.DataFrame:
        """
        Return an empty DataFrame matching PortfolioLoader output.
        """

        return pd.DataFrame(
            columns=self.PORTFOLIO_SOURCE_COLUMNS
        )

    @staticmethod
    def _to_float(value: object) -> float:
        """
        Convert an ORM or repository numeric value to float.
        """

        if value is None:
            return 0.0

        return float(value)

    def _create_unit_of_work(self) -> object:
        """
        Create a UnitOfWork using the configured factory.

        Raises
        ------
        RuntimeError
            If no UnitOfWork factory has been configured.
        """

        if self._unit_of_work_factory is None:
            raise RuntimeError(
                "No UnitOfWork factory has been configured."
            )

        return self._unit_of_work_factory()