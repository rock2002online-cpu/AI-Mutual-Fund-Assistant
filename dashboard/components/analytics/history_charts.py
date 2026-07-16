"""
Historical portfolio analytics chart components.

This module provides reusable Streamlit and Plotly components for displaying
portfolio valuation history produced by PortfolioHistoryService.

Architecture
------------
PortfolioHistoryService is responsible for:

- Reading the portfolio history data source.
- Validating the source schema.
- Normalizing historical records.
- Returning canonical ``Date`` and ``Value`` columns.

This module is responsible only for:

- Validating the component input boundary.
- Building Plotly figures.
- Rendering historical analytics in Streamlit.

The component does not read files, retrieve portfolio data, or duplicate
portfolio analytics calculations.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


logger = logging.getLogger(__name__)


# ============================================================
# Public Schema Constants
# ============================================================

DATE_COLUMN: Final[str] = "Date"
VALUE_COLUMN: Final[str] = "Value"

REQUIRED_HISTORY_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        DATE_COLUMN,
        VALUE_COLUMN,
    }
)

PORTFOLIO_GROWTH_CHART_KEY: Final[str] = (
    "analytics_history_portfolio_growth_chart"
)

PORTFOLIO_GROWTH_CHART_TITLE: Final[str] = (
    "Portfolio Value Growth"
)

HISTORY_SECTION_TITLE: Final[str] = (
    "📈 Historical Portfolio Analytics"
)


# ============================================================
# Input Validation
# ============================================================


def _get_missing_columns(
    dataframe: pd.DataFrame,
    required_columns: Collection[str],
) -> tuple[str, ...]:
    """
    Return required columns missing from a dataframe.

    Args:
        dataframe:
            Dataframe whose schema is being inspected.

        required_columns:
            Column names required by the caller.

    Returns:
        Alphabetically sorted tuple containing missing column names.
    """

    return tuple(
        sorted(
            set(required_columns).difference(
                dataframe.columns
            )
        )
    )


def _validate_history_dataframe(
    history: pd.DataFrame,
) -> bool:
    """
    Validate portfolio history before chart rendering.

    PortfolioHistoryService normally guarantees the canonical schema. This
    validation protects the component boundary when the renderer is called
    independently, supplied with test data, or used by another view.

    Args:
        history:
            Expected normalized portfolio history containing ``Date`` and
            ``Value`` columns.

    Returns:
        True when the dataframe can be rendered.
        False when the component has displayed an appropriate user message.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.
    """

    if not isinstance(history, pd.DataFrame):
        raise TypeError(
            "history must be a pandas DataFrame."
        )

    if history.empty:
        st.info(
            "No historical portfolio data is currently available. "
            "Portfolio history will appear after valuation snapshots "
            "have been recorded."
        )
        return False

    missing_columns = _get_missing_columns(
        history,
        REQUIRED_HISTORY_COLUMNS,
    )

    if missing_columns:
        missing_text = ", ".join(
            missing_columns
        )

        logger.warning(
            "Historical analytics could not be rendered because "
            "required columns were missing: %s",
            missing_text,
        )

        st.warning(
            "Historical portfolio analytics are unavailable because "
            f"the history data is missing: {missing_text}."
        )
        return False

    if history[DATE_COLUMN].isna().all():
        logger.warning(
            "Historical analytics received no valid dates."
        )

        st.warning(
            "Historical portfolio analytics are unavailable because "
            "the history data contains no valid dates."
        )
        return False

    if history[VALUE_COLUMN].isna().all():
        logger.warning(
            "Historical analytics received no valid portfolio values."
        )

        st.warning(
            "Historical portfolio analytics are unavailable because "
            "the history data contains no valid portfolio values."
        )
        return False

    return True


# ============================================================
# Chart Data Preparation
# ============================================================


def _prepare_history_for_chart(
    history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare normalized portfolio history for chart construction.

    The preparation is intentionally limited to presentation safety. It does
    not calculate returns, growth rates, drawdowns, or other analytics.

    Processing performed:

    - Select canonical Date and Value columns.
    - Convert Date values to pandas datetime values.
    - Convert Value values to numeric values.
    - Remove rows that cannot be plotted.
    - Sort records chronologically.
    - Keep the final record when duplicate dates are present.

    The caller's dataframe is never mutated.

    Args:
        history:
            Validated normalized portfolio history dataframe.

    Returns:
        A chart-ready dataframe containing Date and Value.

    Raises:
        ValueError:
            When no plottable records remain after preparation.
    """

    prepared = history.loc[
        :,
        [
            DATE_COLUMN,
            VALUE_COLUMN,
        ],
    ].copy()

    prepared[DATE_COLUMN] = pd.to_datetime(
        prepared[DATE_COLUMN],
        errors="coerce",
    )

    prepared[VALUE_COLUMN] = pd.to_numeric(
        prepared[VALUE_COLUMN],
        errors="coerce",
    )

    prepared = prepared.dropna(
        subset=[
            DATE_COLUMN,
            VALUE_COLUMN,
        ]
    )

    prepared = prepared.sort_values(
        by=DATE_COLUMN,
        kind="stable",
    )

    prepared = prepared.drop_duplicates(
        subset=[DATE_COLUMN],
        keep="last",
    )

    prepared = prepared.reset_index(
        drop=True
    )

    if prepared.empty:
        raise ValueError(
            "Portfolio history contains no plottable records."
        )

    return prepared


