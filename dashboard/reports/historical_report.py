"""
Historical reporting view models and presentation helpers.

This module converts an existing HistoryAnalyticsResult into immutable,
dashboard-friendly presentation models.

Responsibilities
----------------
- Validate historical analytics results.
- Format existing historical analytics for dashboard display.
- Describe metric availability.
- Produce notes and warnings based on available service results.
- Avoid recalculating portfolio analytics.

This module performs no file access, chart construction, Streamlit rendering,
or analytics calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Final

from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)
from services.reporting.report_formatter import (
    format_currency,
    format_percentage,
)


# ============================================================
# Constants
# ============================================================

HISTORICAL_REPORT_TITLE: Final[str] = (
    "Historical Portfolio Analytics"
)

AVAILABLE_STATUS: Final[str] = "available"
PARTIAL_STATUS: Final[str] = "partial"
UNAVAILABLE_STATUS: Final[str] = "unavailable"

SUPPORTED_AVAILABILITY_STATUSES: Final[
    tuple[str, ...]
] = (
    AVAILABLE_STATUS,
    PARTIAL_STATUS,
    UNAVAILABLE_STATUS,
)

UNAVAILABLE_VALUE: Final[str] = "Unavailable"

DATE_DISPLAY_FORMAT: Final[str] = "%d %b %Y"

MINIMUM_HISTORY_OBSERVATIONS: Final[int] = 1


# ============================================================
# Exceptions
# ============================================================


class HistoricalReportError(
    RuntimeError
):
    """
    Base exception raised by historical-report presentation.
    """


class HistoricalReportValidationError(
    HistoricalReportError
):
    """
    Raised when historical-report input is invalid.
    """


# ============================================================
# Immutable View Models
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class HistoricalMetricView:
    """
    Dashboard-ready representation of one historical metric.

    Attributes:
        label:
            Human-readable metric label.

        value:
            Display-ready metric value.

        available:
            Whether the source analytics result was available.

        description:
            Optional explanatory text.
    """

    label: str
    value: str
    available: bool
    description: str = ""

    def __post_init__(
        self,
    ) -> None:
        """
        Validate the metric view after construction.
        """

        _validate_non_blank_text(
            self.label,
            parameter_name="label",
        )

        _validate_non_blank_text(
            self.value,
            parameter_name="value",
        )

        if not isinstance(
            self.available,
            bool,
        ):
            raise TypeError(
                "available must be a boolean."
            )

        if not isinstance(
            self.description,
            str,
        ):
            raise TypeError(
                "description must be a string."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class HistoricalAvailabilityView:
    """
    Availability summary for optional historical analytics.
    """

    status: str
    available_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    message: str

    def __post_init__(
        self,
    ) -> None:
        """
        Validate availability summary fields.
        """

        normalized_status = (
            _validate_availability_status(
                self.status
            )
        )

        if normalized_status != self.status:
            raise HistoricalReportValidationError(
                "status must already be normalized."
            )

        _validate_string_tuple(
            self.available_metrics,
            parameter_name="available_metrics",
        )

        _validate_string_tuple(
            self.unavailable_metrics,
            parameter_name="unavailable_metrics",
        )

        _validate_non_blank_text(
            self.message,
            parameter_name="message",
        )


@dataclass(
    frozen=True,
    slots=True,
)
class HistoricalReportView:
    """
    Complete dashboard-ready historical reporting model.
    """

    title: str
    observation_count: int
    start_date: str
    end_date: str
    duration: str

    starting_value: str
    latest_value: str
    minimum_value: str
    maximum_value: str
    average_value: str
    absolute_growth: str
    total_growth: str

    cagr: HistoricalMetricView
    maximum_drawdown: HistoricalMetricView
    annualised_volatility: HistoricalMetricView

    periodic_return_count: int
    periods_per_year: int

    availability: HistoricalAvailabilityView
    notes: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(
        self,
    ) -> None:
        """
        Validate the historical report view.
        """

        for field_name in (
            "title",
            "start_date",
            "end_date",
            "duration",
            "starting_value",
            "latest_value",
            "minimum_value",
            "maximum_value",
            "average_value",
            "absolute_growth",
            "total_growth",
        ):
            _validate_non_blank_text(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )

        _validate_non_negative_integer(
            self.observation_count,
            parameter_name="observation_count",
        )

        _validate_non_negative_integer(
            self.periodic_return_count,
            parameter_name="periodic_return_count",
        )

        _validate_positive_integer(
            self.periods_per_year,
            parameter_name="periods_per_year",
        )

        if not isinstance(
            self.cagr,
            HistoricalMetricView,
        ):
            raise TypeError(
                "cagr must be a HistoricalMetricView."
            )

        if not isinstance(
            self.maximum_drawdown,
            HistoricalMetricView,
        ):
            raise TypeError(
                "maximum_drawdown must be a HistoricalMetricView."
            )

        if not isinstance(
            self.annualised_volatility,
            HistoricalMetricView,
        ):
            raise TypeError(
                "annualised_volatility must be a HistoricalMetricView."
            )

        if not isinstance(
            self.availability,
            HistoricalAvailabilityView,
        ):
            raise TypeError(
                "availability must be a "
                "HistoricalAvailabilityView."
            )

        _validate_string_tuple(
            self.notes,
            parameter_name="notes",
        )

        _validate_string_tuple(
            self.warnings,
            parameter_name="warnings",
        )


# ============================================================
# Validation Helpers
# ============================================================


def _validate_non_blank_text(
    value: str,
    *,
    parameter_name: str,
) -> str:
    """
    Validate and normalize non-blank text.
    """

    if not isinstance(
        parameter_name,
        str,
    ):
        raise TypeError(
            "parameter_name must be a string."
        )

    normalized_parameter_name = (
        parameter_name.strip()
    )

    if not normalized_parameter_name:
        raise HistoricalReportValidationError(
            "parameter_name cannot be blank."
        )

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise HistoricalReportValidationError(
            f"{normalized_parameter_name} cannot be blank."
        )

    return normalized_value


def _validate_positive_integer(
    value: int,
    *,
    parameter_name: str,
) -> int:
    """
    Validate a positive integer.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be an integer."
        )

    if value <= 0:
        raise HistoricalReportValidationError(
            f"{normalized_parameter_name} must be greater than zero."
        )

    return value


