"""
Unit tests for portfolio report orchestration.

Coverage includes:

- Input validation
- Metadata construction
- Report assembly
- Notes, warnings, and AI-summary normalization
- PDF and Excel download preparation
- Format routing
- Report-bundle generation
- Optional file persistence
- Export error wrapping
- Immutable result models

The tests isolate orchestration from portfolio calculations and exporter
implementation details.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import dashboard.reports.portfolio_report as portfolio_report_module

from dashboard.reports.portfolio_report import (
    EXCEL_FORMAT,
    PDF_FORMAT,
    REPORT_VERSION,
    SUPPORTED_REPORT_FORMATS,
    PortfolioReportBundle,
    PortfolioReportExportError,
    PortfolioReportInputError,
    ReportDownloadPayload,
    _normalise_ai_summary,
    _normalise_messages,
    _validate_export_format,
    _validate_generated_at,
    _validate_non_blank_text,
    build_portfolio_report,
    build_portfolio_report_bundle,
    prepare_excel_download,
    prepare_pdf_download,
    prepare_report_download,
    save_report_bundle,
)
from services.reporting.excel_report_service import (
    DEFAULT_EXCEL_FILENAME,
    EXCEL_MIME_TYPE,
)
from services.reporting.pdf_report_service import (
    DEFAULT_PDF_FILENAME,
    PDF_MIME_TYPE,
)
from services.reporting.report_assets import (
    APPLICATION_NAME,
    DEFAULT_REPORT_TITLE,
)
from services.portfolio_reconciliation_service import (
    PortfolioReconciliationResult,
)

# ============================================================
# Test Doubles
# ============================================================


class FakePerformance:
    """
    Lightweight performance-result test double.
    """


class FakeHistory:
    """
    Lightweight history-result test double.
    """


class FakeAdvancedAnalytics:
    """
    Lightweight advanced-analytics result test double.
    """


class FakeReportMetadata:
    """
    Lightweight metadata object matching the report contract.
    """

    def __init__(
        self,
        *,
        title: str,
        version: str,
        generated_at: datetime,
        application_name: str,
    ) -> None:
        self.title = title
        self.version = version
        self.generated_at = generated_at
        self.application_name = application_name


class FakePortfolioReport:
    """
    Lightweight portfolio-report object matching the orchestration contract.
    """

    def __init__(
        self,
        *,
        metadata: FakeReportMetadata,
        performance: FakePerformance,
        history: FakeHistory | None = None,
        advanced_analytics: FakeAdvancedAnalytics | None = None,
        reconciliation: (
            PortfolioReconciliationResult | None
        ) = None,
        ai_summary: dict[str, object] | None = None,
        notes: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> None:
        self.metadata = metadata
        self.performance = performance
        self.history = history
        self.advanced_analytics = advanced_analytics
        self.reconciliation = reconciliation
        self.ai_summary = (
            {}
            if ai_summary is None
            else ai_summary
        )
        self.notes = notes
        self.warnings = warnings


class FakePDFReportService:
    """
    PDF exporter test double.
    """

    def __init__(
        self,
        *,
        result: tuple[bytes, str, str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or (
            b"%PDF-test",
            DEFAULT_PDF_FILENAME,
            PDF_MIME_TYPE,
        )

        self.error = error
        self.calls: list[
            tuple[
                FakePortfolioReport,
                str,
            ]
        ] = []

    def prepare_download(
        self,
        report: FakePortfolioReport,
        *,
        filename: str,
    ) -> tuple[bytes, str, str]:
        self.calls.append(
            (
                report,
                filename,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


class FakeExcelReportService:
    """
    Excel exporter test double.
    """

    def __init__(
        self,
        *,
        result: tuple[bytes, str, str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or (
            b"PK-test",
            DEFAULT_EXCEL_FILENAME,
            EXCEL_MIME_TYPE,
        )

        self.error = error
        self.calls: list[
            tuple[
                FakePortfolioReport,
                str,
            ]
        ] = []

    def prepare_download(
        self,
        report: FakePortfolioReport,
        *,
        filename: str,
    ) -> tuple[bytes, str, str]:
        self.calls.append(
            (
                report,
                filename,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def patch_report_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Replace imported service models with lightweight test doubles.
    """

    monkeypatch.setattr(
        portfolio_report_module,
        "PortfolioPerformanceMetrics",
        FakePerformance,
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "HistoryAnalyticsResult",
        FakeHistory,
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "AdvancedAnalyticsServiceResult",
        FakeAdvancedAnalytics,
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "ReportMetadata",
        FakeReportMetadata,
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "PortfolioReport",
        FakePortfolioReport,
    )


