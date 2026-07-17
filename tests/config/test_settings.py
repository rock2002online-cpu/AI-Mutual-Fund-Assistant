"""
Unit tests for centralized application settings.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from config.settings import (
    ApplicationEnvironment,
    ApplicationSettings,
    FeatureFlags,
    SettingsDirectoryError,
    SettingsValidationError,
    build_settings,
    discover_project_root,
    get_settings,
    reset_settings_cache,
)


def test_application_environment_parse_supports_enum_member() -> None:
    result = ApplicationEnvironment.parse(
        ApplicationEnvironment.TESTING
    )

    assert result is ApplicationEnvironment.TESTING


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("dev", ApplicationEnvironment.DEVELOPMENT),
        ("development", ApplicationEnvironment.DEVELOPMENT),
        ("test", ApplicationEnvironment.TESTING),
        ("testing", ApplicationEnvironment.TESTING),
        ("stage", ApplicationEnvironment.STAGING),
        ("staging", ApplicationEnvironment.STAGING),
        ("prod", ApplicationEnvironment.PRODUCTION),
        ("production", ApplicationEnvironment.PRODUCTION),
        ("  PRODUCTION  ", ApplicationEnvironment.PRODUCTION),
    ],
)
def test_application_environment_parse_supports_aliases(
    value: str,
    expected: ApplicationEnvironment,
) -> None:
    assert ApplicationEnvironment.parse(value) is expected


def test_application_environment_parse_rejects_empty_value() -> None:
    with pytest.raises(
        SettingsValidationError,
        match="environment must not be empty",
    ):
        ApplicationEnvironment.parse("   ")


def test_application_environment_parse_rejects_unknown_value() -> None:
    with pytest.raises(
        SettingsValidationError,
        match="Unsupported application environment",
    ):
        ApplicationEnvironment.parse("local")


def test_application_environment_parse_rejects_invalid_type() -> None:
    with pytest.raises(
        TypeError,
        match="environment must be a string",
    ):
        ApplicationEnvironment.parse(123)  # type: ignore[arg-type]


def test_feature_flags_defaults_are_enabled() -> None:
    flags = FeatureFlags()

    assert flags.enable_pdf_reports is True
    assert flags.enable_excel_reports is True
    assert flags.enable_ai_advisor is True
    assert flags.enable_advanced_analytics is True


def test_feature_flags_are_immutable() -> None:
    flags = FeatureFlags()

    with pytest.raises(FrozenInstanceError):
        flags.enable_pdf_reports = False  # type: ignore[misc]


def test_feature_flags_as_mapping_returns_immutable_mapping() -> None:
    flags = FeatureFlags()

    result = flags.as_mapping()

    assert isinstance(result, MappingProxyType)
    assert result["enable_pdf_reports"] is True

    with pytest.raises(TypeError):
        result["enable_pdf_reports"] = False  # type: ignore[index]


def test_build_settings_uses_defaults(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    assert settings.application_name == "AI Mutual Fund Assistant"
    assert settings.application_version == "9.0.0"
    assert (
        settings.environment
        is ApplicationEnvironment.DEVELOPMENT
    )
    assert settings.project_root == tmp_path.resolve()
    assert settings.data_directory == (
        tmp_path / "data"
    ).resolve()
    assert settings.report_directory == (
        tmp_path / "reports"
    ).resolve()
    assert settings.log_directory == (
        tmp_path / "logs"
    ).resolve()
    assert settings.log_level == "INFO"
    assert settings.debug is True
    assert settings.database_url == (
        "sqlite:///"
        f"{(tmp_path / 'database' / 'ai_mutual_fund_assistant.db').resolve().as_posix()}"
    )


def test_build_settings_applies_environment_overrides(
    tmp_path: Path,
) -> None:
    custom_root = tmp_path / "custom-root"

    environment = {
        "AIMF_APPLICATION_NAME": "Portfolio Platform",
        "AIMF_APPLICATION_VERSION": "9.1.0",
        "AIMF_ENVIRONMENT": "production",
        "AIMF_PROJECT_ROOT": str(custom_root),
        "AIMF_DATA_DIRECTORY": "storage/data",
        "AIMF_REPORT_DIRECTORY": "storage/reports",
        "AIMF_LOG_DIRECTORY": "storage/logs",
        "AIMF_LOG_LEVEL": "debug",
        "AIMF_DATABASE_URL": "postgresql://user:pass@host/db",
        "AIMF_DEBUG": "false",
        "AIMF_ENABLE_PDF_REPORTS": "false",
        "AIMF_ENABLE_EXCEL_REPORTS": "true",
        "AIMF_ENABLE_AI_ADVISOR": "0",
        "AIMF_ENABLE_ADVANCED_ANALYTICS": "1",
    }

    settings = build_settings(
        environ=environment,
        project_root=tmp_path,
    )

    assert settings.application_name == "Portfolio Platform"
    assert settings.application_version == "9.1.0"
    assert (
        settings.environment
        is ApplicationEnvironment.PRODUCTION
    )
    assert settings.project_root == custom_root.resolve()
    assert settings.data_directory == (
        custom_root / "storage" / "data"
    ).resolve()
    assert settings.report_directory == (
        custom_root / "storage" / "reports"
    ).resolve()
    assert settings.log_directory == (
        custom_root / "storage" / "logs"
    ).resolve()
    assert settings.log_level == "DEBUG"
    assert (
        settings.database_url
        == "postgresql://user:pass@host/db"
    )
    assert settings.debug is False
    assert settings.feature_flags.enable_pdf_reports is False
    assert settings.feature_flags.enable_excel_reports is True
    assert settings.feature_flags.enable_ai_advisor is False
    assert (
        settings.feature_flags.enable_advanced_analytics
        is True
    )


def test_build_settings_environment_project_root_takes_precedence(
    tmp_path: Path,
) -> None:
    argument_root = tmp_path / "argument-root"
    environment_root = tmp_path / "environment-root"

    settings = build_settings(
        environ={
            "AIMF_PROJECT_ROOT": str(environment_root),
        },
        project_root=argument_root,
    )

    assert settings.project_root == environment_root.resolve()


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "TRUE",
        "1",
        "yes",
        "on",
        "enabled",
    ],
)
def test_build_settings_parses_true_boolean_values(
    tmp_path: Path,
    value: str,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DEBUG": value,
        },
        project_root=tmp_path,
    )

    assert settings.debug is True


@pytest.mark.parametrize(
    "value",
    [
        "false",
        "FALSE",
        "0",
        "no",
        "off",
        "disabled",
    ],
)
def test_build_settings_parses_false_boolean_values(
    tmp_path: Path,
    value: str,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DEBUG": value,
        },
        project_root=tmp_path,
    )

    assert settings.debug is False


def test_build_settings_rejects_invalid_boolean_value(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SettingsValidationError,
        match="AIMF_DEBUG must be one of",
    ):
        build_settings(
            environ={
                "AIMF_DEBUG": "sometimes",
            },
            project_root=tmp_path,
        )


def test_application_settings_are_immutable(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    with pytest.raises(FrozenInstanceError):
        settings.log_level = "DEBUG"  # type: ignore[misc]


def test_application_settings_normalizes_log_level(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_LOG_LEVEL": " warning ",
        },
        project_root=tmp_path,
    )

    assert settings.log_level == "WARNING"


def test_application_settings_rejects_invalid_log_level(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SettingsValidationError,
        match="Unsupported log level",
    ):
        build_settings(
            environ={
                "AIMF_LOG_LEVEL": "TRACE",
            },
            project_root=tmp_path,
        )


def test_application_settings_rejects_empty_application_name(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SettingsValidationError,
        match="application_name must not be empty",
    ):
        build_settings(
            environ={
                "AIMF_APPLICATION_NAME": "   ",
            },
            project_root=tmp_path,
        )


def test_application_settings_rejects_empty_database_url(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SettingsValidationError,
        match="database_url must not be empty",
    ):
        build_settings(
            environ={
                "AIMF_DATABASE_URL": "   ",
            },
            project_root=tmp_path,
        )


def test_environment_convenience_properties(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_ENVIRONMENT": "staging",
        },
        project_root=tmp_path,
    )

    assert settings.is_development is False
    assert settings.is_testing is False
    assert settings.is_staging is True
    assert settings.is_production is False


def test_database_directory_is_relative_to_project_root(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    assert settings.database_directory == (
        tmp_path / "database"
    ).resolve()


def test_ensure_directories_creates_required_directories(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    result = settings.ensure_directories()

    assert result == (
        settings.data_directory,
        settings.report_directory,
        settings.log_directory,
        settings.database_directory,
    )

    for directory in result:
        assert directory.exists()
        assert directory.is_dir()


def test_ensure_directories_rejects_existing_file(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "data"
    data_path.write_text(
        "not a directory",
        encoding="utf-8",
    )

    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    with pytest.raises(
        SettingsDirectoryError,
        match="not a directory",
    ):
        settings.ensure_directories()


def test_application_settings_as_mapping_is_immutable(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    result = settings.as_mapping()

    assert isinstance(result, MappingProxyType)
    assert result["application_version"] == "9.0.0"
    assert result["environment"] == "development"

    with pytest.raises(TypeError):
        result["debug"] = False  # type: ignore[index]


def test_discover_project_root_finds_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "AIMF_PROJECT_ROOT",
        raising=False,
    )

    project_root = tmp_path / "project"
    nested_directory = (
        project_root / "src" / "package"
    )
    nested_directory.mkdir(parents=True)

    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'test-project'\n",
        encoding="utf-8",
    )

    result = discover_project_root(
        nested_directory
    )

    assert result == project_root.resolve()


def test_discover_project_root_uses_environment_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "configured"
    project_root.mkdir()

    monkeypatch.setenv(
        "AIMF_PROJECT_ROOT",
        str(project_root),
    )

    result = discover_project_root()

    assert result == project_root.resolve()


def test_discover_project_root_rejects_missing_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_path = tmp_path / "missing"

    monkeypatch.setenv(
        "AIMF_PROJECT_ROOT",
        str(missing_path),
    )

    with pytest.raises(
        SettingsValidationError,
        match="does not exist",
    ):
        discover_project_root()


def test_discover_project_root_rejects_file_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "project.txt"
    file_path.write_text(
        "invalid root",
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "AIMF_PROJECT_ROOT",
        str(file_path),
    )

    with pytest.raises(
        SettingsValidationError,
        match="must reference a directory",
    ):
        discover_project_root()


def test_get_settings_returns_cached_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AIMF_PROJECT_ROOT",
        str(tmp_path),
    )

    reset_settings_cache()

    first = get_settings()
    second = get_settings()

    assert first is second

    reset_settings_cache()


def test_get_settings_reload_rebuilds_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AIMF_PROJECT_ROOT",
        str(tmp_path),
    )
    monkeypatch.setenv(
        "AIMF_APPLICATION_NAME",
        "Initial Name",
    )

    reset_settings_cache()
    first = get_settings()

    monkeypatch.setenv(
        "AIMF_APPLICATION_NAME",
        "Updated Name",
    )

    second = get_settings(reload=True)

    assert first is not second
    assert first.application_name == "Initial Name"
    assert second.application_name == "Updated Name"

    reset_settings_cache()


def test_application_settings_rejects_invalid_feature_flags(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="feature_flags must be a FeatureFlags instance",
    ):
        ApplicationSettings(
            application_name="Application",
            application_version="9.0.0",
            environment=ApplicationEnvironment.TESTING,
            project_root=tmp_path,
            data_directory=tmp_path / "data",
            report_directory=tmp_path / "reports",
            log_directory=tmp_path / "logs",
            log_level="INFO",
            database_url="sqlite:///test.db",
            debug=False,
            feature_flags={},  # type: ignore[arg-type]
        )