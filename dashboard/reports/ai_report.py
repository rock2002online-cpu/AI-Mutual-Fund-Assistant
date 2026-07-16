"""
AI portfolio reporting view models and presentation helpers.

This module converts existing PortfolioInsights output into immutable,
dashboard-friendly presentation models.

Responsibilities
----------------
- Validate existing AI portfolio insight output.
- Normalize recommendation and summary content.
- Format portfolio metrics for dashboard display.
- Build immutable view models for the Reports page.
- Avoid recalculating any portfolio analytics.

This module performs no file access, Streamlit rendering, portfolio loading,
or direct AI/LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Final, Mapping, Sequence

from services.ai.insights import PortfolioInsights
from services.reporting.report_formatter import (
    format_currency,
    format_percentage,
)


# ============================================================
# Constants
# ============================================================

AI_REPORT_TITLE: Final[str] = (
    "AI Portfolio Insights"
)

SUCCESS_RECOMMENDATION: Final[str] = (
    "success"
)

INFO_RECOMMENDATION: Final[str] = (
    "info"
)

WARNING_RECOMMENDATION: Final[str] = (
    "warning"
)

ERROR_RECOMMENDATION: Final[str] = (
    "error"
)

SUPPORTED_RECOMMENDATION_TYPES: Final[
    tuple[str, ...]
] = (
    SUCCESS_RECOMMENDATION,
    INFO_RECOMMENDATION,
    WARNING_RECOMMENDATION,
    ERROR_RECOMMENDATION,
)

UNAVAILABLE_VALUE: Final[str] = "Unavailable"
UNKNOWN_FUND_NAME: Final[str] = "N/A"


# ============================================================
# Exceptions
# ============================================================


class AIReportError(
    RuntimeError
):
    """
    Base exception raised by AI-report presentation.
    """


class AIReportValidationError(
    AIReportError
):
    """
    Raised when AI-report input is invalid.
    """


# ============================================================
# Immutable View Models
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class AIRecommendationView:
    """
    Dashboard-ready AI recommendation.

    Attributes:
        recommendation_type:
            Normalized recommendation severity.

        message:
            Human-readable recommendation text.

        icon:
            Display icon associated with the severity.

        label:
            Human-readable severity label.
    """

    recommendation_type: str
    message: str
    icon: str
    label: str

    def __post_init__(
        self,
    ) -> None:
        """
        Validate recommendation fields.
        """

        normalized_type = (
            _validate_recommendation_type(
                self.recommendation_type
            )
        )

        if normalized_type != self.recommendation_type:
            raise AIReportValidationError(
                "recommendation_type must already be normalized."
            )

        for field_name in (
            "message",
            "icon",
            "label",
        ):
            _validate_non_blank_text(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )


@dataclass(
    frozen=True,
    slots=True,
)
class AIMetricView:
    """
    Dashboard-ready AI portfolio metric.
    """

    label: str
    value: str
    description: str = ""

    def __post_init__(
        self,
    ) -> None:
        """
        Validate metric fields.
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
class AIHoldingView:
    """
    Dashboard-ready important-holding summary.
    """

    label: str
    fund_name: str
    available: bool

    def __post_init__(
        self,
    ) -> None:
        """
        Validate holding fields.
        """

        _validate_non_blank_text(
            self.label,
            parameter_name="label",
        )

        _validate_non_blank_text(
            self.fund_name,
            parameter_name="fund_name",
        )

        if not isinstance(
            self.available,
            bool,
        ):
            raise TypeError(
                "available must be a boolean."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class AIReportView:
    """
    Complete dashboard-ready AI portfolio report view.
    """

    title: str
    executive_summary: str

    portfolio_value: str
    invested_value: str
    gain_loss: str
    gain_percent: str

    health_score: str
    risk_level: str
    diversification_score: str
    concentration: str

    top_holding: AIHoldingView
    worst_holding: AIHoldingView

    recommendations: tuple[
        AIRecommendationView,
        ...
    ]

    notes: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(
        self,
    ) -> None:
        """
        Validate the complete AI report view.
        """

        for field_name in (
            "title",
            "executive_summary",
            "portfolio_value",
            "invested_value",
            "gain_loss",
            "gain_percent",
            "health_score",
            "risk_level",
            "diversification_score",
            "concentration",
        ):
            _validate_non_blank_text(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )

        if not isinstance(
            self.top_holding,
            AIHoldingView,
        ):
            raise TypeError(
                "top_holding must be an AIHoldingView."
            )

        if not isinstance(
            self.worst_holding,
            AIHoldingView,
        ):
            raise TypeError(
                "worst_holding must be an AIHoldingView."
            )

        if not isinstance(
            self.recommendations,
            tuple,
        ):
            raise TypeError(
                "recommendations must be a tuple."
            )

        for index, recommendation in enumerate(
            self.recommendations
        ):
            if not isinstance(
                recommendation,
                AIRecommendationView,
            ):
                raise TypeError(
                    "recommendations"
                    f"[{index}] must be an "
                    "AIRecommendationView."
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
        raise AIReportValidationError(
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
        raise AIReportValidationError(
            f"{normalized_parameter_name} cannot be blank."
        )

    return normalized_value


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
        raise AIReportValidationError(
            f"{normalized_parameter_name} must be finite."
        )

    return numeric_value


def _validate_summary_mapping(
    summary: Mapping[str, Any],
) -> Mapping[str, Any]:
    """
    Validate a PortfolioInsights summary mapping.
    """

    if not isinstance(
        summary,
        Mapping,
    ):
        raise TypeError(
            "summary must be a mapping."
        )

    required_keys = (
        "portfolio_value",
        "invested_value",
        "gain_loss",
        "gain_percent",
        "health_score",
        "risk_level",
        "diversification_score",
        "concentration",
        "executive_summary",
        "recommendations",
    )

    missing_keys = tuple(
        key
        for key in required_keys
        if key not in summary
    )

    if missing_keys:
        raise AIReportValidationError(
            "summary is missing required key(s): "
            f"{', '.join(missing_keys)}."
        )

    return summary


def _validate_recommendation_type(
    recommendation_type: str,
) -> str:
    """
    Validate and normalize recommendation severity.
    """

    normalized = _validate_non_blank_text(
        recommendation_type,
        parameter_name="recommendation_type",
    ).lower()

    if (
        normalized
        not in SUPPORTED_RECOMMENDATION_TYPES
    ):
        supported = ", ".join(
            SUPPORTED_RECOMMENDATION_TYPES
        )

        raise AIReportValidationError(
            "Unsupported recommendation type. "
            f"Expected one of: {supported}."
        )

    return normalized


# ============================================================
# Formatting Helpers
# ============================================================


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


def _format_score(
    value: int | float,
    *,
    parameter_name: str,
    maximum: int = 100,
) -> str:
    """
    Format a score using ``value/maximum`` notation.
    """

    numeric_value = (
        _validate_finite_number(
            value,
            parameter_name=parameter_name,
        )
    )

    if isinstance(
        maximum,
        bool,
    ) or not isinstance(
        maximum,
        int,
    ):
        raise TypeError(
            "maximum must be an integer."
        )

    if maximum <= 0:
        raise AIReportValidationError(
            "maximum must be greater than zero."
        )

    return (
        f"{numeric_value:.1f}/{maximum}"
    )


def _normalise_fund_name(
    value: Any,
) -> str:
    """
    Normalize a fund name from existing insight output.
    """

    if value is None:
        return UNKNOWN_FUND_NAME

    normalized = str(
        value
    ).strip()

    if not normalized:
        return UNKNOWN_FUND_NAME

    return normalized


# ============================================================
# Recommendation Metadata
# ============================================================


def _recommendation_icon(
    recommendation_type: str,
) -> str:
    """
    Return the dashboard icon for a recommendation type.
    """

    normalized = (
        _validate_recommendation_type(
            recommendation_type
        )
    )

    icons = {
        SUCCESS_RECOMMENDATION: "✅",
        INFO_RECOMMENDATION: "ℹ️",
        WARNING_RECOMMENDATION: "⚠️",
        ERROR_RECOMMENDATION: "🚨",
    }

    return icons[
        normalized
    ]


def _recommendation_label(
    recommendation_type: str,
) -> str:
    """
    Return a human-readable recommendation label.
    """

    normalized = (
        _validate_recommendation_type(
            recommendation_type
        )
    )

    labels = {
        SUCCESS_RECOMMENDATION: "Positive",
        INFO_RECOMMENDATION: "Information",
        WARNING_RECOMMENDATION: "Review",
        ERROR_RECOMMENDATION: "Critical",
    }

    return labels[
        normalized
    ]


def _build_recommendation_view(
    recommendation: Mapping[str, Any],
) -> AIRecommendationView:
    """
    Build one recommendation presentation model.
    """

    if not isinstance(
        recommendation,
        Mapping,
    ):
        raise TypeError(
            "recommendation must be a mapping."
        )

    if "type" not in recommendation:
        raise AIReportValidationError(
            "recommendation is missing required key: type."
        )

    if "message" not in recommendation:
        raise AIReportValidationError(
            "recommendation is missing required key: message."
        )

    recommendation_type = (
        _validate_recommendation_type(
            recommendation["type"]
        )
    )

    message = _validate_non_blank_text(
        recommendation["message"],
        parameter_name="recommendation message",
    )

    return AIRecommendationView(
        recommendation_type=(
            recommendation_type
        ),
        message=message,
        icon=_recommendation_icon(
            recommendation_type
        ),
        label=_recommendation_label(
            recommendation_type
        ),
    )

# ============================================================
# Recommendation Collection Normalization
# ============================================================


def _normalise_recommendations(
    recommendations: Sequence[
        Mapping[str, Any]
    ],
) -> tuple[
    AIRecommendationView,
    ...,
]:
    """
    Normalize existing PortfolioInsights recommendation output.
    """

    if isinstance(
        recommendations,
        (str, bytes, bytearray),
    ) or not isinstance(
        recommendations,
        Sequence,
    ):
        raise TypeError(
            "recommendations must be a sequence."
        )

    return tuple(
        _build_recommendation_view(
            recommendation
        )
        for recommendation in recommendations
    )


# ============================================================
# Holding Builders
# ============================================================


def _build_holding_view(
    *,
    label: str,
    fund_name: Any,
) -> AIHoldingView:
    """
    Build a dashboard-ready important-holding view.
    """

    normalized_label = (
        _validate_non_blank_text(
            label,
            parameter_name="label",
        )
    )

    normalized_fund_name = (
        _normalise_fund_name(
            fund_name
        )
    )

    return AIHoldingView(
        label=normalized_label,
        fund_name=normalized_fund_name,
        available=(
            normalized_fund_name
            != UNKNOWN_FUND_NAME
        ),
    )


# ============================================================
# Notes and Warnings
# ============================================================


def _build_notes(
    summary: Mapping[str, Any],
    recommendations: tuple[
        AIRecommendationView,
        ...,
    ],
) -> tuple[str, ...]:
    """
    Build informational notes from existing AI-insight output.
    """

    notes = [
        (
            "AI portfolio insights were generated from the "
            "current portfolio snapshot."
        ),
        (
            "The report includes "
            f"{len(recommendations):,} recommendation"
            f"{'' if len(recommendations) == 1 else 's'}."
        ),
        (
            "Portfolio Health Score: "
            f"{_format_score(
                summary['health_score'],
                parameter_name='summary.health_score',
            )}."
        ),
        (
            "Diversification Score: "
            f"{_format_score(
                summary['diversification_score'],
                parameter_name=(
                    'summary.diversification_score'
                ),
            )}."
        ),
    ]

    return tuple(
        notes
    )


