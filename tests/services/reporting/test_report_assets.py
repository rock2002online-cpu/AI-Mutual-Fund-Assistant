"""
Unit tests for shared reporting assets.

Coverage includes:

- Validation helpers
- Hex color validation
- Public helper functions
- Immutable dataclasses
- Default assets
- Branding metadata
- Layout configuration
- Typography configuration
"""

from __future__ import annotations

from pathlib import Path

import pytest

import services.reporting.report_assets as assets

from services.reporting.report_assets import (
    APPLICATION_NAME,
    DEFAULT_BRANDING,
    DEFAULT_COLOR_PALETTE,
    DEFAULT_LAYOUT,
    DEFAULT_REPORT_TITLE,
    DEFAULT_TYPOGRAPHY,
    EXCEL_FILENAME,
    EXCEL_MIME_TYPE,
    PDF_FILENAME,
    PDF_MIME_TYPE,
    ReportAssetValidationError,
    ReportBranding,
    ReportColorPalette,
    ReportLayout,
    ReportTypography,
    _validate_hex_color,
    _validate_non_blank_text,
    _validate_non_negative_integer,
    _validate_positive_integer,
    as_hex_color,
    resolve_logo_path,
)
# ============================================================
# _validate_non_blank_text
# ============================================================


def test_validate_non_blank_text_returns_trimmed_value():
    assert (
        _validate_non_blank_text(
            "  Hello  ",
            parameter_name="value",
        )
        == "Hello"
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
):
    with pytest.raises(
        ReportAssetValidationError,
        match="value cannot be blank",
    ):
        _validate_non_blank_text(
            value,
            parameter_name="value",
        )


def test_validate_non_blank_text_rejects_non_string():
    with pytest.raises(
        TypeError,
        match="value must be a string",
    ):
        _validate_non_blank_text(
            123,
            parameter_name="value",
        )


def test_validate_non_blank_text_rejects_invalid_parameter_name():
    with pytest.raises(
        ReportAssetValidationError,
        match="parameter_name cannot be blank",
    ):
        _validate_non_blank_text(
            "abc",
            parameter_name=" ",
        )

# ============================================================
# _validate_positive_integer
# ============================================================


@pytest.mark.parametrize(
    "value",
    [
        1,
        5,
        100,
    ],
)
def test_validate_positive_integer_accepts_valid(
    value: int,
):
    assert (
        _validate_positive_integer(
            value,
            parameter_name="size",
        )
        == value
    )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        -50,
    ],
)
def test_validate_positive_integer_rejects_non_positive(
    value: int,
):
    with pytest.raises(
        ReportAssetValidationError,
        match="size must be greater than zero",
    ):
        _validate_positive_integer(
            value,
            parameter_name="size",
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        1.5,
        "10",
    ],
)
def test_validate_positive_integer_rejects_invalid_type(
    value,
):
    with pytest.raises(
        TypeError,
    ):
        _validate_positive_integer(
            value,
            parameter_name="size",
        )
# ============================================================
# _validate_non_negative_integer
# ============================================================


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        100,
    ],
)
def test_validate_non_negative_integer_accepts_valid(
    value: int,
):
    assert (
        _validate_non_negative_integer(
            value,
            parameter_name="padding",
        )
        == value
    )


def test_validate_non_negative_integer_rejects_negative():
    with pytest.raises(
        ReportAssetValidationError,
        match="padding cannot be negative",
    ):
        _validate_non_negative_integer(
            -1,
            parameter_name="padding",
        )
# ============================================================
# Hex Color Validation
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("17365D", "17365D"),
        ("#17365D", "17365D"),
        ("abcdef", "ABCDEF"),
        (" #abcdef ", "ABCDEF"),
        ("000000", "000000"),
        ("FFFFFF", "FFFFFF"),
    ],
)
def test_validate_hex_color_accepts_valid_values(
    value: str,
    expected: str,
) -> None:
    assert (
        _validate_hex_color(
            value,
            parameter_name="color",
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "#",
        "12345",
        "1234567",
        "GGGGGG",
        "#12FG45",
        "red",
        "0x17365D",
    ],
)
def test_validate_hex_color_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match=(
            "color must be a six-character "
            "hexadecimal color"
        ),
    ):
        _validate_hex_color(
            value,
            parameter_name="color",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        1.5,
        object(),
    ],
)
def test_validate_hex_color_rejects_non_string(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="color must be a string",
    ):
        _validate_hex_color(
            value,  # type: ignore[arg-type]
            parameter_name="color",
        )