def _validate_non_negative_integer(
    value: int,
    *,
    parameter_name: str,
) -> int:
    """
    Validate a non-negative integer.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be an integer."
        )

    if value < 0:
        raise HistoricalReportValidationError(
            f"{normalized_parameter_name} cannot be negative."
        )

    return value


def _validate_history_result(
    history: HistoryAnalyticsResult,
) -> HistoryAnalyticsResult:
    """
    Validate a historical analytics result.
    """

    if not isinstance(
        history,
        HistoryAnalyticsResult,
    ):
        raise TypeError(
            "history must be a HistoryAnalyticsResult."
        )

    if (
        isinstance(
            history.observation_count,
            bool,
        )
        or not isinstance(
            history.observation_count,
            int,
        )
    ):
        raise TypeError(
            "history.observation_count must be an integer."
        )

    if (
        history.observation_count
        < MINIMUM_HISTORY_OBSERVATIONS
    ):
        raise HistoricalReportValidationError(
            "history.observation_count must be at least one."
        )

    if not isinstance(
        history.start_date,
        date,
    ):
        raise TypeError(
            "history.start_date must be a date."
        )

    if not isinstance(
        history.end_date,
        date,
    ):
        raise TypeError(
            "history.end_date must be a date."
        )

    if (
        history.end_date
        < history.start_date
    ):
        raise HistoricalReportValidationError(
            "history.end_date cannot be earlier than "
            "history.start_date."
        )

    _validate_non_negative_integer(
        history.duration_days,
        parameter_name="history.duration_days",
    )

    _validate_positive_integer(
        history.periods_per_year,
        parameter_name="history.periods_per_year",
    )

    return history


def _validate_string_tuple(
    values: tuple[str, ...],
    *,
    parameter_name: str,
) -> tuple[str, ...]:
    """
    Validate a tuple containing non-blank strings.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if not isinstance(
        values,
        tuple,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be a tuple."
        )

    for index, value in enumerate(
        values
    ):
        _validate_non_blank_text(
            value,
            parameter_name=(
                f"{normalized_parameter_name}"
                f"[{index}]"
            ),
        )

    return values


def _validate_availability_status(
    status: str,
) -> str:
    """
    Validate and normalize an availability status.
    """

    normalized = _validate_non_blank_text(
        status,
        parameter_name="status",
    ).lower()

    if (
        normalized
        not in SUPPORTED_AVAILABILITY_STATUSES
    ):
        supported = ", ".join(
            SUPPORTED_AVAILABILITY_STATUSES
        )

        raise HistoricalReportValidationError(
            "Unsupported availability status. "
            f"Expected one of: {supported}."
        )

    return normalized


