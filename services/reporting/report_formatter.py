"""
Portfolio report formatting and assembly service.

This module assembles existing analytics results into a typed PortfolioReport.

Responsibilities
----------------
- Validate report metadata and source analytics models.
- Normalize optional AI summary data.
- Normalize report notes and warnings.
- Build immutable PortfolioReport objects.
- Provide reusable display-formatting helpers for future PDF and Excel exports.

This module does not:

- Load portfolio data.
- Calculate portfolio analytics.
- Access Streamlit.
- Generate PDF or Excel files.
- Read or write files.

All portfolio calculations remain owned by the existing analytics services.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Final

from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)
from services.analytics.performance import (
    PortfolioPerformanceMetrics,
)
from services.reporting.report_models import (
    PortfolioReport,
    ReportMetadata,
)


# ============================================================
# Constants
# ============================================================

DEFAULT_REPORT_TITLE: Final[str] = (
    "Professional Portfolio Report"
)

DEFAULT_REPORT_VERSION: Final[str] = "8.0.0"

DEFAULT_APPLICATION_NAME: Final[str] = (
    "AI Mutual Fund Assistant"
)

CURRENCY_SYMBOL: Final[str] = "₹"

UNAVAILABLE_VALUE: Final[str] = "Unavailable"


# ============================================================
# Exceptions
# ============================================================


class ReportFormatterError(RuntimeError):
    """
    Base exception raised by the report formatter.
    """


class ReportFormatterValidationError(
    ReportFormatterError
):
    """
    Raised when report formatter input is invalid.
    """


# ============================================================
# Primitive Validation
# ============================================================


def _validate_non_empty_string(
    value: str,
    field_name: str,
) -> str:
    """
    Validate and normalize a required text value.

    Args:
        value:
            Text value to validate.

        field_name:
            Human-readable field name used in validation errors.

    Returns:
        Stripped text value.

    Raises:
        TypeError:
            When value or field_name is not a string.

        ReportFormatterValidationError:
            When value or field_name is blank.
    """

    if not isinstance(
        field_name,
        str,
    ):
        raise TypeError(
            "field_name must be a string."
        )

    normalized_field_name = field_name.strip()

    if not normalized_field_name:
        raise ReportFormatterValidationError(
            "field_name cannot be blank."
        )

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{normalized_field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ReportFormatterValidationError(
            f"{normalized_field_name} cannot be blank."
        )

    return normalized_value


def _validate_generated_at(
    generated_at: datetime,
) -> datetime:
    """
    Validate a report-generation timestamp.

    Naive datetimes are interpreted as UTC so all report metadata remains
    timezone-aware and consistent across exporters.

    Args:
        generated_at:
            Datetime associated with report generation.

    Returns:
        Timezone-aware datetime.

    Raises:
        TypeError:
            When generated_at is not a datetime.
    """

    if not isinstance(
        generated_at,
        datetime,
    ):
        raise TypeError(
            "generated_at must be a datetime."
        )

    if generated_at.tzinfo is None:
        return generated_at.replace(
            tzinfo=timezone.utc
        )

    return generated_at


# ============================================================
# Collection Normalization
# ============================================================


def _normalize_text_collection(
    values: Iterable[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    """
    Normalize report notes or warnings.

    Blank values are removed while input ordering is preserved. Duplicate
    entries are removed using first-occurrence ordering.

    Args:
        values:
            Optional iterable containing text values.

        field_name:
            Field name used in validation errors.

    Returns:
        Immutable tuple of unique normalized strings.

    Raises:
        TypeError:
            When values is a string, bytes object, non-iterable, or contains
            non-string elements.
    """

    if values is None:
        return ()

    if isinstance(
        values,
        (str, bytes),
    ):
        raise TypeError(
            f"{field_name} must be an iterable of strings."
        )

    try:
        items = tuple(values)

    except TypeError as error:
        raise TypeError(
            f"{field_name} must be an iterable of strings."
        ) from error

    normalized: list[str] = []
    seen: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(
            item,
            str,
        ):
            raise TypeError(
                f"{field_name}[{index}] must be a string."
            )

        text = item.strip()

        if not text or text in seen:
            continue

        seen.add(text)
        normalized.append(text)

    return tuple(normalized)


def _normalize_ai_summary(
    ai_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    Normalize optional AI-report content.

    A shallow copy is returned so callers cannot mutate the resulting report
    by later changing the original mapping.

    Keys must be non-blank strings. Values are intentionally unrestricted
    because existing AI services may expose text, lists, numeric scores, or
    nested serializable structures.

    Args:
        ai_summary:
            Optional AI summary mapping.

    Returns:
        Independent dictionary with normalized string keys.

    Raises:
        TypeError:
            When ai_summary is not a mapping or contains non-string keys.

        ReportFormatterValidationError:
            When a key is blank.
    """

    if ai_summary is None:
        return {}

    if not isinstance(
        ai_summary,
        Mapping,
    ):
        raise TypeError(
            "ai_summary must be a mapping."
        )

    normalized: dict[str, Any] = {}

    for key, value in ai_summary.items():
        if not isinstance(
            key,
            str,
        ):
            raise TypeError(
                "ai_summary keys must be strings."
            )

        normalized_key = key.strip()

        if not normalized_key:
            raise ReportFormatterValidationError(
                "ai_summary keys cannot be blank."
            )

        normalized[normalized_key] = value

    return normalized