def test_validate_hex_color_rejects_blank_parameter_name() -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match="parameter_name cannot be blank",
    ):
        _validate_hex_color(
            "17365D",
            parameter_name=" ",
        )


def test_validate_hex_color_rejects_non_string_parameter_name() -> None:
    with pytest.raises(
        TypeError,
        match="parameter_name must be a string",
    ):
        _validate_hex_color(
            "17365D",
            parameter_name=None,  # type: ignore[arg-type]
        )


# ============================================================
# as_hex_color
# ============================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("17365D", "17365D"),
        ("#17365D", "17365D"),
        ("abcdef", "ABCDEF"),
    ],
)
def test_as_hex_color_returns_normalized_value(
    value: str,
    expected: str,
) -> None:
    assert as_hex_color(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("17365D", "#17365D"),
        ("#17365D", "#17365D"),
        ("abcdef", "#ABCDEF"),
    ],
)
def test_as_hex_color_can_include_hash(
    value: str,
    expected: str,
) -> None:
    assert (
        as_hex_color(
            value,
            include_hash=True,
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        1,
        "yes",
        object(),
    ],
)
def test_as_hex_color_rejects_invalid_include_hash(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="include_hash must be a boolean",
    ):
        as_hex_color(
            "17365D",
            include_hash=value,  # type: ignore[arg-type]
        )


# ============================================================
# ReportColorPalette
# ============================================================


def test_report_color_palette_accepts_valid_colors() -> None:
    palette = ReportColorPalette(
        primary="17365D",
        secondary="4472C4",
        accent="5B9BD5",
        background="F7F9FC",
        label_background="EEF3F8",
        text="25313C",
        muted_text="5A6573",
        border="D9E1EA",
        success="2E7D32",
        warning="D97706",
        error="C62828",
    )

    assert palette.primary == "17365D"
    assert palette.warning == "D97706"


@pytest.mark.parametrize(
    "field_name",
    [
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
    ],
)
def test_report_color_palette_rejects_invalid_color(
    field_name: str,
) -> None:
    values = {
        "primary": "17365D",
        "secondary": "4472C4",
        "accent": "5B9BD5",
        "background": "F7F9FC",
        "label_background": "EEF3F8",
        "text": "25313C",
        "muted_text": "5A6573",
        "border": "D9E1EA",
        "success": "2E7D32",
        "warning": "D97706",
        "error": "C62828",
    }

    values[field_name] = "invalid"

    with pytest.raises(
        ReportAssetValidationError,
        match=(
            f"{field_name} must be a six-character "
            "hexadecimal color"
        ),
    ):
        ReportColorPalette(**values)


# ============================================================
# ReportTypography
# ============================================================


def test_report_typography_accepts_valid_configuration() -> None:
    typography = ReportTypography(
        primary_font="Helvetica",
        bold_font="Helvetica-Bold",
        excel_font="Calibri",
        title_size=21,
        section_size=13,
        body_size=9,
        small_size=8,
    )

    assert typography.primary_font == "Helvetica"
    assert typography.title_size == 21


@pytest.mark.parametrize(
    "field_name",
    [
        "primary_font",
        "bold_font",
        "excel_font",
    ],
)
def test_report_typography_rejects_blank_font_name(
    field_name: str,
) -> None:
    values = {
        "primary_font": "Helvetica",
        "bold_font": "Helvetica-Bold",
        "excel_font": "Calibri",
        "title_size": 21,
        "section_size": 13,
        "body_size": 9,
        "small_size": 8,
    }

    values[field_name] = " "

    with pytest.raises(
        ReportAssetValidationError,
        match=f"{field_name} cannot be blank",
    ):
        ReportTypography(**values)