@pytest.fixture
def performance(
    patch_report_types: None,
) -> FakePerformance:
    return FakePerformance()


@pytest.fixture
def assembled_report(
    patch_report_types: None,
) -> FakePortfolioReport:
    return FakePortfolioReport(
        metadata=FakeReportMetadata(
            title="Portfolio Analytics Report",
            version="8.0.0",
            generated_at=datetime(
                2026,
                7,
                16,
                14,
                0,
                tzinfo=timezone.utc,
            ),
            application_name=(
                "AI Mutual Fund Assistant"
            ),
        ),
        performance=FakePerformance(),
        history=FakeHistory(),
        advanced_analytics=(
            FakeAdvancedAnalytics()
        ),
        ai_summary={
            "Summary": "Healthy portfolio",
        },
        notes=(
            "Latest NAV values used.",
        ),
        warnings=(
            "Past performance is not guaranteed.",
        ),
    )


# ============================================================
# Text Validation
# ============================================================


def test_validate_non_blank_text_returns_trimmed_value() -> None:
    assert (
        _validate_non_blank_text(
            "  report title  ",
            parameter_name="title",
        )
        == "report title"
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
def test_validate_non_blank_text_rejects_blank_value(
    value: str,
) -> None:
    with pytest.raises(
        PortfolioReportInputError,
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
def test_validate_non_blank_text_rejects_non_string_value(
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
        PortfolioReportInputError,
        match="parameter_name cannot be blank",
    ):
        _validate_non_blank_text(
            "value",
            parameter_name=" ",
        )


def test_validate_non_blank_text_rejects_non_string_parameter_name() -> None:
    with pytest.raises(
        TypeError,
        match="parameter_name must be a string",
    ):
        _validate_non_blank_text(
            "value",
            parameter_name=None,  # type: ignore[arg-type]
        )


# ============================================================
# AI Summary Normalization
# ============================================================


def test_normalise_ai_summary_returns_empty_mapping_for_none() -> None:
    assert _normalise_ai_summary(None) == {}


def test_normalise_ai_summary_copies_and_trims_keys() -> None:
    source = {
        " Summary ": "Portfolio is healthy.",
        "Risk": "Moderate",
    }

    result = _normalise_ai_summary(
        source
    )

    assert result == {
        "Summary": "Portfolio is healthy.",
        "Risk": "Moderate",
    }

    assert result is not source


@pytest.mark.parametrize(
    "value",
    [
        [],
        (),
        "summary",
        123,
        object(),
    ],
)
def test_normalise_ai_summary_rejects_non_mapping(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="ai_summary must be a mapping or None",
    ):
        _normalise_ai_summary(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "key",
    [
        "",
        " ",
        "\t",
    ],
)
def test_normalise_ai_summary_rejects_blank_key(
    key: str,
) -> None:
    with pytest.raises(
        PortfolioReportInputError,
        match="ai_summary key cannot be blank",
    ):
        _normalise_ai_summary(
            {
                key: "value",
            }
        )


def test_normalise_ai_summary_rejects_non_string_key() -> None:
    with pytest.raises(
        TypeError,
        match="ai_summary key must be a string",
    ):
        _normalise_ai_summary(
            {
                1: "value",
            }  # type: ignore[dict-item]
        )


# ============================================================
# Message Normalization
# ============================================================


def test_normalise_messages_returns_empty_tuple_for_none() -> None:
    assert (
        _normalise_messages(
            None,
            parameter_name="notes",
        )
        == ()
    )


def test_normalise_messages_returns_trimmed_tuple() -> None:
    result = _normalise_messages(
        [
            " First note ",
            "Second note",
        ],
        parameter_name="notes",
    )

    assert result == (
        "First note",
        "Second note",
    )


@pytest.mark.parametrize(
    "value",
    [
        "single note",
        b"note",
        123,
        {},
        object(),
    ],
)
def test_normalise_messages_rejects_invalid_sequence(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "notes must be a sequence "
            "of strings or None"
        ),
    ):
        _normalise_messages(
            value,  # type: ignore[arg-type]
            parameter_name="notes",
        )


def test_normalise_messages_rejects_non_string_item() -> None:
    with pytest.raises(
        TypeError,
        match=r"notes\[1\] must be a string",
    ):
        _normalise_messages(
            [
                "valid",
                123,
            ],  # type: ignore[list-item]
            parameter_name="notes",
        )


def test_normalise_messages_rejects_blank_item() -> None:
    with pytest.raises(
        PortfolioReportInputError,
        match=r"warnings\[0\] cannot be blank",
    ):
        _normalise_messages(
            [
                " ",
            ],
            parameter_name="warnings",
        )


# ============================================================
# Timestamp Validation
# ============================================================


def test_validate_generated_at_returns_supplied_datetime() -> None:
    generated_at = datetime(
        2026,
        7,
        16,
        14,
        30,
        tzinfo=timezone.utc,
    )

    assert (
        _validate_generated_at(
            generated_at
        )
        is generated_at
    )


def test_validate_generated_at_creates_timezone_aware_utc_datetime() -> None:
    result = _validate_generated_at(
        None
    )

    assert isinstance(
        result,
        datetime,
    )

    assert result.tzinfo is not None
    assert result.utcoffset() == timezone.utc.utcoffset(
        result
    )


@pytest.mark.parametrize(
    "value",
    [
        "2026-07-16",
        123,
        object(),
    ],
)
def test_validate_generated_at_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "generated_at must be a datetime or None"
        ),
    ):
        _validate_generated_at(
            value  # type: ignore[arg-type]
        )


