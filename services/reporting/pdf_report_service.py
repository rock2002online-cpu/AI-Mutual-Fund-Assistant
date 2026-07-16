"""
Professional PDF portfolio report generation service.

This module converts an existing PortfolioReport into a print-ready PDF.

Responsibilities
----------------
- Validate PDF generation inputs.
- Build a professional ReportLab document.
- Render report metadata.
- Render portfolio performance metrics.
- Render historical analytics when available.
- Render advanced-analytics availability information when available.
- Render AI summary content, notes, and warnings.
- Return PDF bytes or save them to a caller-provided path.

This module performs no portfolio calculations and does not retrieve data
from portfolio or analytics services. It consumes PortfolioReport only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO
from math import isfinite
from pathlib import Path
from typing import Any, Final

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    StyleSheet1,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.reporting.report_formatter import (
    format_currency,
    format_datetime,
    format_percentage,
)
from services.reporting.report_models import (
    PortfolioReport,
)


# ============================================================
# Constants
# ============================================================

DEFAULT_PDF_FILENAME: Final[str] = (
    "portfolio_report.pdf"
)

PDF_MIME_TYPE: Final[str] = (
    "application/pdf"
)

PAGE_WIDTH: Final[float] = A4[0]
PAGE_HEIGHT: Final[float] = A4[1]

PAGE_MARGIN: Final[float] = 18 * mm
HEADER_HEIGHT: Final[float] = 18 * mm
FOOTER_HEIGHT: Final[float] = 13 * mm

TABLE_LABEL_WIDTH: Final[float] = 72 * mm
TABLE_VALUE_WIDTH: Final[float] = 95 * mm

MAX_AI_VALUE_LENGTH: Final[int] = 2_000

UNAVAILABLE_VALUE: Final[str] = "Unavailable"


# ============================================================
# Exceptions
# ============================================================


class PDFReportError(RuntimeError):
    """
    Base exception raised by PDF report generation.
    """


class PDFReportValidationError(
    PDFReportError
):
    """
    Raised when PDF report input is invalid.
    """


class PDFReportGenerationError(
    PDFReportError
):
    """
    Raised when ReportLab cannot generate or save the PDF.
    """


# ============================================================
# Validation
# ============================================================


def _validate_report(
    report: PortfolioReport,
) -> PortfolioReport:
    """
    Validate the report supplied to the PDF service.

    Args:
        report:
            Expected PortfolioReport instance.

    Returns:
        Validated report.

    Raises:
        TypeError:
            When report is not a PortfolioReport.
    """

    if not isinstance(
        report,
        PortfolioReport,
    ):
        raise TypeError(
            "report must be a PortfolioReport."
        )

    return report


def _validate_output_path(
    output_path: str | Path,
) -> Path:
    """
    Validate and normalize a PDF output path.

    Args:
        output_path:
            Target path for the generated PDF.

    Returns:
        Resolved Path ending in ``.pdf``.

    Raises:
        TypeError:
            When output_path is not a string or Path.

        PDFReportValidationError:
            When the path is blank or does not use a PDF extension.
    """

    if not isinstance(
        output_path,
        (str, Path),
    ):
        raise TypeError(
            "output_path must be a string or Path."
        )

    if isinstance(
        output_path,
        str,
    ) and not output_path.strip():
        raise PDFReportValidationError(
            "output_path cannot be blank."
        )

    path = Path(
        output_path
    ).expanduser()

    if path.suffix.lower() != ".pdf":
        raise PDFReportValidationError(
            "output_path must end with .pdf."
        )

    return path.resolve()


def _validate_filename(
    filename: str,
) -> str:
    """
    Validate a downloadable PDF filename.
    """

    if not isinstance(
        filename,
        str,
    ):
        raise TypeError(
            "filename must be a string."
        )

    normalized = filename.strip()

    if not normalized:
        raise PDFReportValidationError(
            "filename cannot be blank."
        )

    if Path(normalized).name != normalized:
        raise PDFReportValidationError(
            "filename must not contain directory components."
        )

    if not normalized.lower().endswith(
        ".pdf"
    ):
        raise PDFReportValidationError(
            "filename must end with .pdf."
        )

    return normalized


# ============================================================
# Formatting Helpers
# ============================================================


def _format_integer(
    value: int,
) -> str:
    """
    Format an integer using thousands separators.
    """

    if isinstance(
        value,
        bool,
    ) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            "value must be an integer."
        )

    return f"{value:,}"


def _format_duration(
    duration_days: int,
) -> str:
    """
    Format a historical duration for report display.
    """

    if isinstance(
        duration_days,
        bool,
    ) or not isinstance(
        duration_days,
        int,
    ):
        raise TypeError(
            "duration_days must be an integer."
        )

    if duration_days < 0:
        raise PDFReportValidationError(
            "duration_days cannot be negative."
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

    years, days = divmod(
        duration_days,
        365,
    )

    year_unit = (
        "year"
        if years == 1
        else "years"
    )

    if days == 0:
        return (
            f"{years:,} {year_unit}"
        )

    day_unit = (
        "day"
        if days == 1
        else "days"
    )

    return (
        f"{years:,} {year_unit}, "
        f"{days:,} {day_unit}"
    )


def _safe_text(
    value: Any,
    *,
    maximum_length: int = MAX_AI_VALUE_LENGTH,
) -> str:
    """
    Convert arbitrary report content to bounded display text.
    """

    if isinstance(
        maximum_length,
        bool,
    ) or not isinstance(
        maximum_length,
        int,
    ):
        raise TypeError(
            "maximum_length must be an integer."
        )

    if maximum_length <= 0:
        raise PDFReportValidationError(
            "maximum_length must be greater than zero."
        )

    if value is None:
        return UNAVAILABLE_VALUE

    if isinstance(
        value,
        bool,
    ):
        text = (
            "Yes"
            if value
            else "No"
        )

    elif isinstance(
        value,
        float,
    ):
        text = (
            f"{value:,.4f}"
            if isfinite(value)
            else UNAVAILABLE_VALUE
        )

    elif isinstance(
        value,
        Mapping,
    ):
        text = "; ".join(
            f"{key}: {_safe_text(item, maximum_length=500)}"
            for key, item in value.items()
        )

    elif isinstance(
        value,
        Sequence,
    ) and not isinstance(
        value,
        (str, bytes),
    ):
        text = "; ".join(
            _safe_text(
                item,
                maximum_length=500,
            )
            for item in value
        )

    else:
        text = str(value)

    normalized = " ".join(
        text.split()
    )

    if len(normalized) <= maximum_length:
        return normalized

    return (
        normalized[
            : maximum_length - 3
        ].rstrip()
        + "..."
    )


# ============================================================
# PDF Styles
# ============================================================


def _build_styles() -> StyleSheet1:
    """
    Build the ReportLab paragraph styles used by the PDF.
    """

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=7 * mm,
            textColor=colors.HexColor(
                "#17365D"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
            textColor=colors.HexColor(
                "#5A6573"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            alignment=TA_LEFT,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
            textColor=colors.HexColor(
                "#17365D"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
            textColor=colors.HexColor(
                "#25313C"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor(
                "#5A6573"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportWarning",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=4 * mm,
            borderPadding=2 * mm,
            borderColor=colors.HexColor(
                "#D97706"
            ),
            borderWidth=0.5,
            textColor=colors.HexColor(
                "#7C2D12"
            ),
            backColor=colors.HexColor(
                "#FFF7ED"
            ),
            spaceAfter=2 * mm,
        )
    )

    return styles


# ============================================================
# ReportLab Document Helpers
# ============================================================


def _draw_page_header_footer(
    canvas: Any,
    document: BaseDocTemplate,
    *,
    application_name: str,
    report_version: str,
) -> None:
    """
    Draw a consistent header and footer on every PDF page.
    """

    canvas.saveState()

    canvas.setStrokeColor(
        colors.HexColor(
            "#D9E1EA"
        )
    )

    canvas.setLineWidth(
        0.5
    )

    header_y = (
        PAGE_HEIGHT
        - 12 * mm
    )

    canvas.line(
        PAGE_MARGIN,
        header_y - 3 * mm,
        PAGE_WIDTH - PAGE_MARGIN,
        header_y - 3 * mm,
    )

    canvas.setFont(
        "Helvetica-Bold",
        8,
    )

    canvas.setFillColor(
        colors.HexColor(
            "#17365D"
        )
    )

    canvas.drawString(
        PAGE_MARGIN,
        header_y,
        application_name,
    )

    canvas.setFont(
        "Helvetica",
        8,
    )

    canvas.setFillColor(
        colors.HexColor(
            "#5A6573"
        )
    )

    canvas.drawRightString(
        PAGE_WIDTH - PAGE_MARGIN,
        header_y,
        f"Report version {report_version}",
    )

    footer_y = 10 * mm

    canvas.line(
        PAGE_MARGIN,
        footer_y + 5 * mm,
        PAGE_WIDTH - PAGE_MARGIN,
        footer_y + 5 * mm,
    )

    canvas.drawString(
        PAGE_MARGIN,
        footer_y,
        "Generated for informational and analytical purposes.",
    )

    canvas.drawRightString(
        PAGE_WIDTH - PAGE_MARGIN,
        footer_y,
        f"Page {document.page}",
    )

    canvas.restoreState()


def _build_metric_table(
    rows: Sequence[
        tuple[str, str]
    ],
    styles: StyleSheet1,
) -> Table:
    """
    Build a two-column report metric table.
    """

    table_data = [
        [
            Paragraph(
                str(label),
                styles["ReportBody"],
            ),
            Paragraph(
                str(value),
                styles["ReportBody"],
            ),
        ]
        for label, value in rows
    ]

    table = Table(
        table_data,
        colWidths=[
            TABLE_LABEL_WIDTH,
            TABLE_VALUE_WIDTH,
        ],
        repeatRows=0,
        hAlign="LEFT",
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#EEF3F8"
                    ),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#17365D"
                    ),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (1, 0),
                    (1, -1),
                    "Helvetica",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor(
                        "#D9E1EA"
                    ),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return table


# ============================================================
# Section Builders
# ============================================================


def _build_title_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build the PDF title and metadata section.
    """

    return [
        Spacer(
            1,
            7 * mm,
        ),
        Paragraph(
            report.metadata.title,
            styles["ReportTitle"],
        ),
        Paragraph(
            (
                f"{report.metadata.application_name}"
                f" | Generated "
                f"{format_datetime(report.metadata.generated_at)}"
            ),
            styles["ReportSubtitle"],
        ),
    ]