@pytest.mark.parametrize(
    "field_name",
    [
        "title_size",
        "section_size",
        "body_size",
        "small_size",
    ],
)
def test_report_typography_rejects_non_positive_size(
    field_name: str,
) -> None:
    values = {
        "primary_font": "Helvetica",
        "bold_font": "Helvetica-Bold",
        "excel_font": "Calibri",
        "title_size": 21,
        "section_size": 13,
        "body_size": 9,
        "small_size": 8,
    }

    values[field_name] = 0

    with pytest.raises(
        ReportAssetValidationError,
        match=f"{field_name} must be greater than zero",
    ):
        ReportTypography(**values)


# ============================================================
# ReportLayout
# ============================================================


def test_report_layout_accepts_valid_configuration() -> None:
    layout = ReportLayout(
        page_margin_mm=18,
        header_height_mm=18,
        footer_height_mm=13,
        section_spacing_mm=4,
        content_spacing_mm=3,
        excel_minimum_column_width=12,
        excel_maximum_column_width=60,
        excel_column_padding=2,
    )

    assert layout.page_margin_mm == 18
    assert layout.excel_column_padding == 2


@pytest.mark.parametrize(
    "field_name",
    [
        "page_margin_mm",
        "header_height_mm",
        "footer_height_mm",
        "section_spacing_mm",
        "content_spacing_mm",
        "excel_minimum_column_width",
        "excel_maximum_column_width",
    ],
)
def test_report_layout_rejects_non_positive_value(
    field_name: str,
) -> None:
    values = {
        "page_margin_mm": 18,
        "header_height_mm": 18,
        "footer_height_mm": 13,
        "section_spacing_mm": 4,
        "content_spacing_mm": 3,
        "excel_minimum_column_width": 12,
        "excel_maximum_column_width": 60,
        "excel_column_padding": 2,
    }

    values[field_name] = 0

    with pytest.raises(
        ReportAssetValidationError,
        match=f"{field_name} must be greater than zero",
    ):
        ReportLayout(**values)


def test_report_layout_allows_zero_column_padding() -> None:
    layout = ReportLayout(
        page_margin_mm=18,
        header_height_mm=18,
        footer_height_mm=13,
        section_spacing_mm=4,
        content_spacing_mm=3,
        excel_minimum_column_width=12,
        excel_maximum_column_width=60,
        excel_column_padding=0,
    )

    assert layout.excel_column_padding == 0


def test_report_layout_rejects_negative_column_padding() -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match="excel_column_padding cannot be negative",
    ):
        ReportLayout(
            page_margin_mm=18,
            header_height_mm=18,
            footer_height_mm=13,
            section_spacing_mm=4,
            content_spacing_mm=3,
            excel_minimum_column_width=12,
            excel_maximum_column_width=60,
            excel_column_padding=-1,
        )


def test_report_layout_rejects_maximum_width_below_minimum() -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match=(
            "excel_maximum_column_width must be greater "
            "than or equal to excel_minimum_column_width"
        ),
    ):
        ReportLayout(
            page_margin_mm=18,
            header_height_mm=18,
            footer_height_mm=13,
            section_spacing_mm=4,
            content_spacing_mm=3,
            excel_minimum_column_width=60,
            excel_maximum_column_width=12,
            excel_column_padding=2,
        )


# ============================================================
# ReportBranding
# ============================================================


def test_report_branding_accepts_valid_configuration(
    tmp_path: Path,
) -> None:
    logo_path = tmp_path / "logo.png"

    branding = ReportBranding(
        application_name="AI Mutual Fund Assistant",
        module_name="Professional Reporting",
        default_title="Portfolio Analytics Report",
        footer_text="Generated for analytical purposes.",
        disclaimer="This is a disclaimer.",
        logo_path=logo_path,
    )

    assert branding.application_name == (
        "AI Mutual Fund Assistant"
    )
    assert branding.logo_path == logo_path


