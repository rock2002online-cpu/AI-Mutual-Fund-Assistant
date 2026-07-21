"""Tests for historical AMFI NAV retrieval."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from services.nav_service import NAVService
from unittest.mock import call
import requests


@patch(
    "services.nav_service.requests.get"
)
def test_download_historical_nav(
    mock_get: MagicMock,
) -> None:
    """Download, parse, and filter official AMFI historical NAV data."""

    response = MagicMock()

    response.text = "\n".join(
        (
            (
                "Scheme Code;Scheme Name;"
                "ISIN Div Payout/ISIN Growth;"
                "ISIN Div Reinvestment;"
                "Net Asset Value;"
                "Repurchase Price;"
                "Sale Price;Date"
            ),
            (
                "122639;"
                "Parag Parikh Flexi Cap Fund - Direct Plan - Growth;"
                "INF879O01027;;"
                "91.2500;;;01-Jan-2026"
            ),
            (
                "120503;"
                "Motilal Oswal Midcap Fund - Direct Growth;"
                "INF247L01445;;"
                "75.5000;;;01-Jan-2026"
            ),
            (
                "999999;"
                "Unheld Scheme;"
                "INF000000001;;"
                "10.0000;;;01-Jan-2026"
            ),
        )
    )

    mock_get.return_value = response

    service = NAVService()

    result = service.download_historical_nav(
        scheme_codes=(
            "122639",
            "120503",
        ),
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )

    response.raise_for_status.assert_called_once_with()

    mock_get.assert_called_once_with(
        service.AMFI_HISTORY_URL,
        params={
            "frmdt": "01-Jan-2026",
            "todt": "31-Jan-2026",
        },
        timeout=30,
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert tuple(result.columns) == (
        "Scheme Code",
        "Fund",
        "NAV",
        "Date",
    )

    assert tuple(result["Scheme Code"]) == (
        "122639",
        "120503",
    )

    assert tuple(result["NAV"]) == (
        91.25,
        75.50,
    )

    assert tuple(result["Date"]) == (
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-01"),
    )

def test_get_historical_nav_downloads_in_90_day_chunks() -> None:
    """Split long AMFI history requests into supported date ranges."""

    service = NAVService()

    empty_result = pd.DataFrame(
        columns=[
            "Scheme Code",
            "Fund",
            "NAV",
            "Date",
        ]
    )

    service.download_historical_nav = MagicMock(
        side_effect=(
            empty_result.copy(),
            empty_result.copy(),
            empty_result.copy(),
        )
    )

    result = service.get_historical_nav(
        scheme_codes=(
            "122639",
            "120503",
        ),
        from_date=date(2026, 1, 1),
        to_date=date(2026, 7, 19),
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert service.download_historical_nav.call_args_list == [
        call(
            scheme_codes=(
                "122639",
                "120503",
            ),
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
        ),
        call(
            scheme_codes=(
                "122639",
                "120503",
            ),
            from_date=date(2026, 4, 1),
            to_date=date(2026, 6, 29),
        ),
        call(
            scheme_codes=(
                "122639",
                "120503",
            ),
            from_date=date(2026, 6, 30),
            to_date=date(2026, 7, 19),
        ),
    ]
@patch(
    "services.nav_service.requests.get"
)
def test_download_historical_nav_retries_timeout(
    mock_get: MagicMock,
) -> None:
    """Retry a transient AMFI read timeout."""

    response = MagicMock()

    response.text = "\n".join(
        (
            (
                "Scheme Code;Scheme Name;"
                "ISIN Div Payout/ISIN Growth;"
                "ISIN Div Reinvestment;"
                "Net Asset Value;"
                "Repurchase Price;"
                "Sale Price;Date"
            ),
            (
                "122639;"
                "Parag Parikh Flexi Cap Fund - Direct Plan - Growth;"
                "INF879O01027;;"
                "91.2500;;;01-Jan-2026"
            ),
        )
    )

    mock_get.side_effect = (
        requests.ReadTimeout(
            "AMFI request timed out"
        ),
        response,
    )

    service = NAVService()

    result = service.download_historical_nav(
        scheme_codes=(
            "122639",
        ),
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
    )

    assert mock_get.call_count == 2
    response.raise_for_status.assert_called_once_with()

    assert len(result) == 1
    assert result.iloc[0]["Scheme Code"] == "122639"