# ============================================================
# Export Format Validation
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "pdf",
            PDF_FORMAT,
        ),
        (
            " PDF ",
            PDF_FORMAT,
        ),
        (
            "excel",
            EXCEL_FORMAT,
        ),
        (
            " EXCEL ",
            EXCEL_FORMAT,
        ),
    ],
)
def test_validate_export_format_accepts_supported_format(
    value: str,
    expected: str,
) -> None:
    assert (
        _validate_export_format(value)
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "xlsx",
        "docx",
        "csv",
        "html",
    ],
)
def test_validate_export_format_rejects_unsupported_format(
    value: str,
) -> None:
    with pytest.raises(
        PortfolioReportInputError,
        match="Unsupported report format",
    ):
        _validate_export_format(value)


def test_supported_report_formats_are_complete() -> None:
    assert SUPPORTED_REPORT_FORMATS == (
        PDF_FORMAT,
        EXCEL_FORMAT,
    )


# ============================================================
# Report Assembly
# ============================================================


def test_build_portfolio_report_creates_expected_report(
    performance: FakePerformance,
) -> None:
    generated_at = datetime(
        2026,
        7,
        16,
        15,
        0,
        tzinfo=timezone.utc,
    )

    history = FakeHistory()
    advanced = FakeAdvancedAnalytics()

    result = build_portfolio_report(
        performance,  # type: ignore[arg-type]
        history=history,  # type: ignore[arg-type]
        advanced_analytics=advanced,  # type: ignore[arg-type]
        ai_summary={
            " Summary ": "Strong performance",
        },
        notes=[
            " Note one ",
        ],
        warnings=[
            " Warning one ",
        ],
        title=" Custom Report ",
        version=" 8.1.0 ",
        application_name=" Test Application ",
        generated_at=generated_at,
    )

    assert isinstance(
        result,
        FakePortfolioReport,
    )

    assert result.performance is performance
    assert result.history is history

    assert (
        result.advanced_analytics
        is advanced
    )

    assert result.ai_summary == {
        "Summary": "Strong performance",
    }

    assert result.notes == (
        "Note one",
    )

    assert result.warnings == (
        "Warning one",
    )

    assert (
        result.metadata.title
        == "Custom Report"
    )

    assert (
        result.metadata.version
        == "8.1.0"
    )

    assert (
        result.metadata.application_name
        == "Test Application"
    )

    assert (
        result.metadata.generated_at
        is generated_at
    )
def test_build_portfolio_report_carries_reconciliation(
    performance: FakePerformance,
) -> None:
    """Propagate precomputed reconciliation without recalculation."""

    reconciliation = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    result = build_portfolio_report(
        performance,  # type: ignore[arg-type]
        reconciliation=reconciliation,
    )

    assert result.reconciliation is reconciliation


