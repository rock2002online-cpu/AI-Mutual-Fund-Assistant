"""
Unit tests for the professional PDF portfolio reporting service.

Coverage includes:

- Input validation
- Filename and output-path validation
- Integer and duration formatting
- Safe text conversion
- PDF service metadata
- PDF byte generation
- Invalid PDF detection
- ReportLab error wrapping
- Download preparation
- Convenience generation API

The tests isolate the PDF service from portfolio calculations and external
analytics services.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

import services.reporting.pdf_report_service as pdf_report_module

from services.reporting.pdf_report_service import (
    DEFAULT_PDF_FILENAME,
    PDF_MIME_TYPE,
    PDFReportGenerationError,
    PDFReportService,
    PDFReportValidationError,
    UNAVAILABLE_VALUE,
    _format_duration,
    _format_integer,
    _safe_text,
    _validate_filename,
    _validate_output_path,
    _validate_report,
    generate_portfolio_pdf,
)


# ============================================================
# Test Fixtures
# ============================================================


class FakePortfolioReport:
    """
    Minimal PortfolioReport replacement for isolated service tests.

    The complete report model is intentionally not duplicated here because
    these tests target PDF service orchestration rather than report-model
    construction or portfolio calculations.
    """

    def __init__(self) -> None:
        self.metadata = SimpleNamespace(
            title="Portfolio Analytics Report",
            application_name="AI Mutual Fund Assistant",
            version="8.0.0",
        )


@pytest.fixture
def fake_report(
    monkeypatch: pytest.MonkeyPatch,
) -> FakePortfolioReport:
    """
    Return a lightweight report accepted by the PDF report validator.
    """

    monkeypatch.setattr(
        pdf_report_module,
        "PortfolioReport",
        FakePortfolioReport,
    )

    return FakePortfolioReport()


# ============================================================
# Report Validation
# ============================================================


def test_validate_report_accepts_portfolio_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A valid PortfolioReport instance should be returned unchanged.
    """

    report = object()

    monkeypatch.setattr(
        pdf_report_module,
        "PortfolioReport",
        type(report),
    )

    result = _validate_report(report)

    assert result is report


@pytest.mark.parametrize(
    "invalid_report",
    [
        None,
        {},
        [],
        "report",
        123,
        object(),
    ],
)
def test_validate_report_rejects_invalid_type(
    invalid_report: object,
) -> None:
    """
    Non-PortfolioReport values should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="report must be a PortfolioReport",
    ):
        _validate_report(
            invalid_report  # type: ignore[arg-type]
        )


# ============================================================
# Output Path Validation
# ============================================================


@pytest.mark.parametrize(
    "value",
    [
        "report.pdf",
        "REPORT.PDF",
        Path("portfolio.pdf"),
    ],
)
def test_validate_output_path_accepts_valid_pdf_path(
    value: str | Path,
) -> None:
    """
    Valid PDF paths should be normalized to absolute paths.
    """

    result = _validate_output_path(value)

    assert isinstance(result, Path)
    assert result.is_absolute()
    assert result.suffix.lower() == ".pdf"


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        1.5,
        object(),
    ],
)
def test_validate_output_path_rejects_invalid_type(
    value: object,
) -> None:
    """
    Output paths must be strings or Path instances.
    """

    with pytest.raises(
        TypeError,
        match="output_path must be a string or Path",
    ):
        _validate_output_path(
            value  # type: ignore[arg-type]
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
def test_validate_output_path_rejects_blank_path(
    value: str,
) -> None:
    """
    Blank string paths should be rejected.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="output_path cannot be blank",
    ):
        _validate_output_path(value)


@pytest.mark.parametrize(
    "value",
    [
        "report",
        "report.txt",
        "report.xlsx",
        Path("report.csv"),
    ],
)
def test_validate_output_path_rejects_non_pdf_extension(
    value: str | Path,
) -> None:
    """
    The output path must use the PDF extension.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="output_path must end with .pdf",
    ):
        _validate_output_path(value)


# ============================================================
# Filename Validation
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "report.pdf",
            "report.pdf",
        ),
        (
            " REPORT.PDF ",
            "REPORT.PDF",
        ),
        (
            "portfolio report.pdf",
            "portfolio report.pdf",
        ),
    ],
)
def test_validate_filename_accepts_valid_filename(
    value: str,
    expected: str,
) -> None:
    """
    Valid filenames should be trimmed and returned.
    """

    assert _validate_filename(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        Path("report.pdf"),
        object(),
    ],
)
def test_validate_filename_rejects_invalid_type(
    value: object,
) -> None:
    """
    Download filenames must be strings.
    """

    with pytest.raises(
        TypeError,
        match="filename must be a string",
    ):
        _validate_filename(
            value  # type: ignore[arg-type]
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
def test_validate_filename_rejects_blank_filename(
    value: str,
) -> None:
    """
    Blank filenames should be rejected.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="filename cannot be blank",
    ):
        _validate_filename(value)