def _build_warnings(
    summary: Mapping[str, Any],
    recommendations: tuple[
        AIRecommendationView,
        ...,
    ],
) -> tuple[str, ...]:
    """
    Build report warnings from existing insight results.

    No portfolio metrics are recalculated.
    """

    warnings: list[str] = []

    gain_percent = (
        _validate_finite_number(
            summary["gain_percent"],
            parameter_name=(
                "summary.gain_percent"
            ),
        )
    )

    concentration = (
        _validate_finite_number(
            summary["concentration"],
            parameter_name=(
                "summary.concentration"
            ),
        )
    )

    health_score = (
        _validate_finite_number(
            summary["health_score"],
            parameter_name=(
                "summary.health_score"
            ),
        )
    )

    if gain_percent < 0:
        warnings.append(
            (
                "The portfolio currently has a negative "
                "overall return."
            )
        )

    if concentration >= 50:
        warnings.append(
            (
                "The largest holding represents at least half "
                "of the portfolio, indicating high "
                "concentration risk."
            )
        )

    elif concentration >= 35:
        warnings.append(
            (
                "The portfolio has moderate concentration risk."
            )
        )

    if health_score < 50:
        warnings.append(
            (
                "The Portfolio Health Score is below 50 and may "
                "require closer review."
            )
        )

    critical_recommendations = tuple(
        recommendation
        for recommendation in recommendations
        if recommendation.recommendation_type
        == ERROR_RECOMMENDATION
    )

    if critical_recommendations:
        warnings.append(
            (
                f"{len(critical_recommendations):,} critical "
                "recommendation"
                f"{'' if len(critical_recommendations) == 1 else 's'} "
                "require attention."
            )
        )

    return tuple(
        warnings
    )