# ============================================================
# Existing Result Validation
# ============================================================


def _validate_performance(
    performance: PortfolioPerformanceMetrics,
) -> PortfolioPerformanceMetrics:
    """
    Validate the required portfolio-performance result.
    """

    if not isinstance(
        performance,
        PortfolioPerformanceMetrics,
    ):
        raise TypeError(
            "performance must be a PortfolioPerformanceMetrics."
        )

    return performance


def _validate_history(
    history: HistoryAnalyticsResult | None,
) -> HistoryAnalyticsResult | None:
    """
    Validate the optional historical analytics result.
    """

    if history is not None and not isinstance(
        history,
        HistoryAnalyticsResult,
    ):
        raise TypeError(
            "history must be a HistoryAnalyticsResult or None."
        )

    return history


def _validate_advanced_analytics(
    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ),
) -> AdvancedAnalyticsServiceResult | None:
    """
    Validate the optional advanced analytics result.
    """

    if (
        advanced_analytics is not None
        and not isinstance(
            advanced_analytics,
            AdvancedAnalyticsServiceResult,
        )
    ):
        raise TypeError(
            "advanced_analytics must be an "
            "AdvancedAnalyticsServiceResult or None."
        )

    return advanced_analytics


# ============================================================
# Report Metadata
# ============================================================


def build_report_metadata(
    *,
    title: str = DEFAULT_REPORT_TITLE,
    version: str = DEFAULT_REPORT_VERSION,
    generated_at: datetime | None = None,
    application_name: str = DEFAULT_APPLICATION_NAME,
) -> ReportMetadata:
    """
    Build validated report metadata.

    Args:
        title:
            Human-readable report title.

        version:
            Report schema or application version.

        generated_at:
            Optional generation timestamp. Current UTC time is used when
            omitted.

        application_name:
            Application that generated the report.

    Returns:
        Immutable ReportMetadata instance.
    """

    resolved_generated_at = (
        datetime.now(
            timezone.utc
        )
        if generated_at is None
        else _validate_generated_at(
            generated_at
        )
    )

    return ReportMetadata(
        title=_validate_non_empty_string(
            title,
            "title",
        ),
        version=_validate_non_empty_string(
            version,
            "version",
        ),
        generated_at=resolved_generated_at,
        application_name=_validate_non_empty_string(
            application_name,
            "application_name",
        ),
    )


# ============================================================
# Portfolio Report Assembly
# ============================================================


def build_portfolio_report(
    *,
    performance: PortfolioPerformanceMetrics,
    history: HistoryAnalyticsResult | None = None,
    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ) = None,
    ai_summary: Mapping[str, Any] | None = None,
    notes: Iterable[str] | None = None,
    warnings: Iterable[str] | None = None,
    metadata: ReportMetadata | None = None,
    title: str = DEFAULT_REPORT_TITLE,
    version: str = DEFAULT_REPORT_VERSION,
    generated_at: datetime | None = None,
    application_name: str = DEFAULT_APPLICATION_NAME,
) -> PortfolioReport:
    """
    Build a complete immutable portfolio report.

    The function aggregates results already produced by portfolio analytics
    services. It performs no financial calculations.

    When explicit metadata is supplied, title, version, generated_at, and
    application_name are ignored because the caller-provided metadata is
    treated as authoritative.

    Args:
        performance:
            Required portfolio-performance result.

        history:
            Optional historical analytics result.

        advanced_analytics:
            Optional advanced analytics service result.

        ai_summary:
            Optional AI insight mapping.

        notes:
            Optional report notes.

        warnings:
            Optional report warnings.

        metadata:
            Optional prebuilt metadata.

        title:
            Report title used when metadata is omitted.

        version:
            Report version used when metadata is omitted.

        generated_at:
            Generation timestamp used when metadata is omitted.

        application_name:
            Application name used when metadata is omitted.

    Returns:
        Immutable PortfolioReport instance.

    Raises:
        TypeError:
            When typed analytics results or collections have invalid types.

        ReportFormatterValidationError:
            When required text fields are blank.
    """

    validated_performance = _validate_performance(
        performance
    )

    validated_history = _validate_history(
        history
    )

    validated_advanced_analytics = (
        _validate_advanced_analytics(
            advanced_analytics
        )
    )

    if metadata is None:
        resolved_metadata = build_report_metadata(
            title=title,
            version=version,
            generated_at=generated_at,
            application_name=application_name,
        )

    else:
        if not isinstance(
            metadata,
            ReportMetadata,
        ):
            raise TypeError(
                "metadata must be a ReportMetadata or None."
            )

        resolved_metadata = metadata

    return PortfolioReport(
        metadata=resolved_metadata,
        performance=validated_performance,
        history=validated_history,
        advanced_analytics=(
            validated_advanced_analytics
        ),
        ai_summary=_normalize_ai_summary(
            ai_summary
        ),
        notes=_normalize_text_collection(
            notes,
            "notes",
        ),
        warnings=_normalize_text_collection(
            warnings,
            "warnings",
        ),
    )