def _build_performance_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build the current portfolio performance section.
    """

    performance = report.performance

    rows = [
        (
            "Total Investment",
            format_currency(
                performance.total_investment
            ),
        ),
        (
            "Current Portfolio Value",
            format_currency(
                performance.current_value
            ),
        ),
        (
            "Total Gain / Loss",
            format_currency(
                performance.total_gain
            ),
        ),
        (
            "Absolute Return",
            format_percentage(
                performance.absolute_return_percentage,
                include_sign=True,
            ),
        ),
        (
            "Total Holdings",
            _format_integer(
                performance.total_holdings
            ),
        ),
        (
            "Profitable Holdings",
            _format_integer(
                performance.profitable_holdings
            ),
        ),
        (
            "Loss-Making Holdings",
            _format_integer(
                performance.loss_making_holdings
            ),
        ),
    ]

    return [
        Paragraph(
            "Portfolio Performance",
            styles["ReportSection"],
        ),
        _build_metric_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            3 * mm,
        ),
    ]


def _build_history_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build historical analytics when available.
    """

    history = report.history

    if history is None:
        return [
            Paragraph(
                "Historical Analytics",
                styles["ReportSection"],
            ),
            Paragraph(
                (
                    "Historical analytics were not available "
                    "when this report was generated."
                ),
                styles["ReportBody"],
            ),
        ]

    cagr_value = (
        format_percentage(
            history.cagr.cagr_percent,
            include_sign=True,
        )
        if history.cagr is not None
        else UNAVAILABLE_VALUE
    )

    drawdown_value = (
        format_percentage(
            history.drawdown.maximum_drawdown_percent
        )
        if history.drawdown is not None
        else UNAVAILABLE_VALUE
    )

    volatility_value = (
        format_percentage(
            history.volatility.annualised_volatility_percent
        )
        if history.volatility is not None
        else UNAVAILABLE_VALUE
    )

    rows = [
        (
            "First Snapshot",
            history.start_date.strftime(
                "%d %b %Y"
            ),
        ),
        (
            "Latest Snapshot",
            history.end_date.strftime(
                "%d %b %Y"
            ),
        ),
        (
            "Observations",
            _format_integer(
                history.observation_count
            ),
        ),
        (
            "History Duration",
            _format_duration(
                history.duration_days
            ),
        ),
        (
            "Starting Value",
            format_currency(
                history.starting_value
            ),
        ),
        (
            "Latest Value",
            format_currency(
                history.latest_value
            ),
        ),
        (
            "Lowest Value",
            format_currency(
                history.minimum_value
            ),
        ),
        (
            "Highest Value",
            format_currency(
                history.maximum_value
            ),
        ),
        (
            "Average Value",
            format_currency(
                history.average_value
            ),
        ),
        (
            "Absolute Growth",
            format_currency(
                history.absolute_growth
            ),
        ),
        (
            "Total Growth",
            format_percentage(
                history.total_growth_percent,
                include_sign=True,
            ),
        ),
        (
            "Historical CAGR",
            cagr_value,
        ),
        (
            "Maximum Drawdown",
            drawdown_value,
        ),
        (
            "Annualised Volatility",
            volatility_value,
        ),
    ]

    return [
        Paragraph(
            "Historical Analytics",
            styles["ReportSection"],
        ),
        _build_metric_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            3 * mm,
        ),
    ]