# ============================================================
# AI Report View Builder
# ============================================================


def build_ai_report_view(
    insights: PortfolioInsights,
    *,
    title: str = AI_REPORT_TITLE,
) -> AIReportView:
    """
    Convert an existing PortfolioInsights result into a report view.

    This function does not calculate portfolio analytics directly. It consumes
    the outputs already produced by PortfolioInsights.

    Args:
        insights:
            Existing PortfolioInsights instance.

        title:
            Dashboard section title.

    Returns:
        Immutable AIReportView.
    """

    if not isinstance(
        insights,
        PortfolioInsights,
    ):
        raise TypeError(
            "insights must be a PortfolioInsights."
        )

    normalized_title = (
        _validate_non_blank_text(
            title,
            parameter_name="title",
        )
    )

    summary = (
        _validate_summary_mapping(
            insights.summary()
        )
    )

    portfolio_insights = (
        insights.portfolio_insights()
    )

    if not isinstance(
        portfolio_insights,
        Mapping,
    ):
        raise TypeError(
            "portfolio_insights must be a mapping."
        )

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]
        )
    )

    executive_summary = (
        _validate_non_blank_text(
            summary["executive_summary"],
            parameter_name=(
                "summary.executive_summary"
            ),
        )
    )

    top_holding = (
        _build_holding_view(
            label="Largest Holding",
            fund_name=(
                portfolio_insights.get(
                    "best_fund"
                )
            ),
        )
    )

    worst_holding = (
        _build_holding_view(
            label="Fund to Review",
            fund_name=(
                portfolio_insights.get(
                    "worst_fund"
                )
            ),
        )
    )

    notes = _build_notes(
        summary,
        recommendations,
    )

    warnings = _build_warnings(
        summary,
        recommendations,
    )

    return AIReportView(
        title=normalized_title,
        executive_summary=(
            executive_summary
        ),
        portfolio_value=(
            _format_currency_value(
                summary["portfolio_value"],
                parameter_name=(
                    "summary.portfolio_value"
                ),
            )
        ),
        invested_value=(
            _format_currency_value(
                summary["invested_value"],
                parameter_name=(
                    "summary.invested_value"
                ),
            )
        ),
        gain_loss=(
            _format_currency_value(
                summary["gain_loss"],
                parameter_name=(
                    "summary.gain_loss"
                ),
            )
        ),
        gain_percent=(
            _format_percentage_value(
                summary["gain_percent"],
                parameter_name=(
                    "summary.gain_percent"
                ),
                include_sign=True,
            )
        ),
        health_score=_format_score(
            summary["health_score"],
            parameter_name=(
                "summary.health_score"
            ),
        ),
        risk_level=(
            _validate_non_blank_text(
                summary["risk_level"],
                parameter_name=(
                    "summary.risk_level"
                ),
            )
        ),
        diversification_score=(
            _format_score(
                summary[
                    "diversification_score"
                ],
                parameter_name=(
                    "summary.diversification_score"
                ),
            )
        ),
        concentration=(
            _format_percentage_value(
                summary["concentration"],
                parameter_name=(
                    "summary.concentration"
                ),
            )
        ),
        top_holding=top_holding,
        worst_holding=worst_holding,
        recommendations=recommendations,
        notes=notes,
        warnings=warnings,
    )