@pytest.mark.parametrize(
    "field_name",
    [
        "application_name",
        "module_name",
        "default_title",
        "footer_text",
        "disclaimer",
    ],
)
def test_report_branding_rejects_blank_text(
    field_name: str,
) -> None:
    values = {
        "application_name": "AI Mutual Fund Assistant",
        "module_name": "Professional Reporting",
        "default_title": "Portfolio Analytics Report",
        "footer_text": "Generated for analytical purposes.",
        "disclaimer": "This is a disclaimer.",
        "logo_path": None,
    }

    values[field_name] = " "

    with pytest.raises(
        ReportAssetValidationError,
        match=f"{field_name} cannot be blank",
    ):
        ReportBranding(**values)


@pytest.mark.parametrize(
    "logo_path",
    [
        "logo.png",
        123,
        object(),
    ],
)
def test_report_branding_rejects_invalid_logo_path_type(
    logo_path: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="logo_path must be a Path or None",
    ):
        ReportBranding(
            application_name="AI Mutual Fund Assistant",
            module_name="Professional Reporting",
            default_title="Portfolio Analytics Report",
            footer_text="Generated for analytical purposes.",
            disclaimer="This is a disclaimer.",
            logo_path=logo_path,  # type: ignore[arg-type]
        )
# ============================================================
# resolve_logo_path
# ============================================================


def test_resolve_logo_path_returns_none() -> None:
    assert resolve_logo_path(None) is None


def test_resolve_logo_path_resolves_string_path(
    tmp_path: Path,
) -> None:
    expected = (
        tmp_path
        / "logo.png"
    ).resolve()

    result = resolve_logo_path(
        str(
            tmp_path
            / "logo.png"
        )
    )

    assert result == expected
    assert result.is_absolute()


def test_resolve_logo_path_resolves_path_object(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "logo.png"
    )

    result = resolve_logo_path(
        source
    )

    assert result == source.resolve()


def test_resolve_logo_path_accepts_existing_file(
    tmp_path: Path,
) -> None:
    logo_path = (
        tmp_path
        / "logo.png"
    )

    logo_path.write_bytes(
        b"fake-image-content"
    )

    result = resolve_logo_path(
        logo_path,
        require_existing=True,
    )

    assert result == logo_path.resolve()
    assert result.is_file()


def test_resolve_logo_path_rejects_missing_file_when_required(
    tmp_path: Path,
) -> None:
    logo_path = (
        tmp_path
        / "missing-logo.png"
    )

    with pytest.raises(
        ReportAssetValidationError,
        match="logo_path does not exist",
    ):
        resolve_logo_path(
            logo_path,
            require_existing=True,
        )


def test_resolve_logo_path_rejects_directory_when_file_required(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match="logo_path must reference a file",
    ):
        resolve_logo_path(
            tmp_path,
            require_existing=True,
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
def test_resolve_logo_path_rejects_blank_string(
    value: str,
) -> None:
    with pytest.raises(
        ReportAssetValidationError,
        match="logo_path cannot be blank",
    ):
        resolve_logo_path(value)


@pytest.mark.parametrize(
    "value",
    [
        123,
        1.5,
        [],
        {},
        object(),
    ],
)
def test_resolve_logo_path_rejects_invalid_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "logo_path must be a string, "
            "Path, or None"
        ),
    ):
        resolve_logo_path(
            value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        1,
        "true",
        object(),
    ],
)
def test_resolve_logo_path_rejects_invalid_require_existing(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="require_existing must be a boolean",
    ):
        resolve_logo_path(
            None,
            require_existing=value,  # type: ignore[arg-type]
        )


# ============================================================
# Default Asset Instances
# ============================================================


