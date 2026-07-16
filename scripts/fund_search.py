from scripts.nav_service import download_nav_data


def search_funds(keyword):

    df = download_nav_data()

    result = df[
        df["Scheme Name"].str.contains(
            keyword,
            case=False,
            na=False
        )
    ]

    return result[
        [
            "Scheme Code",
            "Scheme Name",
            "Net Asset Value",
            "Date"
        ]
    ]