@pytest.mark.parametrize(
    "value",
    [
        "reports/report.pdf",
        "reports\\report.pdf",
        "../report.pdf",
        "./report.pdf",
    ],
)
def test_validate_filename_rejects_directory_components(
    value: str,
) -> None:
    """
    Download filenames should not contain directory components.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="filename must not contain directory components",
    ):
        _validate_filename(value)


@pytest.mark.parametrize(
    "value",
    [
        "report",
        "report.txt",
        "report.xlsx",
        "report.pdf.txt",
    ],
)
def test_validate_filename_rejects_non_pdf_filename(
    value: str,
) -> None:
    """
    Download filenames must end with the PDF extension.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="filename must end with .pdf",
    ):
        _validate_filename(value)


# ============================================================
# Integer Formatting
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            "0",
        ),
        (
            1,
            "1",
        ),
        (
            999,
            "999",
        ),
        (
            1_000,
            "1,000",
        ),
        (
            1_234_567,
            "1,234,567",
        ),
        (
            -1_234,
            "-1,234",
        ),
    ],
)
def test_format_integer_formats_with_thousands_separator(
    value: int,
    expected: str,
) -> None:
    """
    Integer values should use thousands separators.
    """

    assert _format_integer(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        1.5,
        "1000",
        object(),
    ],
)
def test_format_integer_rejects_non_integer(
    value: object,
) -> None:
    """
    Boolean and non-integer values should be rejected.
    """

    with pytest.raises(
        TypeError,
        match="value must be an integer",
    ):
        _format_integer(
            value  # type: ignore[arg-type]
        )