def test_default_color_palette_matches_constants() -> None:
    assert (
        DEFAULT_COLOR_PALETTE.primary
        == assets.PRIMARY_NAVY
    )

    assert (
        DEFAULT_COLOR_PALETTE.secondary
        == assets.PRIMARY_BLUE
    )

    assert (
        DEFAULT_COLOR_PALETTE.accent
        == assets.SECONDARY_BLUE
    )

    assert (
        DEFAULT_COLOR_PALETTE.background
        == assets.NEUTRAL_BACKGROUND
    )

    assert (
        DEFAULT_COLOR_PALETTE.label_background
        == assets.LIGHTER_BLUE
    )

    assert (
        DEFAULT_COLOR_PALETTE.text
        == assets.TEXT_DARK
    )

    assert (
        DEFAULT_COLOR_PALETTE.muted_text
        == assets.TEXT_MUTED
    )

    assert (
        DEFAULT_COLOR_PALETTE.border
        == assets.BORDER_LIGHT
    )

    assert (
        DEFAULT_COLOR_PALETTE.success
        == assets.SUCCESS_GREEN
    )

    assert (
        DEFAULT_COLOR_PALETTE.warning
        == assets.WARNING_AMBER
    )

    assert (
        DEFAULT_COLOR_PALETTE.error
        == assets.ERROR_RED
    )


def test_default_typography_matches_constants() -> None:
    assert (
        DEFAULT_TYPOGRAPHY.primary_font
        == assets.PRIMARY_FONT_NAME
    )

    assert (
        DEFAULT_TYPOGRAPHY.bold_font
        == assets.PRIMARY_FONT_BOLD
    )

    assert (
        DEFAULT_TYPOGRAPHY.excel_font
        == assets.EXCEL_FONT_NAME
    )

    assert (
        DEFAULT_TYPOGRAPHY.title_size
        == assets.TITLE_FONT_SIZE
    )

    assert (
        DEFAULT_TYPOGRAPHY.section_size
        == assets.SECTION_FONT_SIZE
    )

    assert (
        DEFAULT_TYPOGRAPHY.body_size
        == assets.BODY_FONT_SIZE
    )

    assert (
        DEFAULT_TYPOGRAPHY.small_size
        == assets.SMALL_FONT_SIZE
    )


def test_default_layout_matches_constants() -> None:
    assert (
        DEFAULT_LAYOUT.page_margin_mm
        == assets.DEFAULT_PAGE_MARGIN_MM
    )

    assert (
        DEFAULT_LAYOUT.header_height_mm
        == assets.DEFAULT_HEADER_HEIGHT_MM
    )

    assert (
        DEFAULT_LAYOUT.footer_height_mm
        == assets.DEFAULT_FOOTER_HEIGHT_MM
    )

    assert (
        DEFAULT_LAYOUT.section_spacing_mm
        == assets.SECTION_SPACING_MM
    )

    assert (
        DEFAULT_LAYOUT.content_spacing_mm
        == assets.CONTENT_SPACING_MM
    )

    assert (
        DEFAULT_LAYOUT.excel_minimum_column_width
        == assets.EXCEL_MINIMUM_COLUMN_WIDTH
    )

    assert (
        DEFAULT_LAYOUT.excel_maximum_column_width
        == assets.EXCEL_MAXIMUM_COLUMN_WIDTH
    )

    assert (
        DEFAULT_LAYOUT.excel_column_padding
        == assets.EXCEL_COLUMN_PADDING
    )


def test_default_branding_matches_constants() -> None:
    assert (
        DEFAULT_BRANDING.application_name
        == APPLICATION_NAME
    )

    assert (
        DEFAULT_BRANDING.module_name
        == assets.REPORTING_MODULE_NAME
    )

    assert (
        DEFAULT_BRANDING.default_title
        == DEFAULT_REPORT_TITLE
    )

    assert (
        DEFAULT_BRANDING.footer_text
        == assets.REPORT_FOOTER_TEXT
    )

    assert (
        DEFAULT_BRANDING.disclaimer
        == assets.REPORT_DISCLAIMER
    )

    assert DEFAULT_BRANDING.logo_path is None


# ============================================================
# Dataclass Immutability
# ============================================================


def test_report_color_palette_is_immutable() -> None:
    with pytest.raises(
        AttributeError,
    ):
        DEFAULT_COLOR_PALETTE.primary = (  # type: ignore[misc]
            "FFFFFF"
        )