# ============================================================
# Formatting Helpers
# ============================================================


def _format_date(
    value: date,
) -> str:
    """
    Format a date for historical-report display.
    """

    if not isinstance(
        value,
        date,
    ):
        raise TypeError(
            "value must be a date."
        )

    return value.strftime(
        DATE_DISPLAY_FORMAT
    )


def _format_duration(
    duration_days: int,
) -> str:
    """
    Format a historical duration using years and days.
    """

    _validate_non_negative_integer(
        duration_days,
        parameter_name="duration_days",
    )

    if duration_days < 365:
        unit = (
            "day"
            if duration_days == 1
            else "days"
        )

        return (
            f"{duration_days:,} {unit}"
        )

    years, remaining_days = divmod(
        duration_days,
        365,
    )

    year_unit = (
        "year"
        if years == 1
        else "years"
    )

    if remaining_days == 0:
        return (
            f"{years:,} {year_unit}"
        )

    day_unit = (
        "day"
        if remaining_days == 1
        else "days"
    )

    return (
        f"{years:,} {year_unit}, "
        f"{remaining_days:,} {day_unit}"
    )


def _format_count(
    value: int,
) -> str:
    """
    Format an integer count using thousands separators.
    """

    _validate_non_negative_integer(
        value,
        parameter_name="value",
    )

    return f"{value:,}"


