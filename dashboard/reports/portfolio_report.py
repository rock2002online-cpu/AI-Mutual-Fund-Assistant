"""
Portfolio report orchestration for the Streamlit reporting dashboard.

This module assembles immutable PortfolioReport objects from results already
produced by the application's portfolio, analytics, and AI services.

Responsibilities
----------------
- Validate report assembly inputs.
- Create report metadata.
- Aggregate existing analytics results into PortfolioReport.
- Prepare PDF and Excel download payloads.
- Provide a single orchestration result for the dashboard.

This module performs no portfolio calculations and does not retrieve portfolio
data directly. PortfolioService and analytics services remain the sources of
portfolio and analytics data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)
from services.analytics.performance import (
    PortfolioPerformanceMetrics,
)
from services.reporting.excel_report_service import (
    DEFAULT_EXCEL_FILENAME,
    EXCEL_MIME_TYPE,
    ExcelReportService,
)
from services.reporting.pdf_report_service import (
    DEFAULT_PDF_FILENAME,
    PDF_MIME_TYPE,
    PDFReportService,
)
from services.reporting.report_assets import (
    APPLICATION_NAME,
    DEFAULT_REPORT_TITLE,
)
from services.reporting.report_models import (
    PortfolioReport,
    ReportMetadata,
)


# ============================================================
# Constants
# ============================================================

REPORT_VERSION: Final[str] = "8.0.0"

PDF_FORMAT: Final[str] = "pdf"
EXCEL_FORMAT: Final[str] = "excel"

SUPPORTED_REPORT_FORMATS: Final[
    tuple[str, ...]
] = (
    PDF_FORMAT,
    EXCEL_FORMAT,
)


# ============================================================
# Exceptions
# ============================================================


class PortfolioReportOrchestrationError(
    RuntimeError
):
    """
    Base exception raised by portfolio-report orchestration.
    """


class PortfolioReportInputError(
    PortfolioReportOrchestrationError
):
    """
    Raised when portfolio-report assembly input is invalid.
    """


class PortfolioReportExportError(
    PortfolioReportOrchestrationError
):
    """
    Raised when an assembled report cannot be exported.
    """


# ============================================================
# Result Models
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class ReportDownloadPayload:
    """
    Download payload prepared for a Streamlit download button.
    """

    data: bytes
    filename: str
    mime_type: str
    format_name: str

    def __post_init__(
        self,
    ) -> None:
        """
        Validate the completed download payload.
        """

        if not isinstance(
            self.data,
            bytes,
        ):
            raise TypeError(
                "data must be bytes."
            )

        if not self.data:
            raise PortfolioReportInputError(
                "data cannot be empty."
            )

        for field_name in (
            "filename",
            "mime_type",
            "format_name",
        ):
            value = getattr(
                self,
                field_name,
            )

            _validate_non_blank_text(
                value,
                parameter_name=field_name,
            )


@dataclass(
    frozen=True,
    slots=True,
)
class PortfolioReportBundle:
    """
    Complete dashboard-ready reporting result.

    Attributes:
        report:
            Immutable typed report model.

        pdf:
            Prepared PDF download payload.

        excel:
            Prepared Excel download payload.
    """

    report: PortfolioReport
    pdf: ReportDownloadPayload
    excel: ReportDownloadPayload

    def __post_init__(
        self,
    ) -> None:
        """
        Validate the assembled report bundle.
        """

        if not isinstance(
            self.report,
            PortfolioReport,
        ):
            raise TypeError(
                "report must be a PortfolioReport."
            )

        if not isinstance(
            self.pdf,
            ReportDownloadPayload,
        ):
            raise TypeError(
                "pdf must be a ReportDownloadPayload."
            )

        if not isinstance(
            self.excel,
            ReportDownloadPayload,
        ):
            raise TypeError(
                "excel must be a ReportDownloadPayload."
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
        raise PortfolioReportInputError(
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
        raise PortfolioReportInputError(
            f"{normalized_parameter_name} cannot be blank."
        )

    return normalized_value


def _validate_performance(
    performance: PortfolioPerformanceMetrics,
) -> PortfolioPerformanceMetrics:
    """
    Validate portfolio-performance input.
    """

    if not isinstance(
        performance,
        PortfolioPerformanceMetrics,
    ):
        raise TypeError(
            "performance must be a "
            "PortfolioPerformanceMetrics."
        )

    return performance


def _validate_history(
    history: HistoryAnalyticsResult | None,
) -> HistoryAnalyticsResult | None:
    """
    Validate optional historical-analytics input.
    """

    if (
        history is not None
        and not isinstance(
            history,
            HistoryAnalyticsResult,
        )
    ):
        raise TypeError(
            "history must be a "
            "HistoryAnalyticsResult or None."
        )

    return history


def _validate_advanced_analytics(
    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ),
) -> AdvancedAnalyticsServiceResult | None:
    """
    Validate optional advanced-analytics input.
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