# ============================================================
# Dashboard Adapters
# ============================================================


def get_ai_metric_cards(
    view: AIReportView,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return AI portfolio metrics for dashboard cards.
    """

    if not isinstance(
        view,
        AIReportView,
    ):
        raise TypeError(
            "view must be an AIReportView."
        )

    return (
        (
            "Portfolio Value",
            view.portfolio_value,
        ),
        (
            "Invested Value",
            view.invested_value,
        ),
        (
            "Gain / Loss",
            view.gain_loss,
        ),
        (
            "Overall Return",
            view.gain_percent,
        ),
        (
            "Portfolio Health",
            view.health_score,
        ),
        (
            "Risk Level",
            view.risk_level,
        ),
        (
            "Diversification",
            view.diversification_score,
        ),
        (
            "Largest Holding",
            view.concentration,
        ),
    )


def get_ai_summary_rows(
    view: AIReportView,
) -> tuple[
    tuple[str, str],
    ...,
]:
    """
    Return formatted AI portfolio summary rows.
    """

    if not isinstance(
        view,
        AIReportView,
    ):
        raise TypeError(
            "view must be an AIReportView."
        )

    return (
        (
            "Portfolio Value",
            view.portfolio_value,
        ),
        (
            "Invested Value",
            view.invested_value,
        ),
        (
            "Gain / Loss",
            view.gain_loss,
        ),
        (
            "Overall Return",
            view.gain_percent,
        ),
        (
            "Portfolio Health",
            view.health_score,
        ),
        (
            "Risk Level",
            view.risk_level,
        ),
        (
            "Diversification Score",
            view.diversification_score,
        ),
        (
            "Largest Holding Concentration",
            view.concentration,
        ),
        (
            "Largest Holding",
            view.top_holding.fund_name,
        ),
        (
            "Fund to Review",
            view.worst_holding.fund_name,
        ),
    )


def get_ai_recommendation_rows(
    view: AIReportView,
) -> tuple[
    tuple[str, str, str],
    ...,
]:
    """
    Return normalized recommendation rows for dashboard rendering.
    """

    if not isinstance(
        view,
        AIReportView,
    ):
        raise TypeError(
            "view must be an AIReportView."
        )

    return tuple(
        (
            recommendation.icon,
            recommendation.label,
            recommendation.message,
        )
        for recommendation in view.recommendations
    )


def get_ai_report_summary(
    view: AIReportView,
) -> dict[str, Any]:
    """
    Convert an AI report view into the report-model summary mapping.
    """

    if not isinstance(
        view,
        AIReportView,
    ):
        raise TypeError(
            "view must be an AIReportView."
        )

    return {
        "Executive Summary": (
            view.executive_summary
        ),
        "Portfolio Value": (
            view.portfolio_value
        ),
        "Invested Value": (
            view.invested_value
        ),
        "Gain / Loss": (
            view.gain_loss
        ),
        "Overall Return": (
            view.gain_percent
        ),
        "Portfolio Health": (
            view.health_score
        ),
        "Risk Level": (
            view.risk_level
        ),
        "Diversification Score": (
            view.diversification_score
        ),
        "Largest Holding Concentration": (
            view.concentration
        ),
        "Largest Holding": (
            view.top_holding.fund_name
        ),
        "Fund to Review": (
            view.worst_holding.fund_name
        ),
        "Recommendations": tuple(
            recommendation.message
            for recommendation
            in view.recommendations
        ),
    }


# ============================================================
# Convenience API
# ============================================================


def prepare_ai_report(
    insights: PortfolioInsights,
    *,
    title: str = AI_REPORT_TITLE,
) -> AIReportView:
    """
    Prepare a dashboard-ready AI portfolio report view.
    """

    return build_ai_report_view(
        insights,
        title=title,
    )


# ============================================================
# Public Exports
# ============================================================

__all__ = [
    "AI_REPORT_TITLE",
    "ERROR_RECOMMENDATION",
    "INFO_RECOMMENDATION",
    "SUCCESS_RECOMMENDATION",
    "SUPPORTED_RECOMMENDATION_TYPES",
    "UNAVAILABLE_VALUE",
    "UNKNOWN_FUND_NAME",
    "WARNING_RECOMMENDATION",
    "AIHoldingView",
    "AIMetricView",
    "AIRecommendationView",
    "AIReportError",
    "AIReportValidationError",
    "AIReportView",
    "build_ai_report_view",
    "get_ai_metric_cards",
    "get_ai_recommendation_rows",
    "get_ai_report_summary",
    "get_ai_summary_rows",
    "prepare_ai_report",
]