def _validate_finite_number(
    value: int | float,
    *,
    parameter_name: str,
) -> float:
    """
    Validate a finite numeric value.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be numeric."
        )

    numeric_value = float(
        value
    )

    if not isfinite(
        numeric_value
    ):
        raise HistoricalReportValidationError(
            f"{normalized_parameter_name} must be finite."
        )

    return numeric_value


def _format_currency_value(
    value: int | float,
    *,
    parameter_name: str,
) -> str:
    """
    Validate and format a monetary value.
    """

    numeric_value = (
        _validate_finite_number(
            value,
            parameter_name=parameter_name,
        )
    )

    return format_currency(
        numeric_value
    )


def _format_percentage_value(
    value: int | float,
    *,
    parameter_name: str,
    include_sign: bool = False,
) -> str:
    """
    Validate and format a percentage value.
    """

    if not isinstance(
        include_sign,
        bool,
    ):
        raise TypeError(
            "include_sign must be a boolean."
        )

    numeric_value = (
        _validate_finite_number(
            value,
            parameter_name=parameter_name,
        )
    )

    return format_percentage(
        numeric_value,
        include_sign=include_sign,
    )


# ============================================================
# Metric View Builders
# ============================================================


def _build_available_metric(
    *,
    label: str,
    value: str,
    description: str,
) -> HistoricalMetricView:
    """
    Build an available historical metric view.
    """

    return HistoricalMetricView(
        label=_validate_non_blank_text(
            label,
            parameter_name="label",
        ),
        value=_validate_non_blank_text(
            value,
            parameter_name="value",
        ),
        available=True,
        description=description,
    )


def _build_unavailable_metric(
    *,
    label: str,
    description: str,
) -> HistoricalMetricView:
    """
    Build an unavailable historical metric view.
    """

    return HistoricalMetricView(
        label=_validate_non_blank_text(
            label,
            parameter_name="label",
        ),
        value=UNAVAILABLE_VALUE,
        available=False,
        description=description,
    )


def _build_cagr_metric(
    history: HistoryAnalyticsResult,
) -> HistoricalMetricView:
    """
    Build the CAGR view from the existing analytics result.
    """

    if history.cagr is None:
        return _build_unavailable_metric(
            label="Historical CAGR",
            description=(
                "CAGR requires at least two observations "
                "across a valid annualisation period."
            ),
        )

    return _build_available_metric(
        label="Historical CAGR",
        value=_format_percentage_value(
            history.cagr.cagr_percent,
            parameter_name="history.cagr.cagr_percent",
            include_sign=True,
        ),
        description=(
            "Annualised growth rate calculated by the "
            "existing CAGR analytics service."
        ),
    )


def _build_drawdown_metric(
    history: HistoryAnalyticsResult,
) -> HistoricalMetricView:
    """
    Build the maximum-drawdown view.
    """

    if history.drawdown is None:
        return _build_unavailable_metric(
            label="Maximum Drawdown",
            description=(
                "Maximum drawdown requires at least "
                "two historical observations."
            ),
        )

    return _build_available_metric(
        label="Maximum Drawdown",
        value=_format_percentage_value(
            (
                history
                .drawdown
                .maximum_drawdown_percent
            ),
            parameter_name=(
                "history.drawdown."
                "maximum_drawdown_percent"
            ),
        ),
        description=(
            "Largest peak-to-trough decline calculated "
            "by the existing drawdown analytics service."
        ),
    )


def _build_volatility_metric(
    history: HistoryAnalyticsResult,
) -> HistoricalMetricView:
    """
    Build the annualised-volatility view.
    """

    if history.volatility is None:
        return _build_unavailable_metric(
            label="Annualised Volatility",
            description=(
                "Volatility requires enough periodic "
                "returns for sample-volatility analysis."
            ),
        )

    return _build_available_metric(
        label="Annualised Volatility",
        value=_format_percentage_value(
            (
                history
                .volatility
                .annualised_volatility_percent
            ),
            parameter_name=(
                "history.volatility."
                "annualised_volatility_percent"
            ),
        ),
        description=(
            "Annualised variability calculated by the "
            "existing volatility analytics service."
        ),
    )

# ============================================================
# Availability Summary
# ============================================================


def _build_availability_view(
    *,
    cagr: HistoricalMetricView,
    maximum_drawdown: HistoricalMetricView,
    annualised_volatility: HistoricalMetricView,
) -> HistoricalAvailabilityView:
    """
    Build the availability summary for optional historical metrics.
    """

    metrics = (
        cagr,
        maximum_drawdown,
        annualised_volatility,
    )

    available_metrics = tuple(
        metric.label
        for metric in metrics
        if metric.available
    )

    unavailable_metrics = tuple(
        metric.label
        for metric in metrics
        if not metric.available
    )

    available_count = len(
        available_metrics
    )

    if available_count == len(
        metrics
    ):
        status = AVAILABLE_STATUS
        message = (
            "All historical analytics metrics are available."
        )

    elif available_count == 0:
        status = UNAVAILABLE_STATUS
        message = (
            "Historical observations are available, but the optional "
            "CAGR, drawdown, and volatility metrics could not be produced."
        )

    else:
        status = PARTIAL_STATUS
        message = (
            "Historical analytics are partially available. "
            f"{available_count} of {len(metrics)} optional metrics "
            "were produced."
        )

    return HistoricalAvailabilityView(
        status=status,
        available_metrics=available_metrics,
        unavailable_metrics=unavailable_metrics,
        message=message,
    )


# ============================================================
# Notes and Warnings
# ============================================================


def _build_notes(
    history: HistoryAnalyticsResult,
    *,
    cagr: HistoricalMetricView,
    maximum_drawdown: HistoricalMetricView,
    annualised_volatility: HistoricalMetricView,
) -> tuple[str, ...]:
    """
    Build informational notes from existing historical results.
    """

    notes: list[str] = [
        (
            "Historical analytics include "
            f"{history.observation_count:,} validated portfolio "
            "valuation observations."
        ),
        (
            "The historical period covers "
            f"{_format_duration(history.duration_days)} from "
            f"{_format_date(history.start_date)} to "
            f"{_format_date(history.end_date)}."
        ),
        (
            "Volatility annualisation uses "
            f"{history.periods_per_year:,} periods per year."
        ),
    ]

    if history.periodic_returns:
        notes.append(
            (
                f"{len(history.periodic_returns):,} periodic return "
                "observations were supplied by the historical "
                "analytics service."
            )
        )
    else:
        notes.append(
            (
                "No periodic return observations were available for "
                "display."
            )
        )

    available_labels = tuple(
        metric.label
        for metric in (
            cagr,
            maximum_drawdown,
            annualised_volatility,
        )
        if metric.available
    )

    if available_labels:
        notes.append(
            (
                "Available optional metrics: "
                f"{', '.join(available_labels)}."
            )
        )

    return tuple(
        notes
    )


def _build_warnings(
    history: HistoryAnalyticsResult,
    *,
    cagr: HistoricalMetricView,
    maximum_drawdown: HistoricalMetricView,
    annualised_volatility: HistoricalMetricView,
) -> tuple[str, ...]:
    """
    Build presentation warnings without recalculating analytics.
    """

    warnings: list[str] = []

    unavailable_metrics = tuple(
        metric
        for metric in (
            cagr,
            maximum_drawdown,
            annualised_volatility,
        )
        if not metric.available
    )

    for metric in unavailable_metrics:
        warnings.append(
            (
                f"{metric.label} is unavailable. "
                f"{metric.description}"
            )
        )

    if history.observation_count < 3:
        warnings.append(
            (
                "The historical dataset contains fewer than three "
                "observations, so volatility analysis may be unavailable."
            )
        )

    if history.duration_days == 0:
        warnings.append(
            (
                "The first and latest observations occur on the same "
                "calendar date."
            )
        )

    if history.total_growth_percent < 0:
        warnings.append(
            (
                "The portfolio value declined over the selected "
                "historical period."
            )
        )

    if (
        history.drawdown is not None
        and (
            history
            .drawdown
            .maximum_drawdown_percent
        ) < -20.0
    ):
        warnings.append(
            (
                "The historical maximum drawdown exceeded 20 percent, "
                "indicating a material peak-to-trough decline."
            )
        )

    return tuple(
        warnings
    )


# ============================================================
# Historical Report View Builder
# ============================================================


def build_historical_report_view(
    history: HistoryAnalyticsResult,
    *,
    title: str = HISTORICAL_REPORT_TITLE,
) -> HistoricalReportView:
    """
    Convert an existing HistoryAnalyticsResult into a presentation model.

    This function performs no analytics calculations. It only validates,
    formats, and organizes values already produced by HistoryAnalyticsService.

    Args:
        history:
            Existing historical analytics result.

        title:
            Dashboard section title.

    Returns:
        Immutable HistoricalReportView.
    """

    validated_history = (
        _validate_history_result(
            history
        )
    )

    normalized_title = (
        _validate_non_blank_text(
            title,
            parameter_name="title",
        )
    )

    starting_value = (
        _format_currency_value(
            validated_history.starting_value,
            parameter_name=(
                "history.starting_value"
            ),
        )
    )

    latest_value = (
        _format_currency_value(
            validated_history.latest_value,
            parameter_name=(
                "history.latest_value"
            ),
        )
    )

    minimum_value = (
        _format_currency_value(
            validated_history.minimum_value,
            parameter_name=(
                "history.minimum_value"
            ),
        )
    )

    maximum_value = (
        _format_currency_value(
            validated_history.maximum_value,
            parameter_name=(
                "history.maximum_value"
            ),
        )
    )

    average_value = (
        _format_currency_value(
            validated_history.average_value,
            parameter_name=(
                "history.average_value"
            ),
        )
    )

    absolute_growth = (
        _format_currency_value(
            validated_history.absolute_growth,
            parameter_name=(
                "history.absolute_growth"
            ),
        )
    )

    total_growth = (
        _format_percentage_value(
            validated_history.total_growth_percent,
            parameter_name=(
                "history.total_growth_percent"
            ),
            include_sign=True,
        )
    )

    cagr = _build_cagr_metric(
        validated_history
    )

    maximum_drawdown = (
        _build_drawdown_metric(
            validated_history
        )
    )

    annualised_volatility = (
        _build_volatility_metric(
            validated_history
        )
    )

    availability = (
        _build_availability_view(
            cagr=cagr,
            maximum_drawdown=maximum_drawdown,
            annualised_volatility=(
                annualised_volatility
            ),
        )
    )

    notes = _build_notes(
        validated_history,
        cagr=cagr,
        maximum_drawdown=maximum_drawdown,
        annualised_volatility=(
            annualised_volatility
        ),
    )

    warnings = _build_warnings(
        validated_history,
        cagr=cagr,
        maximum_drawdown=maximum_drawdown,
        annualised_volatility=(
            annualised_volatility
        ),
    )

    return HistoricalReportView(
        title=normalized_title,
        observation_count=(
            validated_history
            .observation_count
        ),
        start_date=_format_date(
            validated_history.start_date
        ),
        end_date=_format_date(
            validated_history.end_date
        ),
        duration=_format_duration(
            validated_history.duration_days
        ),
        starting_value=starting_value,
        latest_value=latest_value,
        minimum_value=minimum_value,
        maximum_value=maximum_value,
        average_value=average_value,
        absolute_growth=absolute_growth,
        total_growth=total_growth,
        cagr=cagr,
        maximum_drawdown=maximum_drawdown,
        annualised_volatility=(
            annualised_volatility
        ),
        periodic_return_count=len(
            validated_history.periodic_returns
        ),
        periods_per_year=(
            validated_history
            .periods_per_year
        ),
        availability=availability,
        notes=notes,
        warnings=warnings,
    )


# ============================================================
# Dashboard Adapters
# ============================================================


def get_historical_metric_cards(
    view: HistoricalReportView,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return core historical metrics for dashboard metric cards.
    """

    if not isinstance(
        view,
        HistoricalReportView,
    ):
        raise TypeError(
            "view must be a HistoricalReportView."
        )

    return (
        (
            "Starting Value",
            view.starting_value,
        ),
        (
            "Latest Value",
            view.latest_value,
        ),
        (
            "Absolute Growth",
            view.absolute_growth,
        ),
        (
            "Total Growth",
            view.total_growth,
        ),
        (
            "Historical CAGR",
            view.cagr.value,
        ),
        (
            "Maximum Drawdown",
            view.maximum_drawdown.value,
        ),
        (
            "Annualised Volatility",
            view.annualised_volatility.value,
        ),
        (
            "Observations",
            _format_count(
                view.observation_count
            ),
        ),
    )