def _normalise_ai_summary(
    ai_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    Validate and normalize optional AI-summary content.
    """

    if ai_summary is None:
        return {}

    if not isinstance(
        ai_summary,
        Mapping,
    ):
        raise TypeError(
            "ai_summary must be a mapping or None."
        )

    normalized: dict[str, Any] = {}

    for key, value in ai_summary.items():
        normalized_key = _validate_non_blank_text(
            key,
            parameter_name="ai_summary key",
        )

        normalized[
            normalized_key
        ] = value

    return normalized


def _normalise_messages(
    values: Sequence[str] | None,
    *,
    parameter_name: str,
) -> tuple[str, ...]:
    """
    Validate and normalize notes or warnings.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if values is None:
        return ()

    if isinstance(
        values,
        (str, bytes, bytearray),
    ) or not isinstance(
        values,
        Sequence,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be "
            "a sequence of strings or None."
        )

    normalized_values: list[str] = []

    for index, value in enumerate(
        values
    ):
        normalized_values.append(
            _validate_non_blank_text(
                value,
                parameter_name=(
                    f"{normalized_parameter_name}"
                    f"[{index}]"
                ),
            )
        )

    return tuple(
        normalized_values
    )


def _validate_generated_at(
    generated_at: datetime | None,
) -> datetime:
    """
    Validate or create the report-generation timestamp.
    """

    if generated_at is None:
        return datetime.now(
            timezone.utc
        )

    if not isinstance(
        generated_at,
        datetime,
    ):
        raise TypeError(
            "generated_at must be a datetime or None."
        )

    return generated_at


def _validate_export_format(
    format_name: str,
) -> str:
    """
    Validate an export-format identifier.
    """

    normalized = _validate_non_blank_text(
        format_name,
        parameter_name="format_name",
    ).lower()

    if normalized not in SUPPORTED_REPORT_FORMATS:
        supported = ", ".join(
            SUPPORTED_REPORT_FORMATS
        )

        raise PortfolioReportInputError(
            "Unsupported report format. "
            f"Expected one of: {supported}."
        )

    return normalized


# ============================================================
# Report Assembly
# ============================================================


def build_portfolio_report(
    performance: PortfolioPerformanceMetrics,
    *,
    history: HistoryAnalyticsResult | None = None,
    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ) = None,
    ai_summary: Mapping[str, Any] | None = None,
    notes: Sequence[str] | None = None,
    warnings: Sequence[str] | None = None,
    title: str = DEFAULT_REPORT_TITLE,
    version: str = REPORT_VERSION,
    application_name: str = APPLICATION_NAME,
    generated_at: datetime | None = None,
) -> PortfolioReport:
    """
    Assemble a typed portfolio report from existing service results.

    No analytics are calculated by this function.

    Args:
        performance:
            Existing portfolio-performance result.

        history:
            Existing historical-analytics result.

        advanced_analytics:
            Existing advanced-analytics service result.

        ai_summary:
            Existing AI insight content.

        notes:
            Optional report notes.

        warnings:
            Optional report warnings.

        title:
            Human-readable report title.

        version:
            Report schema or application version.

        application_name:
            Name displayed in exported reports.

        generated_at:
            Optional report-generation timestamp. UTC now is used when
            omitted.

    Returns:
        Fully assembled immutable PortfolioReport.
    """

    validated_performance = (
        _validate_performance(
            performance
        )
    )

    validated_history = _validate_history(
        history
    )

    validated_advanced = (
        _validate_advanced_analytics(
            advanced_analytics
        )
    )

    normalized_title = (
        _validate_non_blank_text(
            title,
            parameter_name="title",
        )
    )

    normalized_version = (
        _validate_non_blank_text(
            version,
            parameter_name="version",
        )
    )

    normalized_application_name = (
        _validate_non_blank_text(
            application_name,
            parameter_name="application_name",
        )
    )

    metadata = ReportMetadata(
        title=normalized_title,
        version=normalized_version,
        generated_at=_validate_generated_at(
            generated_at
        ),
        application_name=(
            normalized_application_name
        ),
    )

    return PortfolioReport(
        metadata=metadata,
        performance=validated_performance,
        history=validated_history,
        advanced_analytics=(
            validated_advanced
        ),
        ai_summary=_normalise_ai_summary(
            ai_summary
        ),
        notes=_normalise_messages(
            notes,
            parameter_name="notes",
        ),
        warnings=_normalise_messages(
            warnings,
            parameter_name="warnings",
        ),
    )


