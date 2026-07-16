"""
Portfolio allocation analytics service.

This module calculates portfolio allocation metrics from the portfolio
DataFrame supplied by PortfolioService.

Responsibilities:
- Validate portfolio data
- Calculate total current portfolio value
- Calculate allocation percentage for every holding
- Identify the largest holding
- Identify the smallest holding

This module contains no Streamlit or Plotly code.
PortfolioService remains the single source of portfolio data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd


@dataclass(frozen=True, slots=True)
class FundAllocation:
    """
    Allocation information for one mutual fund holding.

    Attributes:
        fund:
            Name of the mutual fund.

        current_value:
            Current market value of the holding.

        allocation_percentage:
            Percentage contribution of the holding to the total
            current portfolio value.
    """

    fund: str
    current_value: float
    allocation_percentage: float


@dataclass(frozen=True, slots=True)
class PortfolioAllocation:
    """
    Complete portfolio allocation result.

    Attributes:
        total_value:
            Total current market value of the portfolio.

        largest_holding:
            Holding with the highest allocation percentage.

        smallest_holding:
            Holding with the lowest allocation percentage.

        funds:
            All holdings ordered from largest allocation to smallest.
    """

    total_value: float
    largest_holding: FundAllocation
    smallest_holding: FundAllocation
    funds: tuple[FundAllocation, ...]


class PortfolioAllocationService:
    """
    Calculate portfolio allocation metrics.

    The service receives the portfolio DataFrame from PortfolioService.
    It does not load, modify, or persist portfolio data.
    """

    FUND_COLUMN: Final[str] = "Fund"
    CURRENT_VALUE_COLUMN: Final[str] = "Current Value"
    ALLOCATION_COLUMN: Final[str] = "Allocation %"

    REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
        FUND_COLUMN,
        CURRENT_VALUE_COLUMN,
    )

    def calculate(
        self,
        portfolio: pd.DataFrame,
    ) -> PortfolioAllocation:
        """
        Calculate allocation metrics for the complete portfolio.

        Args:
            portfolio:
                Portfolio DataFrame returned by PortfolioService.

        Returns:
            PortfolioAllocation containing total value, largest holding,
            smallest holding, and fund-level allocation details.

        Raises:
            TypeError:
                If portfolio is not a pandas DataFrame.

            ValueError:
                If the DataFrame is empty, required columns are missing,
                fund names are invalid, current values are invalid, or
                total current value is not greater than zero.
        """
        self._validate_dataframe(portfolio)

        allocation_df = portfolio.loc[
            :,
            [
                self.FUND_COLUMN,
                self.CURRENT_VALUE_COLUMN,
            ],
        ].copy()

        allocation_df[self.FUND_COLUMN] = (
            allocation_df[self.FUND_COLUMN]
            .astype("string")
            .str.strip()
        )

        allocation_df[self.CURRENT_VALUE_COLUMN] = self._to_numeric_series(
            allocation_df[self.CURRENT_VALUE_COLUMN],
            column_name=self.CURRENT_VALUE_COLUMN,
        )

        self._validate_rows(allocation_df)

        total_value = float(
            allocation_df[self.CURRENT_VALUE_COLUMN].sum()
        )

        if total_value <= 0:
            raise ValueError(
                "Portfolio allocation cannot be calculated because "
                "the total current portfolio value is not greater than zero."
            )

        allocation_df[self.ALLOCATION_COLUMN] = (
            allocation_df[self.CURRENT_VALUE_COLUMN]
            .div(total_value)
            .mul(100.0)
        )

        allocation_df = allocation_df.sort_values(
            by=[
                self.ALLOCATION_COLUMN,
                self.CURRENT_VALUE_COLUMN,
                self.FUND_COLUMN,
            ],
            ascending=[
                False,
                False,
                True,
            ],
            kind="stable",
        ).reset_index(drop=True)

        funds = tuple(
            FundAllocation(
                fund=str(row[self.FUND_COLUMN]),
                current_value=float(
                    row[self.CURRENT_VALUE_COLUMN]
                ),
                allocation_percentage=float(
                    row[self.ALLOCATION_COLUMN]
                ),
            )
            for _, row in allocation_df.iterrows()
        )

        if not funds:
            raise ValueError(
                "No valid portfolio holdings are available "
                "for allocation analysis."
            )

        return PortfolioAllocation(
            total_value=total_value,
            largest_holding=funds[0],
            smallest_holding=funds[-1],
            funds=funds,
        )

    def _validate_dataframe(
        self,
        portfolio: pd.DataFrame,
    ) -> None:
        """
        Validate the portfolio DataFrame structure.

        Args:
            portfolio:
                Portfolio DataFrame to validate.

        Raises:
            TypeError:
                If portfolio is not a pandas DataFrame.

            ValueError:
                If the DataFrame is empty or required columns are missing.
        """
        if not isinstance(portfolio, pd.DataFrame):
            raise TypeError(
                "PortfolioAllocationService requires a pandas DataFrame."
            )

        if portfolio.empty:
            raise ValueError(
                "Portfolio allocation cannot be calculated because "
                "the portfolio DataFrame is empty."
            )

        missing_columns = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in portfolio.columns
        ]

        if missing_columns:
            raise ValueError(
                "Portfolio allocation requires the following missing "
                f"column(s): {', '.join(missing_columns)}."
            )

    def _validate_rows(
        self,
        allocation_df: pd.DataFrame,
    ) -> None:
        """
        Validate fund names and current values.

        Args:
            allocation_df:
                Prepared allocation DataFrame.

        Raises:
            ValueError:
                If fund names are missing, duplicated, or current values
                are negative.
        """
        invalid_fund_mask = (
            allocation_df[self.FUND_COLUMN].isna()
            | allocation_df[self.FUND_COLUMN].eq("")
        )

        if invalid_fund_mask.any():
            invalid_count = int(invalid_fund_mask.sum())

            raise ValueError(
                "Portfolio allocation contains "
                f"{invalid_count} holding(s) without a valid fund name."
            )

        negative_value_mask = (
            allocation_df[self.CURRENT_VALUE_COLUMN] < 0
        )

        if negative_value_mask.any():
            invalid_count = int(negative_value_mask.sum())

            raise ValueError(
                "Portfolio allocation contains "
                f"{invalid_count} holding(s) with a negative current value."
            )

        duplicate_fund_mask = allocation_df[
            self.FUND_COLUMN
        ].duplicated(keep=False)

        if duplicate_fund_mask.any():
            duplicate_names = sorted(
                allocation_df.loc[
                    duplicate_fund_mask,
                    self.FUND_COLUMN,
                ]
                .astype(str)
                .unique()
                .tolist()
            )

            raise ValueError(
                "Portfolio allocation contains duplicate fund entries: "
                + ", ".join(duplicate_names)
                + ". Combine duplicate holdings before calculating "
                "allocation."
            )

    @staticmethod
    def _to_numeric_series(
        series: pd.Series,
        column_name: str,
    ) -> pd.Series:
        """
        Convert a pandas Series to numeric values.

        Missing values are treated as zero. Non-empty values that cannot
        be converted to numbers raise an error.

        Args:
            series:
                Source pandas Series.

            column_name:
                User-facing column name used in validation messages.

        Returns:
            Numeric Series of float values.

        Raises:
            ValueError:
                If non-empty values cannot be converted to numbers.
        """
        numeric_series = pd.to_numeric(
            series,
            errors="coerce",
        )

        invalid_mask = series.notna() & numeric_series.isna()

        if invalid_mask.any():
            invalid_count = int(invalid_mask.sum())

            raise ValueError(
                f"Column '{column_name}' contains "
                f"{invalid_count} non-numeric value(s)."
            )

        return numeric_series.fillna(0.0).astype(float)