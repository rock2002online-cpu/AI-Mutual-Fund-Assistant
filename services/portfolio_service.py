
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from services.nav_service import NAVService
from services.portfolio_loader import PortfolioLoader
from services.valuation_service import ValuationService


class PortfolioService:
    """
    Coordinate portfolio loading, NAV retrieval, and portfolio valuation.

    Version 10.1 introduces dependency injection for the enterprise
    persistence layer while preserving the existing public API and
    application behaviour.

    The repository-backed loader is available for migration work but is
    not yet used by get_portfolio().
    """

    def __init__(
        self,
        unit_of_work_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        """
        Initialize the portfolio service.

        Parameters
        ----------
        unit_of_work_factory:
            Optional callable used to create a UnitOfWork instance.

            The dependency remains optional during the incremental
            repository migration so existing callers continue to work
            without modification.
        """

        self.loader = PortfolioLoader()
        self.nav_service = NAVService()
        self.valuation = ValuationService()

        self._unit_of_work_factory = unit_of_work_factory

    def get_portfolio(self) -> pd.DataFrame:
        """
        Load portfolio holdings, retrieve latest NAV data, and calculate
        the current portfolio valuation.

        The existing Excel-backed behaviour and public API remain unchanged.

        Returns
        -------
        pd.DataFrame
            Valuated portfolio data.
        """

        portfolio = self.loader.load()
        nav = self.nav_service.get_nav()

        return self.valuation.calculate(
            portfolio,
            nav,
        )

    def _load_portfolio_from_repository(self) -> pd.DataFrame:
        """
        Return the repository-backed portfolio DataFrame structure.

        This method is intentionally not called by get_portfolio() yet.
        A later migration step will populate the DataFrame using:

        - PortfolioRepository
        - FundRepository
        - TransactionRepository
        - NAVHistoryRepository

        Returns
        -------
        pd.DataFrame
            Empty DataFrame with the schema expected by the existing
            portfolio valuation workflow.
        """

        return pd.DataFrame(
            columns=[
                "Scheme Code",
                "Fund",
                "Units",
                "Avg NAV",
                "Latest NAV",
                "Investment",
                "Current Value",
                "Profit/Loss",
                "Return %",
                "Status",
            ]
        )

    def _create_unit_of_work(self) -> object:
        """
        Create and return a UnitOfWork instance.

        Centralizing UnitOfWork construction allows tests to inject fake
        implementations and avoids coupling PortfolioService directly to
        concrete persistence configuration.

        Returns
        -------
        object
            UnitOfWork instance created by the configured factory.

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