def _build_advanced_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build an advanced-analytics availability summary.
    """

    advanced = report.advanced_analytics

    if advanced is None:
        return [
            Paragraph(
                "Advanced Analytics",
                styles["ReportSection"],
            ),
            Paragraph(
                (
                    "Advanced analytics were not available "
                    "when this report was generated."
                ),
                styles["ReportBody"],
            ),
        ]

    status = _safe_text(
        getattr(
            advanced,
            "status",
            UNAVAILABLE_VALUE,
        )
    )

    available_metrics = getattr(
        advanced,
        "available_metrics",
        (),
    )

    unavailable_metrics = getattr(
        advanced,
        "unavailable_metrics",
        (),
    )

    failures = getattr(
        advanced,
        "failures",
        (),
    )

    rows = [
        (
            "Status",
            status.title(),
        ),
        (
            "Available Metrics",
            (
                ", ".join(
                    str(metric)
                    for metric in available_metrics
                )
                if available_metrics
                else UNAVAILABLE_VALUE
            ),
        ),
        (
            "Unavailable Metrics",
            (
                ", ".join(
                    str(metric)
                    for metric in unavailable_metrics
                )
                if unavailable_metrics
                else "None"
            ),
        ),
        (
            "Service Failures",
            (
                _format_integer(
                    len(failures)
                )
                if hasattr(
                    failures,
                    "__len__",
                )
                else UNAVAILABLE_VALUE
            ),
        ),
    ]

    return [
        Paragraph(
            "Advanced Analytics",
            styles["ReportSection"],
        ),
        _build_metric_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            3 * mm,
        ),
    ]


def _build_ai_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build the optional AI summary section.
    """

    if not report.ai_summary:
        return [
            Paragraph(
                "AI Portfolio Insights",
                styles["ReportSection"],
            ),
            Paragraph(
                (
                    "AI portfolio insights were not included "
                    "in this report."
                ),
                styles["ReportBody"],
            ),
        ]

    rows = [
        (
            _safe_text(
                key,
                maximum_length=100,
            ),
            _safe_text(
                value
            ),
        )
        for key, value in report.ai_summary.items()
    ]

    return [
        Paragraph(
            "AI Portfolio Insights",
            styles["ReportSection"],
        ),
        _build_metric_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            3 * mm,
        ),
    ]