# ============================================================
# Duration Formatting
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0,
            "0 days",
        ),
        (
            1,
            "1 day",
        ),
        (
            2,
            "2 days",
        ),
        (
            364,
            "364 days",
        ),
        (
            365,
            "1 year",
        ),
        (
            366,
            "1 year, 1 day",
        ),
        (
            730,
            "2 years",
        ),
        (
            731,
            "2 years, 1 day",
        ),
        (
            1_096,
            "3 years, 1 day",
        ),
    ],
)
def test_format_duration_formats_days_and_years(
    value: int,
    expected: str,
) -> None:
    """
    Durations should use readable day and year units.
    """

    assert _format_duration(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        1.5,
        "365",
        object(),
    ],
)
def test_format_duration_rejects_non_integer(
    value: object,
) -> None:
    """
    Duration input must be an integer and not a boolean.
    """

    with pytest.raises(
        TypeError,
        match="duration_days must be an integer",
    ):
        _format_duration(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        -1,
        -365,
        -10_000,
    ],
)
def test_format_duration_rejects_negative_values(
    value: int,
) -> None:
    """
    Negative durations should be rejected.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="duration_days cannot be negative",
    ):
        _format_duration(value)


# ============================================================
# Safe Text Formatting
# ============================================================


def test_safe_text_handles_none() -> None:
    """
    None should be represented as unavailable.
    """

    assert _safe_text(None) == UNAVAILABLE_VALUE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            True,
            "Yes",
        ),
        (
            False,
            "No",
        ),
    ],
)
def test_safe_text_handles_boolean(
    value: bool,
    expected: str,
) -> None:
    """
    Boolean values should use human-readable text.
    """

    assert _safe_text(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            0.0,
            "0.0000",
        ),
        (
            1.25,
            "1.2500",
        ),
        (
            1_234.56789,
            "1,234.5679",
        ),
        (
            -12.5,
            "-12.5000",
        ),
    ],
)
def test_safe_text_handles_finite_float(
    value: float,
    expected: str,
) -> None:
    """
    Finite floats should be displayed with four decimal places.
    """

    assert _safe_text(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_safe_text_handles_non_finite_float(
    value: float,
) -> None:
    """
    NaN and infinite values should be represented as unavailable.
    """

    assert _safe_text(value) == UNAVAILABLE_VALUE


def test_safe_text_handles_mapping() -> None:
    """
    Mapping content should be rendered as key-value text.
    """

    result = _safe_text(
        {
            "status": "complete",
            "count": 3,
        }
    )

    assert result == (
        "status: complete; count: 3"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            [1, 2, 3],
            "1; 2; 3",
        ),
        (
            ("alpha", "beta"),
            "alpha; beta",
        ),
        (
            ["a", None, True],
            "a; Unavailable; Yes",
        ),
    ],
)
def test_safe_text_handles_sequence(
    value: object,
    expected: str,
) -> None:
    """
    Sequence values should be separated by semicolons.
    """

    assert _safe_text(value) == expected


def test_safe_text_normalizes_whitespace() -> None:
    """
    Repeated and multiline whitespace should be normalized.
    """

    assert _safe_text(
        "  alpha\n\n beta\t gamma  "
    ) == "alpha beta gamma"


def test_safe_text_truncates_long_text() -> None:
    """
    Text exceeding the selected maximum should end in an ellipsis.
    """

    result = _safe_text(
        "abcdefghij",
        maximum_length=8,
    )

    assert result == "abcde..."
    assert len(result) == 8


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        None,
        1.5,
        "10",
        object(),
    ],
)
def test_safe_text_rejects_invalid_maximum_length_type(
    value: object,
) -> None:
    """
    maximum_length must be an integer and not a boolean.
    """

    with pytest.raises(
        TypeError,
        match="maximum_length must be an integer",
    ):
        _safe_text(
            "text",
            maximum_length=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        -100,
    ],
)
def test_safe_text_rejects_non_positive_maximum_length(
    value: int,
) -> None:
    """
    maximum_length must be greater than zero.
    """

    with pytest.raises(
        PDFReportValidationError,
        match="maximum_length must be greater than zero",
    ):
        _safe_text(
            "text",
            maximum_length=value,
        )


# ============================================================
# PDF Service Properties
# ============================================================


def test_pdf_report_service_returns_pdf_mime_type() -> None:
    """
    The service should expose the standard PDF MIME type.
    """

    service = PDFReportService()

    assert service.mime_type == PDF_MIME_TYPE
    assert service.mime_type == "application/pdf"


def test_pdf_report_service_returns_default_filename() -> None:
    """
    The service should expose the configured default filename.
    """

    service = PDFReportService()

    assert (
        service.default_filename
        == DEFAULT_PDF_FILENAME
    )

    assert (
        service.default_filename
        == "portfolio_report.pdf"
    )


# ============================================================
# PDF Byte Generation
# ============================================================


def test_generate_bytes_returns_valid_pdf_document(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Successful generation should return non-empty PDF bytes.
    """

    styles = getSampleStyleSheet()

    monkeypatch.setattr(
        pdf_report_module,
        "_build_story",
        lambda report, report_styles: [
            Paragraph(
                "AI Mutual Fund Assistant PDF Report",
                styles["BodyText"],
            )
        ],
    )

    service = PDFReportService()

    result = service.generate_bytes(
        fake_report  # type: ignore[arg-type]
    )

    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF")
    assert len(result) > 100


@pytest.mark.parametrize(
    "invalid_report",
    [
        None,
        {},
        [],
        "portfolio report",
        123,
        object(),
    ],
)
def test_generate_bytes_rejects_invalid_report(
    invalid_report: object,
) -> None:
    """
    PDF generation should reject invalid report objects.
    """

    service = PDFReportService()

    with pytest.raises(
        TypeError,
        match="report must be a PortfolioReport",
    ):
        service.generate_bytes(
            invalid_report  # type: ignore[arg-type]
        )


