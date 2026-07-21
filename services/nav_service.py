from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd
import requests


class NAVService:
    """
    Downloads and caches the latest AMFI NAV data.
    """

    AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
    AMFI_HISTORY_URL = (
        "https://portal.amfiindia.com/"
        "DownloadNAVHistoryReport_Po.aspx"
    )
    AMFI_MAX_ATTEMPTS = 3

    def __init__(self):

        self.project_root = Path(__file__).resolve().parent.parent

        self.data_folder = self.project_root / "data"

        self.nav_file = self.data_folder / "nav_history.csv"

    def get_nav(self):
        """
        Return today's NAV data.
        Uses cached file if already downloaded today.
        """

        if self.nav_file.exists():

            modified = datetime.fromtimestamp(
                self.nav_file.stat().st_mtime
            ).date()

            if modified == datetime.today().date():
                print("✅ Using cached NAV data")

                return pd.read_csv(self.nav_file)

        print("⬇ Downloading latest NAV data...")

        return self.download_nav()

    def download_nav(self):

        response = requests.get(
            self.AMFI_URL,
            timeout=30
        )

        response.raise_for_status()

        rows = []

        for line in response.text.splitlines():

            parts = line.split(";")

            if len(parts) != 6:
                continue

            if parts[0] == "Scheme Code":
                continue

            rows.append(parts)

        df = pd.DataFrame(
            rows,
            columns=[
                "Scheme Code",
                "ISIN Div",
                "ISIN Growth",
                "Fund",
                "NAV",
                "Date"
            ]
        )

        df["Scheme Code"] = df["Scheme Code"].astype(str)
        df["NAV"] = pd.to_numeric(df["NAV"], errors="coerce")

        df.to_csv(
            self.nav_file,
            index=False
        )

        return df

    def download_historical_nav(
        self,
        *,
        scheme_codes: tuple[str, ...],
        from_date: date,
        to_date: date,
    ) -> pd.DataFrame:
        """Download and parse one AMFI historical NAV date range."""

        normalized_scheme_codes = {
            str(scheme_code).strip()
            for scheme_code in scheme_codes
            if str(scheme_code).strip()
        }

        request_params = {
            "frmdt": from_date.strftime(
                "%d-%b-%Y"
            ),
            "todt": to_date.strftime(
                "%d-%b-%Y"
            ),
        }

        for attempt in range(
            1,
            self.AMFI_MAX_ATTEMPTS + 1,
        ):
            try:
                response = requests.get(
                    self.AMFI_HISTORY_URL,
                    params=request_params,
                    timeout=30,
                )
                break

            except requests.RequestException:
                if attempt == self.AMFI_MAX_ATTEMPTS:
                    raise

        response.raise_for_status()

        rows: list[dict[str, object]] = []

        for line in response.text.splitlines():
            parts = [
                part.strip()
                for part in line.split(";")
            ]

            if len(parts) != 8:
                continue

            scheme_code = parts[0]

            if scheme_code not in normalized_scheme_codes:
                continue

            rows.append(
                {
                    "Scheme Code": scheme_code,
                    "Fund": parts[1],
                    "NAV": parts[4],
                    "Date": parts[7],
                }
            )

        result = pd.DataFrame(
            rows,
            columns=[
                "Scheme Code",
                "Fund",
                "NAV",
                "Date",
            ],
        )

        result["NAV"] = pd.to_numeric(
            result["NAV"],
            errors="coerce",
        )

        result["Date"] = pd.to_datetime(
            result["Date"],
            format="%d-%b-%Y",
            errors="coerce",
        )

        result = result.dropna(
            subset=[
                "NAV",
                "Date",
            ]
        )

        return result.reset_index(
            drop=True,
        )

    def get_historical_nav(
        self,
        *,
        scheme_codes: tuple[str, ...],
        from_date: date,
        to_date: date,
    ) -> pd.DataFrame:
        """Download a historical NAV range in AMFI-supported chunks."""

        if from_date > to_date:
            raise ValueError(
                "from_date must be on or before to_date"
            )

        chunks: list[pd.DataFrame] = []
        chunk_start = from_date

        while chunk_start <= to_date:
            chunk_end = min(
                chunk_start
                + timedelta(days=89),
                to_date,
            )

            chunks.append(
                self.download_historical_nav(
                    scheme_codes=scheme_codes,
                    from_date=chunk_start,
                    to_date=chunk_end,
                )
            )

            chunk_start = (
                chunk_end
                + timedelta(days=1)
            )

        if not chunks:
            return pd.DataFrame(
                columns=[
                    "Scheme Code",
                    "Fund",
                    "NAV",
                    "Date",
                ]
            )

        result = pd.concat(
            chunks,
            ignore_index=True,
        )

        if result.empty:
            return result

        result = result.drop_duplicates(
            subset=[
                "Scheme Code",
                "Date",
            ],
            keep="last",
        )

        result = result.sort_values(
            by=[
                "Date",
                "Scheme Code",
            ]
        )

        return result.reset_index(
            drop=True,
        )