# ============================================================
# Export Preparation
# ============================================================


def prepare_pdf_download(
    report: PortfolioReport,
    *,
    filename: str = DEFAULT_PDF_FILENAME,
    service: PDFReportService | None = None,
) -> ReportDownloadPayload:
    """
    Prepare a PDF download payload from an assembled report.
    """

    if not isinstance(
        report,
        PortfolioReport,
    ):
        raise TypeError(
            "report must be a PortfolioReport."
        )

    if (
        service is not None
        and not isinstance(
            service,
            PDFReportService,
        )
    ):
        raise TypeError(
            "service must be a PDFReportService or None."
        )

    resolved_service = (
        service
        if service is not None
        else PDFReportService()
    )

    try:
        data, resolved_filename, mime_type = (
            resolved_service.prepare_download(
                report,
                filename=filename,
            )
        )

    except Exception as error:
        raise PortfolioReportExportError(
            "Unable to prepare the PDF report download: "
            f"{error}"
        ) from error

    return ReportDownloadPayload(
        data=data,
        filename=resolved_filename,
        mime_type=mime_type,
        format_name=PDF_FORMAT,
    )


def prepare_excel_download(
    report: PortfolioReport,
    *,
    filename: str = DEFAULT_EXCEL_FILENAME,
    service: ExcelReportService | None = None,
) -> ReportDownloadPayload:
    """
    Prepare an Excel download payload from an assembled report.
    """

    if not isinstance(
        report,
        PortfolioReport,
    ):
        raise TypeError(
            "report must be a PortfolioReport."
        )

    if (
        service is not None
        and not isinstance(
            service,
            ExcelReportService,
        )
    ):
        raise TypeError(
            "service must be an ExcelReportService or None."
        )

    resolved_service = (
        service
        if service is not None
        else ExcelReportService()
    )

    try:
        data, resolved_filename, mime_type = (
            resolved_service.prepare_download(
                report,
                filename=filename,
            )
        )

    except Exception as error:
        raise PortfolioReportExportError(
            "Unable to prepare the Excel report download: "
            f"{error}"
        ) from error

    return ReportDownloadPayload(
        data=data,
        filename=resolved_filename,
        mime_type=mime_type,
        format_name=EXCEL_FORMAT,
    )


def prepare_report_download(
    report: PortfolioReport,
    *,
    format_name: str,
    filename: str | None = None,
) -> ReportDownloadPayload:
    """
    Prepare one requested download format.
    """

    normalized_format = (
        _validate_export_format(
            format_name
        )
    )

    if normalized_format == PDF_FORMAT:
        return prepare_pdf_download(
            report,
            filename=(
                filename
                if filename is not None
                else DEFAULT_PDF_FILENAME
            ),
        )

    return prepare_excel_download(
        report,
        filename=(
            filename
            if filename is not None
            else DEFAULT_EXCEL_FILENAME
        ),
    )