def test_build_portfolio_report_uses_defaults(
    performance: FakePerformance,
) -> None:
    result = build_portfolio_report(
        performance  # type: ignore[arg-type]
    )

    assert (
        result.metadata.title
        == DEFAULT_REPORT_TITLE
    )

    assert (
        result.metadata.version
        == REPORT_VERSION
    )

    assert (
        result.metadata.application_name
        == APPLICATION_NAME
    )

    assert result.history is None
    assert result.advanced_analytics is None
    assert result.ai_summary == {}
    assert result.notes == ()
    assert result.warnings == ()


@pytest.mark.parametrize(
    "value",
    [
        None,
        object(),
        "performance",
    ],
)
def test_build_portfolio_report_rejects_invalid_performance(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "performance must be a "
            "PortfolioPerformanceMetrics"
        ),
    ):
        build_portfolio_report(
            value  # type: ignore[arg-type]
        )


def test_build_portfolio_report_rejects_invalid_history(
    performance: FakePerformance,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "history must be a "
            "HistoryAnalyticsResult or None"
        ),
    ):
        build_portfolio_report(
            performance,  # type: ignore[arg-type]
            history=object(),  # type: ignore[arg-type]
        )


def test_build_portfolio_report_rejects_invalid_advanced_analytics(
    performance: FakePerformance,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "advanced_analytics must be an "
            "AdvancedAnalyticsServiceResult or None"
        ),
    ):
        build_portfolio_report(
            performance,  # type: ignore[arg-type]
            advanced_analytics=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        (
            "title",
            {
                "title": " ",
            },
        ),
        (
            "version",
            {
                "version": "",
            },
        ),
        (
            "application_name",
            {
                "application_name": "\t",
            },
        ),
    ],
)
def test_build_portfolio_report_rejects_blank_metadata(
    performance: FakePerformance,
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        PortfolioReportInputError,
        match=f"{field_name} cannot be blank",
    ):
        build_portfolio_report(
            performance,  # type: ignore[arg-type]
            **kwargs,  # type: ignore[arg-type]
        )


# ============================================================
# Download Payload Model
# ============================================================


def test_report_download_payload_accepts_valid_data() -> None:
    payload = ReportDownloadPayload(
        data=b"report-data",
        filename="report.pdf",
        mime_type="application/pdf",
        format_name="pdf",
    )

    assert payload.data == b"report-data"
    assert payload.filename == "report.pdf"


def test_report_download_payload_rejects_non_bytes_data() -> None:
    with pytest.raises(
        TypeError,
        match="data must be bytes",
    ):
        ReportDownloadPayload(
            data="report-data",  # type: ignore[arg-type]
            filename="report.pdf",
            mime_type="application/pdf",
            format_name="pdf",
        )


def test_report_download_payload_rejects_empty_data() -> None:
    with pytest.raises(
        PortfolioReportInputError,
        match="data cannot be empty",
    ):
        ReportDownloadPayload(
            data=b"",
            filename="report.pdf",
            mime_type="application/pdf",
            format_name="pdf",
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "filename",
        "mime_type",
        "format_name",
    ],
)
def test_report_download_payload_rejects_blank_text(
    field_name: str,
) -> None:
    values = {
        "data": b"report-data",
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "format_name": "pdf",
    }

    values[field_name] = " "

    with pytest.raises(
        PortfolioReportInputError,
        match=f"{field_name} cannot be blank",
    ):
        ReportDownloadPayload(
            **values  # type: ignore[arg-type]
        )