# ============================================================
# Display Formatting Helpers
# ============================================================


def format_currency(
    value: float | int,
    *,
    symbol: str = CURRENCY_SYMBOL,
) -> str:
    """
    Format a finite numeric value as currency.

    Args:
        value:
            Numeric currency value.

        symbol:
            Currency symbol or prefix.

    Returns:
        Currency-formatted string.

    Raises:
        TypeError:
            When value is non-numeric or symbol is not a string.

        ReportFormatterValidationError:
            When symbol is blank or value is not finite.
    """

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            "value must be numeric."
        )

    if not isinstance(
        symbol,
        str,
    ):
        raise TypeError(
            "symbol must be a string."
        )

    normalized_symbol = symbol.strip()

    if not normalized_symbol:
        raise ReportFormatterValidationError(
            "symbol cannot be blank."
        )

    numeric_value = float(value)

    if not isfinite(
        numeric_value
    ):
        raise ReportFormatterValidationError(
            "value must be finite."
        )

    return (
        f"{normalized_symbol}"
        f"{numeric_value:,.2f}"
    )


def format_percentage(
    value: float | int | None,
    *,
    include_sign: bool = False,
    unavailable_value: str = UNAVAILABLE_VALUE,
) -> str:
    """
    Format a percentage-point value for reports.

    Args:
        value:
            Percentage-point value. None represents unavailable analytics.

        include_sign:
            Whether positive and zero values should include a leading plus.

        unavailable_value:
            Text displayed when value is None.

    Returns:
        Formatted percentage or unavailable label.
    """

    if not isinstance(
        include_sign,
        bool,
    ):
        raise TypeError(
            "include_sign must be a boolean."
        )

    normalized_unavailable = (
        _validate_non_empty_string(
            unavailable_value,
            "unavailable_value",
        )
    )

    if value is None:
        return normalized_unavailable

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            "value must be numeric or None."
        )

    numeric_value = float(value)

    if not isfinite(
        numeric_value
    ):
        raise ReportFormatterValidationError(
            "value must be finite."
        )

    format_specifier = (
        "+.2f"
        if include_sign
        else ".2f"
    )

    return (
        f"{numeric_value:{format_specifier}}%"
    )


def format_datetime(
    value: datetime,
) -> str:
    """
    Format a report timestamp for human-readable output.

    Args:
        value:
            Datetime to format.

    Returns:
        Timestamp in ``DD Mon YYYY, HH:MM UTC`` format.
    """

    validated = _validate_generated_at(
        value
    )

    utc_value = validated.astimezone(
        timezone.utc
    )

    return utc_value.strftime(
        "%d %b %Y, %H:%M UTC"
    )


# ============================================================
# Convenience Formatter
# ============================================================


class PortfolioReportFormatter:
    """
    Stateless portfolio-report assembler.

    This class provides an object-oriented API for dependency injection while
    delegating to the module-level formatting functions.
    """

    def build(
        self,
        *,
        performance: PortfolioPerformanceMetrics,
        history: HistoryAnalyticsResult | None = None,
        advanced_analytics: (
            AdvancedAnalyticsServiceResult | None
        ) = None,
        ai_summary: Mapping[str, Any] | None = None,
        notes: Iterable[str] | None = None,
        warnings: Iterable[str] | None = None,
        metadata: ReportMetadata | None = None,
        title: str = DEFAULT_REPORT_TITLE,
        version: str = DEFAULT_REPORT_VERSION,
        generated_at: datetime | None = None,
        application_name: str = DEFAULT_APPLICATION_NAME,
    ) -> PortfolioReport:
        """
        Build a PortfolioReport using validated existing analytics results.
        """

        return build_portfolio_report(
            performance=performance,
            history=history,
            advanced_analytics=advanced_analytics,
            ai_summary=ai_summary,
            notes=notes,
            warnings=warnings,
            metadata=metadata,
            title=title,
            version=version,
            generated_at=generated_at,
            application_name=application_name,
        )


__all__ = [
    "CURRENCY_SYMBOL",
    "DEFAULT_APPLICATION_NAME",
    "DEFAULT_REPORT_TITLE",
    "DEFAULT_REPORT_VERSION",
    "PortfolioReportFormatter",
    "ReportFormatterError",
    "ReportFormatterValidationError",
    "UNAVAILABLE_VALUE",
    "build_portfolio_report",
    "build_report_metadata",
    "format_currency",
    "format_datetime",
    "format_percentage",
]