def build_portfolio_report_bundle(
    performance: PortfolioPerformanceMetrics,
    *,
    history: HistoryAnalyticsResult | None = None,
    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ) = None,
    ai_summary: Mapping[str, Any] | None = None,
    notes: Sequence[str] | None = None,
    warnings: Sequence[str] | None = None,
    title: str = DEFAULT_REPORT_TITLE,
    version: str = REPORT_VERSION,
    application_name: str = APPLICATION_NAME,
    generated_at: datetime | None = None,
    pdf_filename: str = DEFAULT_PDF_FILENAME,
    excel_filename: str = DEFAULT_EXCEL_FILENAME,
) -> PortfolioReportBundle:
    """
    Build a report and prepare both supported download formats.
    """

    report = build_portfolio_report(
        performance,
        history=history,
        advanced_analytics=advanced_analytics,
        ai_summary=ai_summary,
        notes=notes,
        warnings=warnings,
        title=title,
        version=version,
        application_name=application_name,
        generated_at=generated_at,
    )

    return PortfolioReportBundle(
        report=report,
        pdf=prepare_pdf_download(
            report,
            filename=pdf_filename,
        ),
        excel=prepare_excel_download(
            report,
            filename=excel_filename,
        ),
    )


# ============================================================
# Optional File Persistence
# ============================================================


def save_report_bundle(
    bundle: PortfolioReportBundle,
    output_directory: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """
    Save both payloads from a completed report bundle.

    This utility writes the already-generated payloads and does not regenerate
    either report.
    """

    if not isinstance(
        bundle,
        PortfolioReportBundle,
    ):
        raise TypeError(
            "bundle must be a PortfolioReportBundle."
        )

    if not isinstance(
        output_directory,
        (str, Path),
    ):
        raise TypeError(
            "output_directory must be a string or Path."
        )

    if (
        isinstance(
            output_directory,
            str,
        )
        and not output_directory.strip()
    ):
        raise PortfolioReportInputError(
            "output_directory cannot be blank."
        )

    if not isinstance(
        overwrite,
        bool,
    ):
        raise TypeError(
            "overwrite must be a boolean."
        )

    directory = Path(
        output_directory
    ).expanduser().resolve()

    try:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    except Exception as error:
        raise PortfolioReportExportError(
            "Unable to create the report output directory: "
            f"{error}"
        ) from error

    if not directory.is_dir():
        raise PortfolioReportInputError(
            "output_directory must reference a directory."
        )

    pdf_path = (
        directory
        / bundle.pdf.filename
    )

    excel_path = (
        directory
        / bundle.excel.filename
    )

    for path in (
        pdf_path,
        excel_path,
    ):
        if path.exists() and not overwrite:
            raise PortfolioReportInputError(
                f"The report file already exists: {path.name}. "
                "Set overwrite=True to replace it."
            )

    try:
        pdf_path.write_bytes(
            bundle.pdf.data
        )

        excel_path.write_bytes(
            bundle.excel.data
        )

    except Exception as error:
        raise PortfolioReportExportError(
            "Unable to save the generated report files: "
            f"{error}"
        ) from error

    return (
        pdf_path,
        excel_path,
    )


# ============================================================
# Public Exports
# ============================================================

__all__ = [
    "EXCEL_FORMAT",
    "PDF_FORMAT",
    "REPORT_VERSION",
    "SUPPORTED_REPORT_FORMATS",
    "PortfolioReportBundle",
    "PortfolioReportExportError",
    "PortfolioReportInputError",
    "PortfolioReportOrchestrationError",
    "ReportDownloadPayload",
    "build_portfolio_report",
    "build_portfolio_report_bundle",
    "prepare_excel_download",
    "prepare_pdf_download",
    "prepare_report_download",
    "save_report_bundle",
]