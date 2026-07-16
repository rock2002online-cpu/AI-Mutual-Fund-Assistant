"""
Shared reporting assets and branding configuration.

This module centralizes reusable visual constants and helper functions used
by PDF, Excel, and dashboard reporting components.

Responsibilities
----------------
- Define the reporting color palette.
- Define standard typography and spacing values.
- Define report names, filenames, and MIME types.
- Provide immutable branding metadata.
- Validate color and spacing configuration.
- Expose safe helpers for consuming shared reporting assets.

This module contains no portfolio calculations and performs no service calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from re import fullmatch
from typing import Final


# ============================================================
# Exceptions
# ============================================================


class ReportAssetError(RuntimeError):
    """
    Base exception raised by report asset operations.
    """


class ReportAssetValidationError(
    ReportAssetError
):
    """
    Raised when a report asset value is invalid.
    """


# ============================================================
# Core Branding Constants
# ============================================================

APPLICATION_NAME: Final[str] = (
    "AI Mutual Fund Assistant"
)

REPORTING_MODULE_NAME: Final[str] = (
    "Professional Reporting"
)

DEFAULT_REPORT_TITLE: Final[str] = (
    "Portfolio Analytics Report"
)

REPORT_DISCLAIMER: Final[str] = (
    "This report is generated for informational and analytical purposes "
    "only. It does not constitute investment, tax, legal, or financial "
    "advice. Mutual fund investments are subject to market risks. Review "
    "scheme documents and consult a qualified financial professional before "
    "making investment decisions."
)

REPORT_FOOTER_TEXT: Final[str] = (
    "Generated for informational and analytical purposes."
)

PDF_FILENAME: Final[str] = (
    "portfolio_report.pdf"
)

EXCEL_FILENAME: Final[str] = (
    "portfolio_report.xlsx"
)

PDF_MIME_TYPE: Final[str] = (
    "application/pdf"
)

EXCEL_MIME_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


# ============================================================
# Color Palette
# ============================================================

PRIMARY_NAVY: Final[str] = "17365D"
PRIMARY_BLUE: Final[str] = "4472C4"
SECONDARY_BLUE: Final[str] = "5B9BD5"

LIGHT_BLUE: Final[str] = "D9EAF7"
LIGHTER_BLUE: Final[str] = "EEF3F8"

TEXT_DARK: Final[str] = "25313C"
TEXT_MUTED: Final[str] = "5A6573"
WHITE: Final[str] = "FFFFFF"

BORDER_LIGHT: Final[str] = "D9E1EA"

SUCCESS_GREEN: Final[str] = "2E7D32"
SUCCESS_BACKGROUND: Final[str] = "E8F5E9"

WARNING_AMBER: Final[str] = "D97706"
WARNING_TEXT: Final[str] = "7C2D12"
WARNING_BACKGROUND: Final[str] = "FFF7ED"

ERROR_RED: Final[str] = "C62828"
ERROR_BACKGROUND: Final[str] = "FFEBEE"

NEUTRAL_BACKGROUND: Final[str] = "F7F9FC"


# ============================================================
# Typography
# ============================================================

PRIMARY_FONT_NAME: Final[str] = (
    "Helvetica"
)

PRIMARY_FONT_BOLD: Final[str] = (
    "Helvetica-Bold"
)

EXCEL_FONT_NAME: Final[str] = (
    "Calibri"
)

TITLE_FONT_SIZE: Final[int] = 21
SECTION_FONT_SIZE: Final[int] = 13
BODY_FONT_SIZE: Final[int] = 9
SMALL_FONT_SIZE: Final[int] = 8

EXCEL_TITLE_FONT_SIZE: Final[int] = 18
EXCEL_SECTION_FONT_SIZE: Final[int] = 12
EXCEL_BODY_FONT_SIZE: Final[int] = 10
EXCEL_SMALL_FONT_SIZE: Final[int] = 9


# ============================================================
# Layout and Spacing
# ============================================================

DEFAULT_PAGE_MARGIN_MM: Final[int] = 18
DEFAULT_HEADER_HEIGHT_MM: Final[int] = 18
DEFAULT_FOOTER_HEIGHT_MM: Final[int] = 13

SECTION_SPACING_MM: Final[int] = 4
CONTENT_SPACING_MM: Final[int] = 3

EXCEL_MINIMUM_COLUMN_WIDTH: Final[int] = 12
EXCEL_MAXIMUM_COLUMN_WIDTH: Final[int] = 60
EXCEL_COLUMN_PADDING: Final[int] = 2

MAX_REPORT_TEXT_LENGTH: Final[int] = 2_000
MAX_EXCEL_CELL_TEXT_LENGTH: Final[int] = 32_000


# ============================================================
# Data Classes
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class ReportColorPalette:
    """
    Immutable reporting color palette.
    """

    primary: str
    secondary: str
    accent: str
    background: str
    label_background: str
    text: str
    muted_text: str
    border: str
    success: str
    warning: str
    error: str

    def __post_init__(
        self,
    ) -> None:
        """
        Validate all color values after construction.
        """

        for field_name in (
            "primary",
            "secondary",
            "accent",
            "background",
            "label_background",
            "text",
            "muted_text",
            "border",
            "success",
            "warning",
            "error",
        ):
            value = getattr(
                self,
                field_name,
            )

            _validate_hex_color(
                value,
                parameter_name=field_name,
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ReportTypography:
    """
    Immutable reporting typography configuration.
    """

    primary_font: str
    bold_font: str
    excel_font: str
    title_size: int
    section_size: int
    body_size: int
    small_size: int

    def __post_init__(
        self,
    ) -> None:
        """
        Validate typography values after construction.
        """

        for field_name in (
            "primary_font",
            "bold_font",
            "excel_font",
        ):
            _validate_non_blank_text(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )

        for field_name in (
            "title_size",
            "section_size",
            "body_size",
            "small_size",
        ):
            _validate_positive_integer(
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
class ReportLayout:
    """
    Immutable report layout and spacing configuration.
    """

    page_margin_mm: int
    header_height_mm: int
    footer_height_mm: int
    section_spacing_mm: int
    content_spacing_mm: int
    excel_minimum_column_width: int
    excel_maximum_column_width: int
    excel_column_padding: int

    def __post_init__(
        self,
    ) -> None:
        """
        Validate layout values after construction.
        """

        for field_name in (
            "page_margin_mm",
            "header_height_mm",
            "footer_height_mm",
            "section_spacing_mm",
            "content_spacing_mm",
            "excel_minimum_column_width",
            "excel_maximum_column_width",
        ):
            _validate_positive_integer(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )

        _validate_non_negative_integer(
            self.excel_column_padding,
            parameter_name="excel_column_padding",
        )

        if (
            self.excel_maximum_column_width
            < self.excel_minimum_column_width
        ):
            raise ReportAssetValidationError(
                "excel_maximum_column_width must be greater than or equal "
                "to excel_minimum_column_width."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ReportBranding:
    """
    Immutable report branding metadata.
    """

    application_name: str
    module_name: str
    default_title: str
    footer_text: str
    disclaimer: str
    logo_path: Path | None = None

    def __post_init__(
        self,
    ) -> None:
        """
        Validate branding metadata after construction.
        """

        for field_name in (
            "application_name",
            "module_name",
            "default_title",
            "footer_text",
            "disclaimer",
        ):
            _validate_non_blank_text(
                getattr(
                    self,
                    field_name,
                ),
                parameter_name=field_name,
            )

        if (
            self.logo_path is not None
            and not isinstance(
                self.logo_path,
                Path,
            )
        ):
            raise TypeError(
                "logo_path must be a Path or None."
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
        raise ReportAssetValidationError(
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
        raise ReportAssetValidationError(
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
        raise ReportAssetValidationError(
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
        raise ReportAssetValidationError(
            f"{normalized_parameter_name} cannot be negative."
        )

    return value


def _validate_hex_color(
    value: str,
    *,
    parameter_name: str = "color",
) -> str:
    """
    Validate and normalize a six-character hexadecimal color.

    Both ``17365D`` and ``#17365D`` are accepted.

    Returns:
        Uppercase color without the leading ``#``.
    """

    normalized_parameter_name = (
        _validate_non_blank_text(
            parameter_name,
            parameter_name="parameter_name",
        )
    )

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{normalized_parameter_name} must be a string."
        )

    normalized = value.strip()

    if normalized.startswith("#"):
        normalized = normalized[1:]

    if not fullmatch(
        r"[0-9A-Fa-f]{6}",
        normalized,
    ):
        raise ReportAssetValidationError(
            f"{normalized_parameter_name} must be a six-character "
            "hexadecimal color."
        )

    return normalized.upper()


# ============================================================
# Public Helpers
# ============================================================


def as_hex_color(
    value: str,
    *,
    include_hash: bool = False,
) -> str:
    """
    Return a normalized hexadecimal color.

    Args:
        value:
            Six-character hexadecimal color, optionally prefixed by ``#``.

        include_hash:
            Whether to prefix the returned color with ``#``.
    """

    if not isinstance(
        include_hash,
        bool,
    ):
        raise TypeError(
            "include_hash must be a boolean."
        )

    normalized = _validate_hex_color(
        value
    )

    if include_hash:
        return f"#{normalized}"

    return normalized


def resolve_logo_path(
    logo_path: str | Path | None,
    *,
    require_existing: bool = False,
) -> Path | None:
    """
    Resolve an optional logo path.

    Args:
        logo_path:
            Logo path or None.

        require_existing:
            Whether the path must already exist.

    Returns:
        Resolved logo path or None.
    """

    if not isinstance(
        require_existing,
        bool,
    ):
        raise TypeError(
            "require_existing must be a boolean."
        )

    if logo_path is None:
        return None

    if not isinstance(
        logo_path,
        (str, Path),
    ):
        raise TypeError(
            "logo_path must be a string, Path, or None."
        )

    if (
        isinstance(
            logo_path,
            str,
        )
        and not logo_path.strip()
    ):
        raise ReportAssetValidationError(
            "logo_path cannot be blank."
        )

    resolved = Path(
        logo_path
    ).expanduser().resolve()

    if require_existing:
        if not resolved.exists():
            raise ReportAssetValidationError(
                "logo_path does not exist."
            )

        if not resolved.is_file():
            raise ReportAssetValidationError(
                "logo_path must reference a file."
            )

    return resolved


# ============================================================
# Default Immutable Assets
# ============================================================

DEFAULT_COLOR_PALETTE: Final[
    ReportColorPalette
] = ReportColorPalette(
    primary=PRIMARY_NAVY,
    secondary=PRIMARY_BLUE,
    accent=SECONDARY_BLUE,
    background=NEUTRAL_BACKGROUND,
    label_background=LIGHTER_BLUE,
    text=TEXT_DARK,
    muted_text=TEXT_MUTED,
    border=BORDER_LIGHT,
    success=SUCCESS_GREEN,
    warning=WARNING_AMBER,
    error=ERROR_RED,
)

DEFAULT_TYPOGRAPHY: Final[
    ReportTypography
] = ReportTypography(
    primary_font=PRIMARY_FONT_NAME,
    bold_font=PRIMARY_FONT_BOLD,
    excel_font=EXCEL_FONT_NAME,
    title_size=TITLE_FONT_SIZE,
    section_size=SECTION_FONT_SIZE,
    body_size=BODY_FONT_SIZE,
    small_size=SMALL_FONT_SIZE,
)

DEFAULT_LAYOUT: Final[
    ReportLayout
] = ReportLayout(
    page_margin_mm=DEFAULT_PAGE_MARGIN_MM,
    header_height_mm=DEFAULT_HEADER_HEIGHT_MM,
    footer_height_mm=DEFAULT_FOOTER_HEIGHT_MM,
    section_spacing_mm=SECTION_SPACING_MM,
    content_spacing_mm=CONTENT_SPACING_MM,
    excel_minimum_column_width=(
        EXCEL_MINIMUM_COLUMN_WIDTH
    ),
    excel_maximum_column_width=(
        EXCEL_MAXIMUM_COLUMN_WIDTH
    ),
    excel_column_padding=(
        EXCEL_COLUMN_PADDING
    ),
)

DEFAULT_BRANDING: Final[
    ReportBranding
] = ReportBranding(
    application_name=APPLICATION_NAME,
    module_name=REPORTING_MODULE_NAME,
    default_title=DEFAULT_REPORT_TITLE,
    footer_text=REPORT_FOOTER_TEXT,
    disclaimer=REPORT_DISCLAIMER,
)


# ============================================================
# Public Exports
# ============================================================

__all__ = [
    "APPLICATION_NAME",
    "BORDER_LIGHT",
    "DEFAULT_BRANDING",
    "DEFAULT_COLOR_PALETTE",
    "DEFAULT_LAYOUT",
    "DEFAULT_REPORT_TITLE",
    "DEFAULT_TYPOGRAPHY",
    "ERROR_BACKGROUND",
    "ERROR_RED",
    "EXCEL_BODY_FONT_SIZE",
    "EXCEL_COLUMN_PADDING",
    "EXCEL_FILENAME",
    "EXCEL_FONT_NAME",
    "EXCEL_MAXIMUM_COLUMN_WIDTH",
    "EXCEL_MIME_TYPE",
    "EXCEL_MINIMUM_COLUMN_WIDTH",
    "EXCEL_SECTION_FONT_SIZE",
    "EXCEL_SMALL_FONT_SIZE",
    "EXCEL_TITLE_FONT_SIZE",
    "LIGHTER_BLUE",
    "LIGHT_BLUE",
    "MAX_EXCEL_CELL_TEXT_LENGTH",
    "MAX_REPORT_TEXT_LENGTH",
    "NEUTRAL_BACKGROUND",
    "PDF_FILENAME",
    "PDF_MIME_TYPE",
    "PRIMARY_BLUE",
    "PRIMARY_FONT_BOLD",
    "PRIMARY_FONT_NAME",
    "PRIMARY_NAVY",
    "REPORT_DISCLAIMER",
    "REPORT_FOOTER_TEXT",
    "REPORTING_MODULE_NAME",
    "ReportAssetError",
    "ReportAssetValidationError",
    "ReportBranding",
    "ReportColorPalette",
    "ReportLayout",
    "ReportTypography",
    "SECONDARY_BLUE",
    "SUCCESS_BACKGROUND",
    "SUCCESS_GREEN",
    "TEXT_DARK",
    "TEXT_MUTED",
    "WARNING_AMBER",
    "WARNING_BACKGROUND",
    "WARNING_TEXT",
    "WHITE",
    "as_hex_color",
    "resolve_logo_path",
]