def _build_notes_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build optional report notes.
    """

    if not report.notes:
        return []

    content: list[Any] = [
        Paragraph(
            "Notes",
            styles["ReportSection"],
        )
    ]

    for note in report.notes:
        content.append(
            Paragraph(
                f"- {_safe_text(note)}",
                styles["ReportBody"],
            )
        )

    return content


def _build_warnings_section(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build optional report warnings.
    """

    if not report.warnings:
        return []

    content: list[Any] = [
        Paragraph(
            "Warnings and Limitations",
            styles["ReportSection"],
        )
    ]

    for warning in report.warnings:
        content.append(
            Paragraph(
                _safe_text(warning),
                styles["ReportWarning"],
            )
        )

    return content


def _build_disclaimer_section(
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build the final investment disclaimer.
    """

    return [
        Spacer(
            1,
            5 * mm,
        ),
        Paragraph(
            "Important Disclaimer",
            styles["ReportSection"],
        ),
        Paragraph(
            (
                "This report is generated for informational and analytical "
                "purposes only. It does not constitute investment, tax, legal, "
                "or financial advice. Mutual fund investments are subject to "
                "market risks. Review scheme documents and consult a qualified "
                "financial professional before making investment decisions."
            ),
            styles["ReportSmall"],
        ),
    ]


def _build_story(
    report: PortfolioReport,
    styles: StyleSheet1,
) -> list[Any]:
    """
    Build the complete ReportLab document story.
    """

    story: list[Any] = []

    story.extend(
        _build_title_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_performance_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_history_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_advanced_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_ai_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_notes_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_warnings_section(
            report,
            styles,
        )
    )

    story.extend(
        _build_disclaimer_section(
            styles
        )
    )

    return story


# ============================================================
# PDF Service
# ============================================================


class PDFReportService:
    """
    Generate professional portfolio reports as PDF bytes or files.
    """

    @property
    def mime_type(self) -> str:
        """
        Return the PDF MIME type.
        """

        return PDF_MIME_TYPE

    @property
    def default_filename(self) -> str:
        """
        Return the default downloadable PDF filename.
        """

        return DEFAULT_PDF_FILENAME

    def generate_bytes(
        self,
        report: PortfolioReport,
    ) -> bytes:
        """
        Generate a portfolio report as PDF bytes.

        Args:
            report:
                Fully assembled PortfolioReport.

        Returns:
            Generated PDF bytes.

        Raises:
            TypeError:
                When report is not a PortfolioReport.

            PDFReportGenerationError:
                When ReportLab cannot build the document.
        """

        validated_report = _validate_report(
            report
        )

        styles = _build_styles()
        buffer = BytesIO()

        try:
            document = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=PAGE_MARGIN,
                leftMargin=PAGE_MARGIN,
                topMargin=HEADER_HEIGHT,
                bottomMargin=FOOTER_HEIGHT,
                title=validated_report.metadata.title,
                author=(
                    validated_report
                    .metadata
                    .application_name
                ),
                subject=(
                    "Professional mutual fund "
                    "portfolio analytics report"
                ),
            )

            story = _build_story(
                validated_report,
                styles,
            )

            page_callback = lambda canvas, doc: (
                _draw_page_header_footer(
                    canvas,
                    doc,
                    application_name=(
                        validated_report
                        .metadata
                        .application_name
                    ),
                    report_version=(
                        validated_report
                        .metadata
                        .version
                    ),
                )
            )

            document.build(
                story,
                onFirstPage=page_callback,
                onLaterPages=page_callback,
            )

            pdf_bytes = buffer.getvalue()

        except PDFReportError:
            raise

        except Exception as error:
            raise PDFReportGenerationError(
                "Unable to generate the portfolio PDF report: "
                f"{error}"
            ) from error

        finally:
            buffer.close()

        if not pdf_bytes.startswith(
            b"%PDF"
        ):
            raise PDFReportGenerationError(
                "Generated output is not a valid PDF document."
            )

        return pdf_bytes

    def save(
        self,
        report: PortfolioReport,
        output_path: str | Path,
        *,
        create_parent_directories: bool = True,
        overwrite: bool = False,
    ) -> Path:
        """
        Generate and save a portfolio PDF report.

        Args:
            report:
                Fully assembled PortfolioReport.

            output_path:
                Destination PDF path.

            create_parent_directories:
                Whether missing parent directories should be created.

            overwrite:
                Whether an existing file may be replaced.

        Returns:
            Resolved output path.

        Raises:
            TypeError:
                When boolean options or output_path have invalid types.

            PDFReportValidationError:
                When the output path is invalid or already exists and
                overwrite is False.

            PDFReportGenerationError:
                When writing the generated PDF fails.
        """

        if not isinstance(
            create_parent_directories,
            bool,
        ):
            raise TypeError(
                "create_parent_directories must be a boolean."
            )

        if not isinstance(
            overwrite,
            bool,
        ):
            raise TypeError(
                "overwrite must be a boolean."
            )

        path = _validate_output_path(
            output_path
        )

        if path.exists() and not overwrite:
            raise PDFReportValidationError(
                "The output PDF already exists. "
                "Set overwrite=True to replace it."
            )

        parent = path.parent

        if not parent.exists():
            if not create_parent_directories:
                raise PDFReportValidationError(
                    "The output directory does not exist."
                )

            try:
                parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            except Exception as error:
                raise PDFReportGenerationError(
                    "Unable to create the output directory: "
                    f"{error}"
                ) from error

        pdf_bytes = self.generate_bytes(
            report
        )

        try:
            path.write_bytes(
                pdf_bytes
            )

        except Exception as error:
            raise PDFReportGenerationError(
                "Unable to save the portfolio PDF report: "
                f"{error}"
            ) from error

        return path

    def prepare_download(
        self,
        report: PortfolioReport,
        *,
        filename: str = DEFAULT_PDF_FILENAME,
    ) -> tuple[bytes, str, str]:
        """
        Prepare PDF bytes and metadata for a Streamlit download button.

        Args:
            report:
                Fully assembled PortfolioReport.

            filename:
                Download filename.

        Returns:
            Tuple containing:

            - PDF bytes
            - Validated filename
            - PDF MIME type
        """

        resolved_filename = _validate_filename(
            filename
        )

        return (
            self.generate_bytes(
                report
            ),
            resolved_filename,
            self.mime_type,
        )


# ============================================================
# Convenience APIs
# ============================================================


def generate_portfolio_pdf(
    report: PortfolioReport,
) -> bytes:
    """
    Generate PortfolioReport as PDF bytes.
    """

    service = PDFReportService()

    return service.generate_bytes(
        report
    )


def save_portfolio_pdf(
    report: PortfolioReport,
    output_path: str | Path,
    *,
    create_parent_directories: bool = True,
    overwrite: bool = False,
) -> Path:
    """
    Generate and save a PortfolioReport PDF.
    """

    service = PDFReportService()

    return service.save(
        report,
        output_path,
        create_parent_directories=(
            create_parent_directories
        ),
        overwrite=overwrite,
    )


__all__ = [
    "DEFAULT_PDF_FILENAME",
    "MAX_AI_VALUE_LENGTH",
    "PDF_MIME_TYPE",
    "PDFReportError",
    "PDFReportGenerationError",
    "PDFReportService",
    "PDFReportValidationError",
    "UNAVAILABLE_VALUE",
    "generate_portfolio_pdf",
    "save_portfolio_pdf",
]