def test_report_download_payload_is_immutable() -> None:
    payload = ReportDownloadPayload(
        data=b"report-data",
        filename="report.pdf",
        mime_type="application/pdf",
        format_name="pdf",
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        payload.filename = (  # type: ignore[misc]
            "changed.pdf"
        )


# ============================================================
# PDF Download Preparation
# ============================================================


def test_prepare_pdf_download_returns_payload(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePDFReportService(
        result=(
            b"%PDF-custom",
            "custom.pdf",
            PDF_MIME_TYPE,
        )
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "PDFReportService",
        FakePDFReportService,
    )

    result = prepare_pdf_download(
        assembled_report,  # type: ignore[arg-type]
        filename="custom.pdf",
        service=service,  # type: ignore[arg-type]
    )

    assert result == ReportDownloadPayload(
        data=b"%PDF-custom",
        filename="custom.pdf",
        mime_type=PDF_MIME_TYPE,
        format_name=PDF_FORMAT,
    )

    assert service.calls == [
        (
            assembled_report,
            "custom.pdf",
        )
    ]


def test_prepare_pdf_download_constructs_default_service(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePDFReportService()

    monkeypatch.setattr(
        portfolio_report_module,
        "PDFReportService",
        Mock(
            return_value=service
        ),
    )

    result = prepare_pdf_download(
        assembled_report  # type: ignore[arg-type]
    )

    assert result.filename == (
        DEFAULT_PDF_FILENAME
    )

    assert result.mime_type == PDF_MIME_TYPE


def test_prepare_pdf_download_wraps_export_failure(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakePDFReportService(
        error=RuntimeError(
            "PDF generation failed"
        )
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "PDFReportService",
        FakePDFReportService,
    )

    with pytest.raises(
        PortfolioReportExportError,
        match=(
            "Unable to prepare the PDF report download: "
            "PDF generation failed"
        ),
    ) as error_info:
        prepare_pdf_download(
            assembled_report,  # type: ignore[arg-type]
            service=service,  # type: ignore[arg-type]
        )

    assert isinstance(
        error_info.value.__cause__,
        RuntimeError,
    )


# ============================================================
# Excel Download Preparation
# ============================================================


def test_prepare_excel_download_returns_payload(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeExcelReportService(
        result=(
            b"PK-custom",
            "custom.xlsx",
            EXCEL_MIME_TYPE,
        )
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "ExcelReportService",
        FakeExcelReportService,
    )

    result = prepare_excel_download(
        assembled_report,  # type: ignore[arg-type]
        filename="custom.xlsx",
        service=service,  # type: ignore[arg-type]
    )

    assert result == ReportDownloadPayload(
        data=b"PK-custom",
        filename="custom.xlsx",
        mime_type=EXCEL_MIME_TYPE,
        format_name=EXCEL_FORMAT,
    )

    assert service.calls == [
        (
            assembled_report,
            "custom.xlsx",
        )
    ]


def test_prepare_excel_download_wraps_export_failure(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeExcelReportService(
        error=RuntimeError(
            "Excel generation failed"
        )
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "ExcelReportService",
        FakeExcelReportService,
    )

    with pytest.raises(
        PortfolioReportExportError,
        match=(
            "Unable to prepare the Excel report download: "
            "Excel generation failed"
        ),
    ):
        prepare_excel_download(
            assembled_report,  # type: ignore[arg-type]
            service=service,  # type: ignore[arg-type]
        )


# ============================================================
# Generic Download Routing
# ============================================================


def test_prepare_report_download_routes_pdf(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ReportDownloadPayload(
        data=b"%PDF-test",
        filename="r.pdf",
        mime_type=PDF_MIME_TYPE,
        format_name=PDF_FORMAT,
    )

    prepare_mock = Mock(
        return_value=expected
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "prepare_pdf_download",
        prepare_mock,
    )

    result = prepare_report_download(
        assembled_report,  # type: ignore[arg-type]
        format_name="PDF",
        filename="r.pdf",
    )

    assert result is expected

    prepare_mock.assert_called_once_with(
        assembled_report,
        filename="r.pdf",
    )


def test_prepare_report_download_routes_excel_with_default_filename(
    assembled_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ReportDownloadPayload(
        data=b"PK-test",
        filename=DEFAULT_EXCEL_FILENAME,
        mime_type=EXCEL_MIME_TYPE,
        format_name=EXCEL_FORMAT,
    )

    prepare_mock = Mock(
        return_value=expected
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "prepare_excel_download",
        prepare_mock,
    )

    result = prepare_report_download(
        assembled_report,  # type: ignore[arg-type]
        format_name="excel",
    )

    assert result is expected

    prepare_mock.assert_called_once_with(
        assembled_report,
        filename=DEFAULT_EXCEL_FILENAME,
    )


# ============================================================
# Report Bundle
# ============================================================


def test_build_portfolio_report_bundle_combines_report_and_downloads(
    performance: FakePerformance,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = Mock(
        spec=FakePortfolioReport
    )

    pdf_payload = ReportDownloadPayload(
        data=b"%PDF-test",
        filename="bundle.pdf",
        mime_type=PDF_MIME_TYPE,
        format_name=PDF_FORMAT,
    )

    excel_payload = ReportDownloadPayload(
        data=b"PK-test",
        filename="bundle.xlsx",
        mime_type=EXCEL_MIME_TYPE,
        format_name=EXCEL_FORMAT,
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "build_portfolio_report",
        Mock(
            return_value=report
        ),
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "prepare_pdf_download",
        Mock(
            return_value=pdf_payload
        ),
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "prepare_excel_download",
        Mock(
            return_value=excel_payload
        ),
    )

    monkeypatch.setattr(
        portfolio_report_module,
        "PortfolioReport",
        type(report),
    )
    reconciliation = PortfolioReconciliationResult(
        items=[],
        is_reconciled=True,
    )

    result = build_portfolio_report_bundle(
        performance,  # type: ignore[arg-type]
        pdf_filename="bundle.pdf",
        excel_filename="bundle.xlsx",
        reconciliation=reconciliation,
    )

    assert result.report is report
    assert result.pdf is pdf_payload
    assert result.excel is excel_payload
    build_call = (
        portfolio_report_module
        .build_portfolio_report
        .call_args
    )

    assert (
        build_call.kwargs["reconciliation"]
        is reconciliation
    )


def test_portfolio_report_bundle_is_immutable(
    assembled_report: FakePortfolioReport,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF-test",
            filename="report.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK-test",
            filename="report.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        bundle.report = (  # type: ignore[misc]
            assembled_report
        )


# ============================================================
# Bundle Persistence
# ============================================================


def test_save_report_bundle_writes_both_files(
    assembled_report: FakePortfolioReport,
    tmp_path: Path,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF-test",
            filename="portfolio.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK-test",
            filename="portfolio.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    pdf_path, excel_path = (
        save_report_bundle(
            bundle,
            tmp_path / "reports",
        )
    )

    assert pdf_path.read_bytes() == (
        b"%PDF-test"
    )

    assert excel_path.read_bytes() == (
        b"PK-test"
    )


def test_save_report_bundle_rejects_existing_file_without_overwrite(
    assembled_report: FakePortfolioReport,
    tmp_path: Path,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF-test",
            filename="portfolio.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK-test",
            filename="portfolio.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    output_directory = (
        tmp_path
        / "reports"
    )

    output_directory.mkdir()

    (
        output_directory
        / "portfolio.pdf"
    ).write_bytes(
        b"existing"
    )

    with pytest.raises(
        PortfolioReportInputError,
        match="report file already exists",
    ):
        save_report_bundle(
            bundle,
            output_directory,
        )


def test_save_report_bundle_overwrites_existing_files(
    assembled_report: FakePortfolioReport,
    tmp_path: Path,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF-new",
            filename="portfolio.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK-new",
            filename="portfolio.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    output_directory = (
        tmp_path
        / "reports"
    )

    output_directory.mkdir()

    (
        output_directory
        / "portfolio.pdf"
    ).write_bytes(
        b"old"
    )

    (
        output_directory
        / "portfolio.xlsx"
    ).write_bytes(
        b"old"
    )

    pdf_path, excel_path = (
        save_report_bundle(
            bundle,
            output_directory,
            overwrite=True,
        )
    )

    assert pdf_path.read_bytes() == (
        b"%PDF-new"
    )

    assert excel_path.read_bytes() == (
        b"PK-new"
    )


@pytest.mark.parametrize(
    "output_directory",
    [
        "",
        " ",
        "\t",
    ],
)
def test_save_report_bundle_rejects_blank_directory(
    assembled_report: FakePortfolioReport,
    output_directory: str,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF",
            filename="r.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK",
            filename="r.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    with pytest.raises(
        PortfolioReportInputError,
        match="output_directory cannot be blank",
    ):
        save_report_bundle(
            bundle,
            output_directory,
        )


def test_save_report_bundle_rejects_invalid_overwrite(
    assembled_report: FakePortfolioReport,
    tmp_path: Path,
) -> None:
    bundle = PortfolioReportBundle(
        report=assembled_report,  # type: ignore[arg-type]
        pdf=ReportDownloadPayload(
            data=b"%PDF",
            filename="r.pdf",
            mime_type=PDF_MIME_TYPE,
            format_name=PDF_FORMAT,
        ),
        excel=ReportDownloadPayload(
            data=b"PK",
            filename="r.xlsx",
            mime_type=EXCEL_MIME_TYPE,
            format_name=EXCEL_FORMAT,
        ),
    )

    with pytest.raises(
        TypeError,
        match="overwrite must be a boolean",
    ):
        save_report_bundle(
            bundle,
            tmp_path,
            overwrite=1,  # type: ignore[arg-type]
        )