# ============================================================
# Plotly Figure Construction
# ============================================================


def build_portfolio_growth_figure(
    history: pd.DataFrame,
) -> go.Figure:
    """
    Build the historical portfolio-value growth figure.

    Separating figure construction from Streamlit rendering makes the chart
    easier to test and reuse.

    Args:
        history:
            Normalized portfolio history containing Date and Value columns.

    Returns:
        Configured Plotly figure.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.

        ValueError:
            When required columns are missing or no valid chart records exist.
    """

    if not isinstance(history, pd.DataFrame):
        raise TypeError(
            "history must be a pandas DataFrame."
        )

    missing_columns = _get_missing_columns(
        history,
        REQUIRED_HISTORY_COLUMNS,
    )

    if missing_columns:
        raise ValueError(
            "Portfolio history is missing required column(s): "
            f"{', '.join(missing_columns)}."
        )

    prepared = _prepare_history_for_chart(
        history
    )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=prepared[DATE_COLUMN],
            y=prepared[VALUE_COLUMN],
            mode="lines+markers",
            name="Portfolio Value",
            line={
                "width": 3,
            },
            marker={
                "size": 7,
            },
            hovertemplate=(
                "<b>%{x|%d %b %Y}</b><br>"
                "Portfolio Value: ₹%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        title={
            "text": PORTFOLIO_GROWTH_CHART_TITLE,
            "x": 0.01,
            "xanchor": "left",
        },
        xaxis={
            "title": "Date",
            "showgrid": False,
            "rangeslider": {
                "visible": False,
            },
        },
        yaxis={
            "title": "Portfolio Value (₹)",
            "tickprefix": "₹",
            "tickformat": ",.2f",
            "rangemode": "tozero",
        },
        hovermode="x unified",
        template="plotly_white",
        height=460,
        margin={
            "l": 20,
            "r": 20,
            "t": 70,
            "b": 20,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )

    return figure


# ============================================================
# Individual Chart Renderer
# ============================================================


def render_portfolio_growth_chart(
    history: pd.DataFrame,
) -> bool:
    """
    Render the historical portfolio-value growth chart.

    Args:
        history:
            Normalized portfolio history returned by
            PortfolioHistoryService.get_history().

    Returns:
        True when the chart is rendered.
        False when history is unavailable or cannot be rendered.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.
    """

    if not _validate_history_dataframe(
        history
    ):
        return False

    try:
        figure = build_portfolio_growth_figure(
            history
        )

    except ValueError as error:
        logger.warning(
            "Historical portfolio growth chart could not be built: %s",
            error,
        )

        st.warning(
            "Historical portfolio analytics are unavailable because "
            "the recorded history contains no valid chart data."
        )
        return False

    except Exception as error:
        logger.exception(
            "Unexpected error while building the historical "
            "portfolio growth chart."
        )

        st.error(
            "The historical portfolio growth chart could not be prepared."
        )

        with st.expander(
            "Historical chart technical details"
        ):
            st.exception(error)

        return False

    try:
        st.plotly_chart(
            figure,
            use_container_width=True,
            key=PORTFOLIO_GROWTH_CHART_KEY,
        )

    except Exception as error:
        logger.exception(
            "Unexpected error while rendering the historical "
            "portfolio growth chart."
        )

        st.error(
            "The historical portfolio growth chart could not be displayed."
        )

        with st.expander(
            "Historical chart technical details"
        ):
            st.exception(error)

        return False

    return True


# ============================================================
# Composite Historical Analytics Renderer
# ============================================================


def render_history_charts(
    history: pd.DataFrame,
) -> bool:
    """
    Render the historical portfolio analytics section.

    The current PortfolioHistoryService exposes canonical Date and Value
    columns. Therefore, Version 7.0 initially renders the portfolio-value
    timeline without reading raw CSV columns or duplicating calculations.

    Additional historical charts should be added only when their required
    datasets are exposed through an approved service or analytics adapter.

    Args:
        history:
            Normalized portfolio history returned by
            PortfolioHistoryService.get_history().

    Returns:
        True when the historical section and chart are rendered.
        False when no usable history is available.

    Raises:
        TypeError:
            When history is not a pandas DataFrame.
    """

    if not _validate_history_dataframe(
        history
    ):
        return False

    st.subheader(
        HISTORY_SECTION_TITLE
    )

    st.caption(
        "Track how the total portfolio value has changed across "
        "recorded valuation dates."
    )

    return render_portfolio_growth_chart(
        history
    )


__all__ = [
    "DATE_COLUMN",
    "HISTORY_SECTION_TITLE",
    "PORTFOLIO_GROWTH_CHART_KEY",
    "PORTFOLIO_GROWTH_CHART_TITLE",
    "REQUIRED_HISTORY_COLUMNS",
    "VALUE_COLUMN",
    "build_portfolio_growth_figure",
    "render_history_charts",
    "render_portfolio_growth_chart",
]