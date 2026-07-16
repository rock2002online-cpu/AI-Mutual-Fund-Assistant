from pathlib import Path
from datetime import datetime

import pandas as pd
import requests


class NAVService:
    """
    Downloads and caches the latest AMFI NAV data.
    """

    AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

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