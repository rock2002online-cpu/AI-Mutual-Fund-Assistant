"""
Bootstrap enterprise portfolio data.

This script imports:

- One default portfolio
- Mutual fund master records from data/portfolio.xlsx
- One opening-balance transaction for each holding

The script is idempotent. Running it repeatedly does not create duplicate
portfolios, funds, or opening-balance transactions.

Repositories do not commit directly. The Unit of Work controls the complete
transaction boundary and rolls back all changes if an error occurs.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

import pandas as pd


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from models.fund import Fund
from models.nav_history import NAVHistory
from models.portfolio import Portfolio
from models.transaction import Transaction
from repositories.unit_of_work import UnitOfWork


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORTFOLIO_FILE: Final[Path] = (
    PROJECT_ROOT / "data" / "portfolio.xlsx"
)

DEFAULT_PORTFOLIO_NAME: Final[str] = "Primary Portfolio"
DEFAULT_PORTFOLIO_DESCRIPTION: Final[str] = (
    "Primary mutual fund portfolio imported from "
    "data/portfolio.xlsx."
)
DEFAULT_OWNER_REFERENCE: Final[str] = "default"
DEFAULT_CURRENCY: Final[str] = "INR"

OPENING_TRANSACTION_TYPE: Final[str] = "OPENING_BALANCE"

REQUIRED_COLUMNS: Final[set[str]] = {
    "Scheme Code",
    "Fund",
    "Units",
    "Avg NAV",
}

NAV_HISTORY_FILE: Final[Path] = (
    PROJECT_ROOT / "data" / "nav_history.csv"
)

NAV_DATE_FORMAT: Final[str] = "%d-%b-%Y"

REQUIRED_NAV_COLUMNS: Final[set[str]] = {
    "Scheme Code",
    "NAV",
    "Date",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BootstrapDataError(RuntimeError):
    """Raised when enterprise portfolio data cannot be bootstrapped."""


# ---------------------------------------------------------------------------
# Source-data loading and validation
# ---------------------------------------------------------------------------


def load_portfolio_source() -> pd.DataFrame:
    """
    Load and validate the existing portfolio workbook.

    Returns:
        Validated portfolio DataFrame.

    Raises:
        BootstrapDataError:
            If the workbook does not exist, cannot be read, is empty, or
            does not contain the required columns.
    """

    if not PORTFOLIO_FILE.exists():
        raise BootstrapDataError(
            f"Portfolio file was not found: {PORTFOLIO_FILE}"
        )

    try:
        dataframe = pd.read_excel(PORTFOLIO_FILE)
    except Exception as exc:
        raise BootstrapDataError(
            f"Unable to read portfolio file: {PORTFOLIO_FILE}"
        ) from exc

    missing_columns = REQUIRED_COLUMNS.difference(
        dataframe.columns
    )

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise BootstrapDataError(
            "Portfolio file is missing required columns: "
            f"{missing}"
        )

    if dataframe.empty:
        raise BootstrapDataError(
            "Portfolio file contains no holdings."
        )

    return dataframe.copy()

def load_nav_history_source() -> pd.DataFrame:
    """
    Load and validate the cached NAV source file.

    Only portfolio-related funds will later be imported.
    """

    if not NAV_HISTORY_FILE.exists():
        raise BootstrapDataError(
            f"NAV history file was not found: {NAV_HISTORY_FILE}"
        )

    try:
        dataframe = pd.read_csv(
            NAV_HISTORY_FILE,
            dtype={
                "Scheme Code": "string",
            },
        )
    except Exception as exc:
        raise BootstrapDataError(
            f"Unable to read NAV history file: {NAV_HISTORY_FILE}"
        ) from exc

    missing_columns = REQUIRED_NAV_COLUMNS.difference(
        dataframe.columns
    )

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise BootstrapDataError(
            "NAV history file is missing required columns: "
            f"{missing}"
        )

    if dataframe.empty:
        raise BootstrapDataError(
            "NAV history file contains no records."
        )

    return dataframe.copy()

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
def normalize_nav_date(
    value: object,
    *,
    scheme_code: str,
) -> date:
    """Parse an AMFI NAV date into a date object."""

    if pd.isna(value):
        raise BootstrapDataError(
            f"NAV Date is empty for scheme code {scheme_code}."
        )

    raw_date = str(value).strip()

    if not raw_date:
        raise BootstrapDataError(
            f"NAV Date is invalid for scheme code {scheme_code}."
        )

    try:
        return datetime.strptime(
            raw_date,
            NAV_DATE_FORMAT,
        ).date()
    except ValueError as exc:
        raise BootstrapDataError(
            f"NAV Date has an unsupported format for scheme code "
            f"{scheme_code}: {raw_date!r}"
        ) from exc

def normalize_scheme_code(value: object) -> str:
    """
    Normalize a scheme code read from Excel.

    Excel may expose scheme codes as integers, floats, or strings.
    """

    if pd.isna(value):
        raise BootstrapDataError(
            "A portfolio row contains an empty Scheme Code."
        )

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    scheme_code = str(value).strip()

    if scheme_code.endswith(".0"):
        numeric_part = scheme_code[:-2]

        if numeric_part.isdigit():
            scheme_code = numeric_part

    if not scheme_code:
        raise BootstrapDataError(
            "A portfolio row contains an invalid Scheme Code."
        )

    return scheme_code


def normalize_fund_name(value: object) -> str:
    """Normalize and validate a fund name."""

    if pd.isna(value):
        raise BootstrapDataError(
            "A portfolio row contains an empty Fund name."
        )

    fund_name = str(value).strip()

    if not fund_name:
        raise BootstrapDataError(
            "A portfolio row contains an invalid Fund name."
        )

    return fund_name


def normalize_positive_decimal(
    value: object,
    *,
    field_name: str,
    scheme_code: str,
) -> Decimal:
    """
    Convert a source value into a positive finite Decimal.

    Args:
        value:
            Value read from the source workbook.
        field_name:
            Human-readable source column name.
        scheme_code:
            Scheme code used in validation messages.

    Returns:
        Positive Decimal value.

    Raises:
        BootstrapDataError:
            If the value is missing, invalid, non-finite, zero, or negative.
    """

    if pd.isna(value):
        raise BootstrapDataError(
            f"{field_name} is empty for scheme code "
            f"{scheme_code}."
        )

    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BootstrapDataError(
            f"{field_name} is invalid for scheme code "
            f"{scheme_code}: {value!r}"
        ) from exc

    if not normalized.is_finite():
        raise BootstrapDataError(
            f"{field_name} must be finite for scheme code "
            f"{scheme_code}."
        )

    if normalized <= 0:
        raise BootstrapDataError(
            f"{field_name} must be greater than zero for "
            f"scheme code {scheme_code}."
        )

    return normalized


# ---------------------------------------------------------------------------
# Portfolio import
# ---------------------------------------------------------------------------


def get_or_create_portfolio(
    unit_of_work: UnitOfWork,
) -> tuple[Portfolio, bool]:
    """
    Return the default portfolio, creating it when necessary.

    Returns:
        Tuple of:
        - portfolio entity
        - True when newly created, otherwise False
    """

    if unit_of_work.portfolios is None:
        raise BootstrapDataError(
            "PortfolioRepository is unavailable."
        )

    existing_portfolio = (
        unit_of_work.portfolios.get_by_name(
            DEFAULT_PORTFOLIO_NAME
        )
    )

    if existing_portfolio is not None:
        return existing_portfolio, False

    portfolio = Portfolio(
        name=DEFAULT_PORTFOLIO_NAME,
        description=DEFAULT_PORTFOLIO_DESCRIPTION,
        owner_reference=DEFAULT_OWNER_REFERENCE,
        base_currency=DEFAULT_CURRENCY,
        is_active=True,
    )

    created_portfolio = (
        unit_of_work.portfolios.add(portfolio)
    )

    return created_portfolio, True


# ---------------------------------------------------------------------------
# Fund import
# ---------------------------------------------------------------------------


def import_funds(
    dataframe: pd.DataFrame,
    unit_of_work: UnitOfWork,
) -> tuple[int, int]:
    """
    Import fund master records.

    Existing funds are matched using scheme code.

    Returns:
        Tuple of:
        - number of funds created
        - number of existing funds reused
    """

    if unit_of_work.funds is None:
        raise BootstrapDataError(
            "FundRepository is unavailable."
        )

    created_count = 0
    existing_count = 0

    source = dataframe[
        ["Scheme Code", "Fund"]
    ].drop_duplicates(
        subset=["Scheme Code"],
        keep="first",
    )

    for raw_scheme_code, raw_fund_name in source.itertuples(
        index=False,
        name=None,
    ):
        scheme_code = normalize_scheme_code(
            raw_scheme_code
        )
        fund_name = normalize_fund_name(
            raw_fund_name
        )

        existing_fund = (
            unit_of_work.funds.get_by_scheme_code(
                scheme_code
            )
        )

        if existing_fund is not None:
            existing_count += 1
            continue

        fund = Fund(
            scheme_code=scheme_code,
            name=fund_name,
            amc=None,
            category=None,
            plan=None,
            option=None,
        )

        unit_of_work.funds.add(fund)
        created_count += 1

    return created_count, existing_count


# ---------------------------------------------------------------------------
# Opening-transaction import
# ---------------------------------------------------------------------------


def import_opening_transactions(
    dataframe: pd.DataFrame,
    *,
    portfolio: Portfolio,
    unit_of_work: UnitOfWork,
) -> tuple[int, int]:
    """
    Import one opening-balance transaction for each fund holding.

    An existing opening transaction is identified by:

    - portfolio_id
    - fund_id
    - transaction_type == OPENING_BALANCE

    This makes the import idempotent.

    Returns:
        Tuple of:
        - number of opening transactions created
        - number of existing opening transactions reused
    """

    if unit_of_work.funds is None:
        raise BootstrapDataError(
            "FundRepository is unavailable."
        )

    if unit_of_work.transactions is None:
        raise BootstrapDataError(
            "TransactionRepository is unavailable."
        )

    if portfolio.id is None:
        raise BootstrapDataError(
            "Portfolio must have an identifier before "
            "transactions can be imported."
        )

    created_count = 0
    existing_count = 0

    source = dataframe[
        [
            "Scheme Code",
            "Fund",
            "Units",
            "Avg NAV",
        ]
    ].drop_duplicates(
        subset=["Scheme Code"],
        keep="first",
    )

    for (
        raw_scheme_code,
        _raw_fund_name,
        raw_units,
        raw_average_nav,
    ) in source.itertuples(
        index=False,
        name=None,
    ):
        scheme_code = normalize_scheme_code(
            raw_scheme_code
        )

        units = normalize_positive_decimal(
            raw_units,
            field_name="Units",
            scheme_code=scheme_code,
        )

        average_nav = normalize_positive_decimal(
            raw_average_nav,
            field_name="Avg NAV",
            scheme_code=scheme_code,
        )

        fund = unit_of_work.funds.get_by_scheme_code(
            scheme_code
        )

        if fund is None:
            raise BootstrapDataError(
                "Fund was not found after fund import for "
                f"scheme code {scheme_code}."
            )

        if fund.id is None:
            raise BootstrapDataError(
                "Fund must have an identifier before a "
                "transaction can be imported for scheme code "
                f"{scheme_code}."
            )

        existing_transactions = (
            unit_of_work.transactions.find_by(
                portfolio_id=portfolio.id,
                fund_id=fund.id,
                transaction_type=(
                    OPENING_TRANSACTION_TYPE
                ),
            )
        )

        if existing_transactions:
            existing_count += 1
            continue

        amount = units * average_nav

        transaction = Transaction(
            portfolio_id=portfolio.id,
            fund_id=fund.id,
            transaction_date=date.today(),
            transaction_type=(
                OPENING_TRANSACTION_TYPE
            ),
            units=units,
            nav=average_nav,
            amount=amount,
        )

        unit_of_work.transactions.add(
            transaction
        )
        created_count += 1

    return created_count, existing_count

def import_nav_history(
    dataframe: pd.DataFrame,
    *,
    unit_of_work: UnitOfWork,
) -> tuple[int, int, int]:
    """
    Import cached NAV records for funds already stored in the database.

    A NAV record is considered unique by:

    - fund_id
    - nav_date

    Returns:
        Tuple containing:
        - number of NAV records created
        - number of existing NAV records reused
        - number of unrelated NAV rows skipped
    """

    if unit_of_work.funds is None:
        raise BootstrapDataError(
            "FundRepository is unavailable."
        )

    if unit_of_work.nav_history is None:
        raise BootstrapDataError(
            "NAVHistoryRepository is unavailable."
        )

    database_funds = unit_of_work.funds.get_all()

    funds_by_scheme_code = {
        normalize_scheme_code(fund.scheme_code): fund
        for fund in database_funds
    }

    if not funds_by_scheme_code:
        raise BootstrapDataError(
            "No funds exist in the database. Import funds before "
            "importing NAV history."
        )

    created_count = 0
    existing_count = 0
    skipped_count = 0

    source = dataframe[
        ["Scheme Code", "NAV", "Date"]
    ].drop_duplicates(
        subset=["Scheme Code", "Date"],
        keep="last",
    )

    for (
        raw_scheme_code,
        raw_nav,
        raw_nav_date,
    ) in source.itertuples(
        index=False,
        name=None,
    ):
        scheme_code = normalize_scheme_code(
            raw_scheme_code
        )

        fund = funds_by_scheme_code.get(
            scheme_code
        )

        if fund is None:
            skipped_count += 1
            continue

        if fund.id is None:
            raise BootstrapDataError(
                "Fund must have an identifier before NAV history "
                f"can be imported for scheme code {scheme_code}."
            )

        nav = normalize_positive_decimal(
            raw_nav,
            field_name="NAV",
            scheme_code=scheme_code,
        )

        nav_date = normalize_nav_date(
            raw_nav_date,
            scheme_code=scheme_code,
        )

        existing_records = (
            unit_of_work.nav_history.find_by(
                fund_id=fund.id,
                nav_date=nav_date,
            )
        )

        if existing_records:
            existing_count += 1
            continue

        nav_record = NAVHistory(
            fund_id=fund.id,
            nav_date=nav_date,
            nav=nav,
        )

        unit_of_work.nav_history.add(
            nav_record
        )
        created_count += 1

    return (
        created_count,
        existing_count,
        skipped_count,
    )

# ---------------------------------------------------------------------------
# Bootstrap orchestration
# ---------------------------------------------------------------------------


def bootstrap_enterprise_data() -> None:
    """
    Import portfolio, funds, opening transactions, and cached NAV records.

    All database operations share one Unit of Work transaction.
    """

    portfolio_dataframe = load_portfolio_source()
    nav_dataframe = load_nav_history_source()

    with UnitOfWork() as unit_of_work:
        portfolio, portfolio_created = (
            get_or_create_portfolio(
                unit_of_work
            )
        )

        (
            funds_created,
            funds_existing,
        ) = import_funds(
            dataframe=portfolio_dataframe,
            unit_of_work=unit_of_work,
        )

        (
            transactions_created,
            transactions_existing,
        ) = import_opening_transactions(
            dataframe=portfolio_dataframe,
            portfolio=portfolio,
            unit_of_work=unit_of_work,
        )

        (
            nav_records_created,
            nav_records_existing,
            nav_records_skipped,
        ) = import_nav_history(
            dataframe=nav_dataframe,
            unit_of_work=unit_of_work,
        )

    portfolio_status = (
        "created"
        if portfolio_created
        else "already existed"
    )

    print("Enterprise data bootstrap completed.")
    print(
        f"Portfolio: {portfolio.name} "
        f"({portfolio_status})"
    )
    print(f"Funds created: {funds_created}")
    print(
        f"Funds already present: {funds_existing}"
    )
    print(
        "Opening transactions created: "
        f"{transactions_created}"
    )
    print(
        "Opening transactions already present: "
        f"{transactions_existing}"
    )
    print(
        f"NAV records created: {nav_records_created}"
    )
    print(
        "NAV records already present: "
        f"{nav_records_existing}"
    )
    print(
        "Unrelated NAV rows skipped: "
        f"{nav_records_skipped}"
    )


# ---------------------------------------------------------------------------
# Command entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the enterprise-data bootstrap command."""

    try:
        bootstrap_enterprise_data()
    except BootstrapDataError as exc:
        print(
            f"Bootstrap failed: {exc}"
        )
        return 1
    except Exception as exc:
        print(
            "Bootstrap failed because of an unexpected "
            f"error: {exc}"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())