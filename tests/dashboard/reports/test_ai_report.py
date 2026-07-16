"""
Unit tests for AI portfolio report presentation helpers.

Coverage includes:

- Text and numeric validation
- Summary mapping validation
- Recommendation normalization
- Recommendation metadata
- Holding normalization
- Notes and warning generation
- AI report view construction
- Dashboard adapters
- Report-summary conversion
- Convenience API behavior
- Immutable result models

The tests isolate presentation logic from portfolio calculations.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

import dashboard.reports.ai_report as ai_report_module

from dashboard.reports.ai_report import (
    AI_REPORT_TITLE,
    ERROR_RECOMMENDATION,
    INFO_RECOMMENDATION,
    SUCCESS_RECOMMENDATION,
    SUPPORTED_RECOMMENDATION_TYPES,
    UNKNOWN_FUND_NAME,
    WARNING_RECOMMENDATION,
    AIHoldingView,
    AIMetricView,
    AIRecommendationView,
    AIReportValidationError,
    AIReportView,
    _build_holding_view,
    _build_notes,
    _build_recommendation_view,
    _build_warnings,
    _format_currency_value,
    _format_percentage_value,
    _format_score,
    _normalise_fund_name,
    _normalise_recommendations,
    _recommendation_icon,
    _recommendation_label,
    _validate_finite_number,
    _validate_non_blank_text,
    _validate_recommendation_type,
    _validate_string_tuple,
    _validate_summary_mapping,
    build_ai_report_view,
    get_ai_metric_cards,
    get_ai_recommendation_rows,
    get_ai_report_summary,
    get_ai_summary_rows,
    prepare_ai_report,
)


# ============================================================
# Test Doubles
# ============================================================


class FakePortfolioInsights:
    """
    Lightweight PortfolioInsights test double.
    """

    def __init__(
        self,
        *,
        summary_result: dict[str, object] | None = None,
        portfolio_result: dict[str, object] | None = None,
    ) -> None:
        self.summary_result = (
            summary_result
            if summary_result is not None
            else {
                "portfolio_value": 125_000.0,
                "invested_value": 100_000.0,
                "gain_loss": 25_000.0,
                "gain_percent": 25.0,
                "health_score": 70.0,
                "risk_level": "🟡 Moderate",
                "diversification_score": 65.0,
                "concentration": 35.0,
                "executive_summary": (
                    "The portfolio is performing well."
                ),
                "recommendations": [
                    {
                        "type": "success",
                        "message": (
                            "Portfolio returns are strong."
                        ),
                    },
                    {
                        "type": "warning",
                        "message": (
                            "Review concentration risk."
                        ),
                    },
                ],
            }
        )

        self.portfolio_result = (
            portfolio_result
            if portfolio_result is not None
            else {
                "investment": 100_000.0,
                "current_value": 125_000.0,
                "profit": 25_000.0,
                "best_fund": "Alpha Fund",
                "worst_fund": "Beta Fund",
            }
        )

    def summary(self) -> dict[str, object]:
        return self.summary_result

    def portfolio_insights(
        self,
    ) -> dict[str, object]:
        return self.portfolio_result


@pytest.fixture
def patch_insights_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_report_module,
        "PortfolioInsights",
        FakePortfolioInsights,
    )


@pytest.fixture
def insights(
    patch_insights_type: None,
) -> FakePortfolioInsights:
    return FakePortfolioInsights()


# ============================================================
# Text Validation
# ============================================================


def test_validate_non_blank_text_returns_trimmed_value() -> None:
    assert (
        _validate_non_blank_text(
            "  AI Report  ",
            parameter_name="title",
        )
        == "AI Report"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_validate_non_blank_text_rejects_blank(
    value: str,
) -> None:
    with pytest.raises(
        AIReportValidationError,
        match="title cannot be blank",
    ):
        _validate_non_blank_text(
            value,
            parameter_name="title",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        object(),
    ],
)
def test_validate_non_blank_text_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="title must be a string",
    ):
        _validate_non_blank_text(
            value,  # type: ignore[arg-type]
            parameter_name="title",
        )


def test_validate_non_blank_text_rejects_blank_parameter_name() -> None:
    with pytest.raises(
        AIReportValidationError,
        match="parameter_name cannot be blank",
    ):
        _validate_non_blank_text(
            "value",
            parameter_name=" ",
        )


def test_validate_non_blank_text_rejects_invalid_parameter_name_type() -> None:
    with pytest.raises(
        TypeError,
        match="parameter_name must be a string",
    ):
        _validate_non_blank_text(
            "value",
            parameter_name=None,  # type: ignore[arg-type]
        )


# ============================================================
# String Tuple Validation
# ============================================================


def test_validate_string_tuple_accepts_valid_tuple() -> None:
    values = (
        "Note one",
        "Note two",
    )

    assert (
        _validate_string_tuple(
            values,
            parameter_name="notes",
        )
        is values
    )


@pytest.mark.parametrize(
    "value",
    [
        [],
        "note",
        None,
        123,
    ],
)
def test_validate_string_tuple_rejects_non_tuple(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="notes must be a tuple",
    ):
        _validate_string_tuple(
            value,  # type: ignore[arg-type]
            parameter_name="notes",
        )


def test_validate_string_tuple_rejects_blank_item() -> None:
    with pytest.raises(
        AIReportValidationError,
        match=r"notes\[1\] cannot be blank",
    ):
        _validate_string_tuple(
            (
                "Valid",
                " ",
            ),
            parameter_name="notes",
        )


# ============================================================
# Numeric Validation and Formatting
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            0.0,
        ),
        (
            25,
            25.0,
        ),
        (
            -12.5,
            -12.5,
        ),
    ],
)
def test_validate_finite_number_accepts_numeric_value(
    value: int | float,
    expected: float,
) -> None:
    assert (
        _validate_finite_number(
            value,
            parameter_name="metric",
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_validate_finite_number_rejects_non_finite_value(
    value: float,
) -> None:
    with pytest.raises(
        AIReportValidationError,
        match="metric must be finite",
    ):
        _validate_finite_number(
            value,
            parameter_name="metric",
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        "25",
        object(),
    ],
)
def test_validate_finite_number_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="metric must be numeric",
    ):
        _validate_finite_number(
            value,  # type: ignore[arg-type]
            parameter_name="metric",
        )


def test_format_currency_value_returns_expected_text() -> None:
    assert (
        _format_currency_value(
            125_000,
            parameter_name="portfolio_value",
        )
        == "₹125,000.00"
    )


def test_format_percentage_value_supports_sign() -> None:
    assert (
        _format_percentage_value(
            25.0,
            parameter_name="gain_percent",
            include_sign=True,
        )
        == "+25.00%"
    )


def test_format_percentage_value_rejects_invalid_include_sign() -> None:
    with pytest.raises(
        TypeError,
        match="include_sign must be a boolean",
    ):
        _format_percentage_value(
            25.0,
            parameter_name="gain_percent",
            include_sign=1,  # type: ignore[arg-type]
        )


def test_format_score_returns_expected_text() -> None:
    assert (
        _format_score(
            70,
            parameter_name="health_score",
        )
        == "70.0/100"
    )


def test_format_score_supports_custom_maximum() -> None:
    assert (
        _format_score(
            4.5,
            parameter_name="score",
            maximum=5,
        )
        == "4.5/5"
    )


@pytest.mark.parametrize(
    "maximum",
    [
        0,
        -1,
    ],
)
def test_format_score_rejects_non_positive_maximum(
    maximum: int,
) -> None:
    with pytest.raises(
        AIReportValidationError,
        match="maximum must be greater than zero",
    ):
        _format_score(
            70,
            parameter_name="score",
            maximum=maximum,
        )


@pytest.mark.parametrize(
    "maximum",
    [
        True,
        1.5,
        "100",
    ],
)
def test_format_score_rejects_invalid_maximum_type(
    maximum: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="maximum must be an integer",
    ):
        _format_score(
            70,
            parameter_name="score",
            maximum=maximum,  # type: ignore[arg-type]
        )


# ============================================================
# Summary Mapping Validation
# ============================================================


def test_validate_summary_mapping_accepts_complete_mapping() -> None:
    summary = FakePortfolioInsights().summary()

    assert (
        _validate_summary_mapping(
            summary
        )
        is summary
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        (),
        "summary",
        123,
    ],
)
def test_validate_summary_mapping_rejects_non_mapping(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="summary must be a mapping",
    ):
        _validate_summary_mapping(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "missing_key",
    [
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
    ],
)
def test_validate_summary_mapping_rejects_missing_key(
    missing_key: str,
) -> None:
    summary = FakePortfolioInsights().summary()
    summary.pop(
        missing_key
    )

    with pytest.raises(
        AIReportValidationError,
        match="summary is missing required key",
    ):
        _validate_summary_mapping(
            summary
        )


# ============================================================
# Recommendation Type Validation
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "success",
            SUCCESS_RECOMMENDATION,
        ),
        (
            " SUCCESS ",
            SUCCESS_RECOMMENDATION,
        ),
        (
            "info",
            INFO_RECOMMENDATION,
        ),
        (
            "warning",
            WARNING_RECOMMENDATION,
        ),
        (
            "error",
            ERROR_RECOMMENDATION,
        ),
    ],
)
def test_validate_recommendation_type_accepts_supported_value(
    value: str,
    expected: str,
) -> None:
    assert (
        _validate_recommendation_type(
            value
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "critical",
        "positive",
        "unknown",
    ],
)
def test_validate_recommendation_type_rejects_unsupported_value(
    value: str,
) -> None:
    with pytest.raises(
        AIReportValidationError,
        match="Unsupported recommendation type",
    ):
        _validate_recommendation_type(
            value
        )


def test_supported_recommendation_types_are_complete() -> None:
    assert (
        SUPPORTED_RECOMMENDATION_TYPES
        == (
            SUCCESS_RECOMMENDATION,
            INFO_RECOMMENDATION,
            WARNING_RECOMMENDATION,
            ERROR_RECOMMENDATION,
        )
    )


# ============================================================
# Recommendation Metadata
# ============================================================


@pytest.mark.parametrize(
    ("recommendation_type", "expected"),
    [
        (
            SUCCESS_RECOMMENDATION,
            "✅",
        ),
        (
            INFO_RECOMMENDATION,
            "ℹ️",
        ),
        (
            WARNING_RECOMMENDATION,
            "⚠️",
        ),
        (
            ERROR_RECOMMENDATION,
            "🚨",
        ),
    ],
)
def test_recommendation_icon_returns_expected_icon(
    recommendation_type: str,
    expected: str,
) -> None:
    assert (
        _recommendation_icon(
            recommendation_type
        )
        == expected
    )


@pytest.mark.parametrize(
    ("recommendation_type", "expected"),
    [
        (
            SUCCESS_RECOMMENDATION,
            "Positive",
        ),
        (
            INFO_RECOMMENDATION,
            "Information",
        ),
        (
            WARNING_RECOMMENDATION,
            "Review",
        ),
        (
            ERROR_RECOMMENDATION,
            "Critical",
        ),
    ],
)
def test_recommendation_label_returns_expected_label(
    recommendation_type: str,
    expected: str,
) -> None:
    assert (
        _recommendation_label(
            recommendation_type
        )
        == expected
    )


# ============================================================
# Recommendation View Models
# ============================================================


def test_build_recommendation_view_returns_expected_view() -> None:
    result = _build_recommendation_view(
        {
            "type": "warning",
            "message": " Review concentration. ",
        }
    )

    assert result == AIRecommendationView(
        recommendation_type="warning",
        message="Review concentration.",
        icon="⚠️",
        label="Review",
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "recommendation",
        123,
    ],
)
def test_build_recommendation_view_rejects_non_mapping(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="recommendation must be a mapping",
    ):
        _build_recommendation_view(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("recommendation", "missing_key"),
    [
        (
            {
                "message": "Message",
            },
            "type",
        ),
        (
            {
                "type": "info",
            },
            "message",
        ),
    ],
)
def test_build_recommendation_view_rejects_missing_key(
    recommendation: dict[str, str],
    missing_key: str,
) -> None:
    with pytest.raises(
        AIReportValidationError,
        match=f"missing required key: {missing_key}",
    ):
        _build_recommendation_view(
            recommendation
        )


def test_normalise_recommendations_returns_tuple() -> None:
    result = _normalise_recommendations(
        [
            {
                "type": "success",
                "message": "Good performance.",
            },
            {
                "type": "info",
                "message": "Monitor regularly.",
            },
        ]
    )

    assert isinstance(
        result,
        tuple,
    )

    assert len(result) == 2

    assert all(
        isinstance(
            item,
            AIRecommendationView,
        )
        for item in result
    )


@pytest.mark.parametrize(
    "value",
    [
        "recommendations",
        b"recommendations",
        123,
        {},
        object(),
    ],
)
def test_normalise_recommendations_rejects_invalid_sequence(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="recommendations must be a sequence",
    ):
        _normalise_recommendations(
            value  # type: ignore[arg-type]
        )


def test_ai_recommendation_view_is_immutable() -> None:
    recommendation = AIRecommendationView(
        recommendation_type="info",
        message="Monitor regularly.",
        icon="ℹ️",
        label="Information",
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        recommendation.message = (  # type: ignore[misc]
            "Changed"
        )


# ============================================================
# Fund and Holding Normalization
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "Alpha Fund",
            "Alpha Fund",
        ),
        (
            " Alpha Fund ",
            "Alpha Fund",
        ),
        (
            None,
            UNKNOWN_FUND_NAME,
        ),
        (
            "",
            UNKNOWN_FUND_NAME,
        ),
        (
            " ",
            UNKNOWN_FUND_NAME,
        ),
    ],
)
def test_normalise_fund_name_returns_expected_value(
    value: object,
    expected: str,
) -> None:
    assert (
        _normalise_fund_name(value)
        == expected
    )


def test_build_holding_view_marks_available_fund() -> None:
    result = _build_holding_view(
        label="Largest Holding",
        fund_name="Alpha Fund",
    )

    assert result == AIHoldingView(
        label="Largest Holding",
        fund_name="Alpha Fund",
        available=True,
    )


def test_build_holding_view_marks_missing_fund_unavailable() -> None:
    result = _build_holding_view(
        label="Fund to Review",
        fund_name=None,
    )

    assert result == AIHoldingView(
        label="Fund to Review",
        fund_name=UNKNOWN_FUND_NAME,
        available=False,
    )


def test_ai_holding_view_rejects_invalid_available_type() -> None:
    with pytest.raises(
        TypeError,
        match="available must be a boolean",
    ):
        AIHoldingView(
            label="Largest Holding",
            fund_name="Alpha Fund",
            available=1,  # type: ignore[arg-type]
        )


# ============================================================
# Notes and Warnings
# ============================================================


def test_build_notes_describes_report() -> None:
    summary = FakePortfolioInsights().summary()

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]  # type: ignore[arg-type]
        )
    )

    notes = _build_notes(
        summary,
        recommendations,
    )

    assert any(
        "current portfolio snapshot"
        in note
        for note in notes
    )

    assert any(
        "2 recommendations"
        in note
        for note in notes
    )

    assert any(
        "70.0/100"
        in note
        for note in notes
    )


def test_build_warnings_reports_negative_return() -> None:
    summary = FakePortfolioInsights().summary()
    summary["gain_percent"] = -5.0

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]  # type: ignore[arg-type]
        )
    )

    warnings = _build_warnings(
        summary,
        recommendations,
    )

    assert any(
        "negative overall return"
        in warning
        for warning in warnings
    )


def test_build_warnings_reports_high_concentration() -> None:
    summary = FakePortfolioInsights().summary()
    summary["concentration"] = 55.0

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]  # type: ignore[arg-type]
        )
    )

    warnings = _build_warnings(
        summary,
        recommendations,
    )

    assert any(
        "at least half"
        in warning
        for warning in warnings
    )


def test_build_warnings_reports_low_health_score() -> None:
    summary = FakePortfolioInsights().summary()
    summary["health_score"] = 45.0

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]  # type: ignore[arg-type]
        )
    )

    warnings = _build_warnings(
        summary,
        recommendations,
    )

    assert any(
        "below 50"
        in warning
        for warning in warnings
    )


def test_build_warnings_reports_critical_recommendation() -> None:
    summary = FakePortfolioInsights().summary()
    summary["recommendations"] = [
        {
            "type": "error",
            "message": "Critical concentration risk.",
        }
    ]

    recommendations = (
        _normalise_recommendations(
            summary["recommendations"]  # type: ignore[arg-type]
        )
    )

    warnings = _build_warnings(
        summary,
        recommendations,
    )

    assert any(
        "1 critical recommendation"
        in warning
        for warning in warnings
    )


# ============================================================
# AI Report View Construction
# ============================================================


def test_build_ai_report_view_formats_complete_insights(
    insights: FakePortfolioInsights,
) -> None:
    result = build_ai_report_view(
        insights,  # type: ignore[arg-type]
        title=" AI Portfolio Summary ",
    )

    assert isinstance(
        result,
        AIReportView,
    )

    assert result.title == (
        "AI Portfolio Summary"
    )

    assert result.portfolio_value == (
        "₹125,000.00"
    )

    assert result.invested_value == (
        "₹100,000.00"
    )

    assert result.gain_loss == (
        "₹25,000.00"
    )

    assert result.gain_percent == (
        "+25.00%"
    )

    assert result.health_score == (
        "70.0/100"
    )

    assert result.risk_level == (
        "🟡 Moderate"
    )

    assert (
        result.diversification_score
        == "65.0/100"
    )

    assert result.concentration == (
        "35.00%"
    )

    assert result.top_holding.fund_name == (
        "Alpha Fund"
    )

    assert result.worst_holding.fund_name == (
        "Beta Fund"
    )

    assert len(
        result.recommendations
    ) == 2


def test_build_ai_report_view_uses_default_title(
    insights: FakePortfolioInsights,
) -> None:
    result = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    assert result.title == (
        AI_REPORT_TITLE
    )


def test_build_ai_report_view_handles_missing_funds(
    patch_insights_type: None,
) -> None:
    insights = FakePortfolioInsights(
        portfolio_result={
            "investment": 100_000.0,
            "current_value": 125_000.0,
            "profit": 25_000.0,
            "best_fund": None,
            "worst_fund": "",
        }
    )

    result = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    assert result.top_holding.available is False

    assert result.worst_holding.available is False

    assert result.top_holding.fund_name == (
        UNKNOWN_FUND_NAME
    )


def test_build_ai_report_view_rejects_invalid_insights_type(
    patch_insights_type: None,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "insights must be a "
            "PortfolioInsights"
        ),
    ):
        build_ai_report_view(
            object()  # type: ignore[arg-type]
        )


def test_build_ai_report_view_rejects_invalid_portfolio_insights_mapping(
    patch_insights_type: None,
) -> None:
    insights = FakePortfolioInsights()

    insights.portfolio_insights = Mock(
        return_value=[]
    )

    with pytest.raises(
        TypeError,
        match=(
            "portfolio_insights must be a mapping"
        ),
    ):
        build_ai_report_view(
            insights  # type: ignore[arg-type]
        )


def test_build_ai_report_view_rejects_non_finite_summary_value(
    patch_insights_type: None,
) -> None:
    summary = FakePortfolioInsights().summary()
    summary["portfolio_value"] = float("nan")

    insights = FakePortfolioInsights(
        summary_result=summary
    )

    with pytest.raises(
        AIReportValidationError,
        match=(
            "summary.portfolio_value "
            "must be finite"
        ),
    ):
        build_ai_report_view(
            insights  # type: ignore[arg-type]
        )


def test_ai_report_view_is_immutable(
    insights: FakePortfolioInsights,
) -> None:
    view = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        view.title = (  # type: ignore[misc]
            "Changed"
        )


# ============================================================
# Metric and Summary Adapters
# ============================================================


def test_get_ai_metric_cards_returns_expected_rows(
    insights: FakePortfolioInsights,
) -> None:
    view = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    result = get_ai_metric_cards(
        view
    )

    assert (
        "Portfolio Value",
        "₹125,000.00",
    ) in result

    assert (
        "Portfolio Health",
        "70.0/100",
    ) in result

    assert (
        "Largest Holding",
        "35.00%",
    ) in result


def test_get_ai_summary_rows_returns_expected_rows(
    insights: FakePortfolioInsights,
) -> None:
    view = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    result = get_ai_summary_rows(
        view
    )

    assert (
        "Largest Holding",
        "Alpha Fund",
    ) in result

    assert (
        "Fund to Review",
        "Beta Fund",
    ) in result


def test_get_ai_recommendation_rows_returns_expected_rows(
    insights: FakePortfolioInsights,
) -> None:
    view = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    result = (
        get_ai_recommendation_rows(
            view
        )
    )

    assert (
        "✅",
        "Positive",
        "Portfolio returns are strong.",
    ) in result

    assert (
        "⚠️",
        "Review",
        "Review concentration risk.",
    ) in result


def test_get_ai_report_summary_returns_export_mapping(
    insights: FakePortfolioInsights,
) -> None:
    view = build_ai_report_view(
        insights  # type: ignore[arg-type]
    )

    result = get_ai_report_summary(
        view
    )

    assert result[
        "Executive Summary"
    ] == (
        "The portfolio is performing well."
    )

    assert result[
        "Portfolio Health"
    ] == "70.0/100"

    assert result[
        "Largest Holding"
    ] == "Alpha Fund"

    assert result[
        "Recommendations"
    ] == (
        "Portfolio returns are strong.",
        "Review concentration risk.",
    )


@pytest.mark.parametrize(
    "function",
    [
        get_ai_metric_cards,
        get_ai_summary_rows,
        get_ai_recommendation_rows,
        get_ai_report_summary,
    ],
)
def test_dashboard_adapter_rejects_invalid_view(
    function: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="view must be an AIReportView",
    ):
        function(  # type: ignore[operator]
            object()
        )


# ============================================================
# Convenience API
# ============================================================


def test_prepare_ai_report_delegates_to_builder(
    insights: FakePortfolioInsights,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = object()

    builder_mock = Mock(
        return_value=expected
    )

    monkeypatch.setattr(
        ai_report_module,
        "build_ai_report_view",
        builder_mock,
    )

    result = prepare_ai_report(
        insights,  # type: ignore[arg-type]
        title="Custom AI Report",
    )

    assert result is expected

    builder_mock.assert_called_once_with(
        insights,
        title="Custom AI Report",
    )


def test_prepare_ai_report_uses_default_title(
    insights: FakePortfolioInsights,
) -> None:
    result = prepare_ai_report(
        insights  # type: ignore[arg-type]
    )

    assert result.title == (
        AI_REPORT_TITLE
    )


# ============================================================
# AIMetricView
# ============================================================


def test_ai_metric_view_accepts_valid_data() -> None:
    metric = AIMetricView(
        label="Portfolio Health",
        value="70.0/100",
        description="Overall portfolio health.",
    )

    assert metric.label == (
        "Portfolio Health"
    )

    assert metric.value == (
        "70.0/100"
    )


def test_ai_metric_view_rejects_invalid_description_type() -> None:
    with pytest.raises(
        TypeError,
        match="description must be a string",
    ):
        AIMetricView(
            label="Portfolio Health",
            value="70.0/100",
            description=123,  # type: ignore[arg-type]
        )