def get_historical_summary_rows(
    view: HistoricalReportView,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return formatted historical summary rows for tables or expanders.
    """

    if not isinstance(
        view,
        HistoricalReportView,
    ):
        raise TypeError(
            "view must be a HistoricalReportView."
        )

    return (
        (
            "Start Date",
            view.start_date,
        ),
        (
            "End Date",
            view.end_date,
        ),
        (
            "Duration",
            view.duration,
        ),
        (
            "Starting Value",
            view.starting_value,
        ),
        (
            "Latest Value",
            view.latest_value,
        ),
        (
            "Minimum Value",
            view.minimum_value,
        ),
        (
            "Maximum Value",
            view.maximum_value,
        ),
        (
            "Average Value",
            view.average_value,
        ),
        (
            "Absolute Growth",
            view.absolute_growth,
        ),
        (
            "Total Growth",
            view.total_growth,
        ),
        (
            "Historical CAGR",
            view.cagr.value,
        ),
        (
            "Maximum Drawdown",
            view.maximum_drawdown.value,
        ),
        (
            "Annualised Volatility",
            view.annualised_volatility.value,
        ),
        (
            "Periodic Returns",
            _format_count(
                view.periodic_return_count
            ),
        ),
        (
            "Periods Per Year",
            _format_count(
                view.periods_per_year
            ),
        ),
    )


def get_historical_availability_rows(
    view: HistoricalReportView,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return availability information for dashboard presentation.
    """

    if not isinstance(
        view,
        HistoricalReportView,
    ):
        raise TypeError(
            "view must be a HistoricalReportView."
        )

    available_metrics = (
        ", ".join(
            view
            .availability
            .available_metrics
        )
        if (
            view
            .availability
            .available_metrics
        )
        else "None"
    )

    unavailable_metrics = (
        ", ".join(
            view
            .availability
            .unavailable_metrics
        )
        if (
            view
            .availability
            .unavailable_metrics
        )
        else "None"
    )

    return (
        (
            "Status",
            view.availability.status.title(),
        ),
        (
            "Available Metrics",
            available_metrics,
        ),
        (
            "Unavailable Metrics",
            unavailable_metrics,
        ),
        (
            "Summary",
            view.availability.message,
        ),
    )


# ============================================================
# Convenience API
# ============================================================


def prepare_historical_report(
    history: HistoryAnalyticsResult,
    *,
    title: str = HISTORICAL_REPORT_TITLE,
) -> HistoricalReportView:
    """
    Prepare a dashboard-ready historical report view.
    """

    return build_historical_report_view(
        history,
        title=title,
    )


# ============================================================
# Public Exports
# ============================================================

__all__ = [
    "AVAILABLE_STATUS",
    "DATE_DISPLAY_FORMAT",
    "HISTORICAL_REPORT_TITLE",
    "MINIMUM_HISTORY_OBSERVATIONS",
    "PARTIAL_STATUS",
    "SUPPORTED_AVAILABILITY_STATUSES",
    "UNAVAILABLE_STATUS",
    "UNAVAILABLE_VALUE",
    "HistoricalAvailabilityView",
    "HistoricalMetricView",
    "HistoricalReportError",
    "HistoricalReportValidationError",
    "HistoricalReportView",
    "build_historical_report_view",
    "get_historical_availability_rows",
    "get_historical_metric_cards",
    "get_historical_summary_rows",
    "prepare_historical_report",
]