def test_report_typography_is_immutable() -> None:
    with pytest.raises(
        AttributeError,
    ):
        DEFAULT_TYPOGRAPHY.title_size = (  # type: ignore[misc]
            24
        )


def test_report_layout_is_immutable() -> None:
    with pytest.raises(
        AttributeError,
    ):
        DEFAULT_LAYOUT.page_margin_mm = (  # type: ignore[misc]
            20
        )


def test_report_branding_is_immutable() -> None:
    with pytest.raises(
        AttributeError,
    ):
        DEFAULT_BRANDING.application_name = (  # type: ignore[misc]
            "Changed"
        )


# ============================================================
# Constants
# ============================================================


def test_core_branding_constants() -> None:
    assert (
        APPLICATION_NAME
        == "AI Mutual Fund Assistant"
    )

    assert (
        DEFAULT_REPORT_TITLE
        == "Portfolio Analytics Report"
    )

    assert (
        assets.REPORTING_MODULE_NAME
        == "Professional Reporting"
    )


def test_report_filenames() -> None:
    assert (
        PDF_FILENAME
        == "portfolio_report.pdf"
    )

    assert (
        EXCEL_FILENAME
        == "portfolio_report.xlsx"
    )


def test_report_mime_types() -> None:
    assert (
        PDF_MIME_TYPE
        == "application/pdf"
    )

    assert EXCEL_MIME_TYPE == (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    )


def test_text_length_limits_are_positive() -> None:
    assert (
        assets.MAX_REPORT_TEXT_LENGTH
        > 0
    )

    assert (
        assets.MAX_EXCEL_CELL_TEXT_LENGTH
        > 0
    )

    assert (
        assets.MAX_EXCEL_CELL_TEXT_LENGTH
        > assets.MAX_REPORT_TEXT_LENGTH
    )


@pytest.mark.parametrize(
    "color_name",
    [
        "PRIMARY_NAVY",
        "PRIMARY_BLUE",
        "SECONDARY_BLUE",
        "LIGHT_BLUE",
        "LIGHTER_BLUE",
        "TEXT_DARK",
        "TEXT_MUTED",
        "WHITE",
        "BORDER_LIGHT",
        "SUCCESS_GREEN",
        "SUCCESS_BACKGROUND",
        "WARNING_AMBER",
        "WARNING_TEXT",
        "WARNING_BACKGROUND",
        "ERROR_RED",
        "ERROR_BACKGROUND",
        "NEUTRAL_BACKGROUND",
    ],
)
def test_color_constants_are_valid_hex_colors(
    color_name: str,
) -> None:
    value = getattr(
        assets,
        color_name,
    )

    assert (
        _validate_hex_color(
            value,
            parameter_name=color_name,
        )
        == value
    )


# ============================================================
# Public Exports
# ============================================================


@pytest.mark.parametrize(
    "export_name",
    [
        "APPLICATION_NAME",
        "DEFAULT_BRANDING",
        "DEFAULT_COLOR_PALETTE",
        "DEFAULT_LAYOUT",
        "DEFAULT_REPORT_TITLE",
        "DEFAULT_TYPOGRAPHY",
        "EXCEL_FILENAME",
        "EXCEL_MIME_TYPE",
        "PDF_FILENAME",
        "PDF_MIME_TYPE",
        "ReportAssetError",
        "ReportAssetValidationError",
        "ReportBranding",
        "ReportColorPalette",
        "ReportLayout",
        "ReportTypography",
        "as_hex_color",
        "resolve_logo_path",
    ],
)
def test_public_export_is_available(
    export_name: str,
) -> None:
    assert export_name in assets.__all__
    assert hasattr(
        assets,
        export_name,
    )


def test_all_exports_reference_existing_attributes() -> None:
    missing_exports = [
        name
        for name in assets.__all__
        if not hasattr(
            assets,
            name,
        )
    ]

    assert missing_exports == []


def test_all_exports_are_unique() -> None:
    assert len(
        assets.__all__
    ) == len(
        set(
            assets.__all__
        )
    )