def test_generate_bytes_wraps_reportlab_build_failure(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Unexpected ReportLab errors should be wrapped consistently.
    """

    class FailingDocument:
        """
        Test double that raises during document construction.
        """

        def __init__(
            self,
            *args: object,
            **kwargs: object,
        ) -> None:
            pass

        def build(
            self,
            *args: object,
            **kwargs: object,
        ) -> None:
            raise RuntimeError(
                "simulated ReportLab failure"
            )

    monkeypatch.setattr(
        pdf_report_module,
        "SimpleDocTemplate",
        FailingDocument,
    )

    monkeypatch.setattr(
        pdf_report_module,
        "_build_story",
        lambda report, styles: [],
    )

    service = PDFReportService()

    with pytest.raises(
        PDFReportGenerationError,
        match=(
            "Unable to generate the portfolio PDF report: "
            "simulated ReportLab failure"
        ),
    ) as error_info:
        service.generate_bytes(
            fake_report  # type: ignore[arg-type]
        )

    assert isinstance(
        error_info.value.__cause__,
        RuntimeError,
    )


def test_generate_bytes_rejects_output_without_pdf_signature(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Generated content that does not begin with %PDF should be rejected.
    """

    class InvalidPDFDocument:
        """
        Test double that writes invalid non-PDF output.
        """

        def __init__(
            self,
            buffer: object,
            *args: object,
            **kwargs: object,
        ) -> None:
            self.buffer = buffer

        def build(
            self,
            *args: object,
            **kwargs: object,
        ) -> None:
            self.buffer.write(
                b"not-a-pdf-document"
            )

    monkeypatch.setattr(
        pdf_report_module,
        "SimpleDocTemplate",
        InvalidPDFDocument,
    )

    monkeypatch.setattr(
        pdf_report_module,
        "_build_story",
        lambda report, styles: [],
    )

    service = PDFReportService()

    with pytest.raises(
        PDFReportGenerationError,
        match=(
            "Generated output is not a valid "
            "PDF document"
        ),
    ):
        service.generate_bytes(
            fake_report  # type: ignore[arg-type]
        )


# ============================================================
# Download Preparation
# ============================================================


def test_prepare_download_returns_pdf_download_payload(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Download preparation should return bytes, filename, and MIME type.
    """

    expected_bytes = b"%PDF-test-content"

    generate_mock = Mock(
        return_value=expected_bytes
    )

    monkeypatch.setattr(
        PDFReportService,
        "generate_bytes",
        generate_mock,
    )

    service = PDFReportService()

    result = service.prepare_download(
        fake_report,  # type: ignore[arg-type]
        filename="portfolio-analysis.pdf",
    )

    assert result == (
        expected_bytes,
        "portfolio-analysis.pdf",
        PDF_MIME_TYPE,
    )

    generate_mock.assert_called_once_with(
        fake_report
    )


def test_prepare_download_uses_default_filename(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The default configured PDF filename should be used when omitted.
    """

    monkeypatch.setattr(
        PDFReportService,
        "generate_bytes",
        lambda self, report: b"%PDF-test-content",
    )

    service = PDFReportService()

    pdf_bytes, filename, mime_type = (
        service.prepare_download(
            fake_report  # type: ignore[arg-type]
        )
    )

    assert pdf_bytes == b"%PDF-test-content"
    assert filename == DEFAULT_PDF_FILENAME
    assert mime_type == PDF_MIME_TYPE


@pytest.mark.parametrize(
    "filename",
    [
        "",
        " ",
        "report.txt",
        "folder/report.pdf",
        "../report.pdf",
    ],
)
def test_prepare_download_rejects_invalid_filename_before_generation(
    fake_report: FakePortfolioReport,
    filename: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Invalid filenames should fail before PDF generation is attempted.
    """

    generate_mock = Mock()

    monkeypatch.setattr(
        PDFReportService,
        "generate_bytes",
        generate_mock,
    )

    service = PDFReportService()

    with pytest.raises(
        PDFReportValidationError,
    ):
        service.prepare_download(
            fake_report,  # type: ignore[arg-type]
            filename=filename,
        )

    generate_mock.assert_not_called()


def test_prepare_download_rejects_non_string_filename(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A non-string download filename should be rejected before generation.
    """

    generate_mock = Mock()

    monkeypatch.setattr(
        PDFReportService,
        "generate_bytes",
        generate_mock,
    )

    service = PDFReportService()

    with pytest.raises(
        TypeError,
        match="filename must be a string",
    ):
        service.prepare_download(
            fake_report,  # type: ignore[arg-type]
            filename=Path("report.pdf"),  # type: ignore[arg-type]
        )

    generate_mock.assert_not_called()


# ============================================================
# Convenience Generation API
# ============================================================


def test_generate_portfolio_pdf_delegates_to_service(
    fake_report: FakePortfolioReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The convenience API should delegate generation to PDFReportService.
    """

    expected_bytes = b"%PDF-convenience-api"

    generate_mock = Mock(
        return_value=expected_bytes
    )

    monkeypatch.setattr(
        PDFReportService,
        "generate_bytes",
        generate_mock,
    )

    result = generate_portfolio_pdf(
        fake_report  # type: ignore[arg-type]
    )

    assert result == expected_bytes

    generate_mock.assert_called_once_with(
        fake_report
    )


def test_generate_portfolio_pdf_propagates_validation_error() -> None:
    """
    Validation errors from the underlying service should propagate.
    """

    with pytest.raises(
        TypeError,
        match="report must be a PortfolioReport",
    ):
        generate_portfolio_pdf(
            None  # type: ignore[arg-type]
        )