"""Tests for the Portfolio summary component."""

from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.components.portfolio_summary import (
    show_portfolio_summary,
)


@patch("dashboard.components.portfolio_summary.st.divider")
@patch("dashboard.components.portfolio_summary.st.columns")
@patch("dashboard.components.portfolio_summary.st.write")
@patch("dashboard.components.portfolio_summary.st.success")
def test_portfolio_summary_does_not_render_debug_output(
    mock_success,
    mock_write,
    mock_columns,
    mock_divider,
) -> None:
    """Render production metrics without development diagnostics."""

    portfolio = pd.DataFrame(
        {
            "Investment": [1000.0],
            "Current Value": [1200.0],
            "Profit/Loss": [200.0],
            "Return %": [20.0],
        }
    )

    mock_columns.side_effect = [
        (
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ),
        (
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ),
    ]

    show_portfolio_summary(portfolio)

    mock_success.assert_not_called()
    mock_write.assert_not_called()