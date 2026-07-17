"""
Centralized application settings.

This module provides immutable, validated configuration for the
AI Mutual Fund Assistant.

Configuration responsibilities
------------------------------
- Application metadata
- Runtime environment selection
- Project-root discovery
- Data and report directories
- Logging configuration
- Database connection settings
- Feature flags
- Environment-variable overrides
- Path creation and validation helpers

The module does not perform portfolio calculations, access portfolio data,
or depend on Streamlit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping


# ============================================================
# Environment-variable names
# ============================================================

ENV_PREFIX: Final[str] = "AIMF_"

ENV_APPLICATION_NAME: Final[str] = (
    f"{ENV_PREFIX}APPLICATION_NAME"
)
ENV_APPLICATION_VERSION: Final[str] = (
    f"{ENV_PREFIX}APPLICATION_VERSION"
)
ENV_ENVIRONMENT: Final[str] = (
    f"{ENV_PREFIX}ENVIRONMENT"
)
ENV_PROJECT_ROOT: Final[str] = (
    f"{ENV_PREFIX}PROJECT_ROOT"
)
ENV_DATA_DIRECTORY: Final[str] = (
    f"{ENV_PREFIX}DATA_DIRECTORY"
)
ENV_REPORT_DIRECTORY: Final[str] = (
    f"{ENV_PREFIX}REPORT_DIRECTORY"
)
ENV_LOG_DIRECTORY: Final[str] = (
    f"{ENV_PREFIX}LOG_DIRECTORY"
)
ENV_LOG_LEVEL: Final[str] = (
    f"{ENV_PREFIX}LOG_LEVEL"
)
ENV_DATABASE_URL: Final[str] = (
    f"{ENV_PREFIX}DATABASE_URL"
)
ENV_DEBUG: Final[str] = (
    f"{ENV_PREFIX}DEBUG"
)
ENV_ENABLE_PDF_REPORTS: Final[str] = (
    f"{ENV_PREFIX}ENABLE_PDF_REPORTS"
)
ENV_ENABLE_EXCEL_REPORTS: Final[str] = (
    f"{ENV_PREFIX}ENABLE_EXCEL_REPORTS"
)
ENV_ENABLE_AI_ADVISOR: Final[str] = (
    f"{ENV_PREFIX}ENABLE_AI_ADVISOR"
)
ENV_ENABLE_ADVANCED_ANALYTICS: Final[str] = (
    f"{ENV_PREFIX}ENABLE_ADVANCED_ANALYTICS"
)


# ============================================================
# Defaults
# ============================================================

DEFAULT_APPLICATION_NAME: Final[str] = (
    "AI Mutual Fund Assistant"
)
DEFAULT_APPLICATION_VERSION: Final[str] = "9.0.0"
DEFAULT_ENVIRONMENT: Final[str] = "development"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"

DEFAULT_DATA_DIRECTORY_NAME: Final[str] = "data"
DEFAULT_REPORT_DIRECTORY_NAME: Final[str] = "reports"
DEFAULT_LOG_DIRECTORY_NAME: Final[str] = "logs"
DEFAULT_DATABASE_DIRECTORY_NAME: Final[str] = "database"
DEFAULT_DATABASE_FILENAME: Final[str] = (
    "ai_mutual_fund_assistant.db"
)

SUPPORTED_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    }
)

TRUE_VALUES: Final[frozenset[str]] = frozenset(
    {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }
)

FALSE_VALUES: Final[frozenset[str]] = frozenset(
    {
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }
)


# ============================================================
# Exceptions
# ============================================================


class SettingsError(RuntimeError):
    """
    Base exception for application-settings failures.
    """


class SettingsValidationError(SettingsError):
    """
    Raised when a settings value is invalid.
    """


class SettingsDirectoryError(SettingsError):
    """
    Raised when a required application directory cannot be created.
    """


# ============================================================
# Runtime environment
# ============================================================


class ApplicationEnvironment(str, Enum):
    """
    Supported application runtime environments.
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def parse(
        cls,
        value: str | ApplicationEnvironment,
    ) -> ApplicationEnvironment:
        """
        Parse and validate an application environment.

        Args:
            value:
                Environment enum member or textual environment name.

        Returns:
            Validated ApplicationEnvironment member.

        Raises:
            TypeError:
                When value is not a string or ApplicationEnvironment.

            SettingsValidationError:
                When the environment name is unsupported.
        """

        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError(
                "environment must be a string or "
                "ApplicationEnvironment."
            )

        normalized_value = value.strip().lower()

        if not normalized_value:
            raise SettingsValidationError(
                "environment must not be empty."
            )

        aliases = {
            "dev": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "test": cls.TESTING,
            "testing": cls.TESTING,
            "stage": cls.STAGING,
            "staging": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }

        try:
            return aliases[normalized_value]
        except KeyError as exc:
            supported_values = ", ".join(
                environment.value
                for environment in cls
            )

            raise SettingsValidationError(
                "Unsupported application environment "
                f"{value!r}. Supported environments: "
                f"{supported_values}."
            ) from exc


# ============================================================
# Immutable feature flags
# ============================================================


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    """
    Immutable application feature flags.

    Attributes:
        enable_pdf_reports:
            Enable PDF report generation.

        enable_excel_reports:
            Enable Excel report generation.

        enable_ai_advisor:
            Enable AI Portfolio Advisor features.

        enable_advanced_analytics:
            Enable advanced portfolio analytics.
    """

    enable_pdf_reports: bool = True
    enable_excel_reports: bool = True
    enable_ai_advisor: bool = True
    enable_advanced_analytics: bool = True

    def as_mapping(self) -> Mapping[str, bool]:
        """
        Return feature flags as an immutable mapping.
        """

        return MappingProxyType(
            {
                "enable_pdf_reports": (
                    self.enable_pdf_reports
                ),
                "enable_excel_reports": (
                    self.enable_excel_reports
                ),
                "enable_ai_advisor": (
                    self.enable_ai_advisor
                ),
                "enable_advanced_analytics": (
                    self.enable_advanced_analytics
                ),
            }
        )


# ============================================================
# Immutable application settings
# ============================================================


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """
    Immutable validated application configuration.

    Attributes:
        application_name:
            Human-readable application name.

        application_version:
            Current application version.

        environment:
            Active runtime environment.

        project_root:
            Absolute project-root directory.

        data_directory:
            Directory containing application data.

        report_directory:
            Directory containing generated reports.

        log_directory:
            Directory containing application log files.

        log_level:
            Configured logging level.

        database_url:
            Database connection URL.

        debug:
            Whether debug mode is enabled.

        feature_flags:
            Immutable feature-toggle configuration.
    """

    application_name: str
    application_version: str
    environment: ApplicationEnvironment
    project_root: Path
    data_directory: Path
    report_directory: Path
    log_directory: Path
    log_level: str
    database_url: str
    debug: bool
    feature_flags: FeatureFlags = field(
        default_factory=FeatureFlags
    )

    def __post_init__(self) -> None:
        """
        Validate and normalize settings after construction.
        """

        application_name = _validate_required_text(
            self.application_name,
            field_name="application_name",
        )

        application_version = _validate_required_text(
            self.application_version,
            field_name="application_version",
        )

        environment = ApplicationEnvironment.parse(
            self.environment
        )

        project_root = _normalize_absolute_path(
            self.project_root,
            field_name="project_root",
        )

        data_directory = _normalize_absolute_path(
            self.data_directory,
            field_name="data_directory",
            base_directory=project_root,
        )

        report_directory = _normalize_absolute_path(
            self.report_directory,
            field_name="report_directory",
            base_directory=project_root,
        )

        log_directory = _normalize_absolute_path(
            self.log_directory,
            field_name="log_directory",
            base_directory=project_root,
        )

        log_level = _validate_log_level(
            self.log_level
        )

        database_url = _validate_required_text(
            self.database_url,
            field_name="database_url",
        )

        if not isinstance(self.debug, bool):
            raise TypeError(
                "debug must be a boolean."
            )

        if not isinstance(
            self.feature_flags,
            FeatureFlags,
        ):
            raise TypeError(
                "feature_flags must be a FeatureFlags instance."
            )

        object.__setattr__(
            self,
            "application_name",
            application_name,
        )
        object.__setattr__(
            self,
            "application_version",
            application_version,
        )
        object.__setattr__(
            self,
            "environment",
            environment,
        )
        object.__setattr__(
            self,
            "project_root",
            project_root,
        )
        object.__setattr__(
            self,
            "data_directory",
            data_directory,
        )
        object.__setattr__(
            self,
            "report_directory",
            report_directory,
        )
        object.__setattr__(
            self,
            "log_directory",
            log_directory,
        )
        object.__setattr__(
            self,
            "log_level",
            log_level,
        )
        object.__setattr__(
            self,
            "database_url",
            database_url,
        )

    @property
    def is_development(self) -> bool:
        """
        Return True when running in development.
        """

        return (
            self.environment
            is ApplicationEnvironment.DEVELOPMENT
        )

    @property
    def is_testing(self) -> bool:
        """
        Return True when running in testing.
        """

        return (
            self.environment
            is ApplicationEnvironment.TESTING
        )

    @property
    def is_staging(self) -> bool:
        """
        Return True when running in staging.
        """

        return (
            self.environment
            is ApplicationEnvironment.STAGING
        )

    @property
    def is_production(self) -> bool:
        """
        Return True when running in production.
        """

        return (
            self.environment
            is ApplicationEnvironment.PRODUCTION
        )

    @property
    def database_directory(self) -> Path:
        """
        Return the default local database directory.
        """

        return (
            self.project_root
            / DEFAULT_DATABASE_DIRECTORY_NAME
        )

    def ensure_directories(self) -> tuple[Path, ...]:
        """
        Create required writable application directories.

        Returns:
            Tuple of validated directories.

        Raises:
            SettingsDirectoryError:
                When a directory cannot be created or a path exists
                but is not a directory.
        """

        directories = (
            self.data_directory,
            self.report_directory,
            self.log_directory,
            self.database_directory,
        )

        for directory in directories:
            _ensure_directory(directory)

        return directories

    def as_mapping(self) -> Mapping[str, object]:
        """
        Return settings as an immutable mapping.

        Sensitive values such as database credentials are not separately
        parsed or exposed.
        """

        return MappingProxyType(
            {
                "application_name": (
                    self.application_name
                ),
                "application_version": (
                    self.application_version
                ),
                "environment": (
                    self.environment.value
                ),
                "project_root": (
                    self.project_root
                ),
                "data_directory": (
                    self.data_directory
                ),
                "report_directory": (
                    self.report_directory
                ),
                "log_directory": (
                    self.log_directory
                ),
                "log_level": (
                    self.log_level
                ),
                "database_url": (
                    self.database_url
                ),
                "debug": (
                    self.debug
                ),
                "feature_flags": (
                    self.feature_flags.as_mapping()
                ),
            }
        )


# ============================================================
# Validation helpers
# ============================================================


def _validate_required_text(
    value: object,
    *,
    field_name: str,
) -> str:
    """
    Validate a required textual value.
    """

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise SettingsValidationError(
            f"{field_name} must not be empty."
        )

    return normalized_value


def _validate_log_level(
    value: object,
) -> str:
    """
    Normalize and validate a logging level.
    """

    if not isinstance(value, str):
        raise TypeError(
            "log_level must be a string."
        )

    normalized_value = value.strip().upper()

    if not normalized_value:
        raise SettingsValidationError(
            "log_level must not be empty."
        )

    if normalized_value not in SUPPORTED_LOG_LEVELS:
        supported_levels = ", ".join(
            sorted(SUPPORTED_LOG_LEVELS)
        )

        raise SettingsValidationError(
            f"Unsupported log level {value!r}. "
            f"Supported levels: {supported_levels}."
        )

    return normalized_value


def _normalize_absolute_path(
    value: str | os.PathLike[str],
    *,
    field_name: str,
    base_directory: Path | None = None,
) -> Path:
    """
    Convert a path value into a normalized absolute path.
    """

    if not isinstance(
        value,
        (str, os.PathLike),
    ):
        raise TypeError(
            f"{field_name} must be a string or path-like value."
        )

    path = Path(value).expanduser()

    if not path.is_absolute():
        if base_directory is None:
            path = Path.cwd() / path
        else:
            path = base_directory / path

    try:
        return path.resolve(strict=False)
    except OSError as exc:
        raise SettingsValidationError(
            f"{field_name} could not be resolved: {path}."
        ) from exc


def _parse_boolean(
    value: object,
    *,
    field_name: str,
) -> bool:
    """
    Parse a boolean environment-variable value.
    """

    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a boolean or string."
        )

    normalized_value = value.strip().lower()

    if normalized_value in TRUE_VALUES:
        return True

    if normalized_value in FALSE_VALUES:
        return False

    raise SettingsValidationError(
        f"{field_name} must be one of "
        f"{sorted(TRUE_VALUES | FALSE_VALUES)}; "
        f"received {value!r}."
    )


def _ensure_directory(
    directory: Path,
) -> None:
    """
    Create and validate one application directory.
    """

    if directory.exists() and not directory.is_dir():
        raise SettingsDirectoryError(
            "Configured directory path is not a directory: "
            f"{directory}."
        )

    try:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise SettingsDirectoryError(
            f"Unable to create directory: {directory}."
        ) from exc

    if not directory.is_dir():
        raise SettingsDirectoryError(
            "Configured directory path is not a directory: "
            f"{directory}."
        )


# ============================================================
# Project-root discovery
# ============================================================


def discover_project_root(
    start_path: str | os.PathLike[str] | None = None,
) -> Path:
    """
    Discover the project root.

    Discovery order
    ---------------
    1. Explicit ``AIMF_PROJECT_ROOT`` environment override.
    2. Supplied ``start_path`` and its parents.
    3. This module's parent directories.

    A directory is treated as a project root when it contains one or more
    common project markers such as ``pyproject.toml``, ``requirements.txt``,
    ``.git``, or ``app.py``.

    Args:
        start_path:
            Optional file or directory from which discovery begins.

    Returns:
        Absolute project-root path.

    Raises:
        SettingsValidationError:
            When an explicit environment override does not point to an
            existing directory.
    """

    environment_override = os.getenv(
        ENV_PROJECT_ROOT
    )

    if environment_override is not None:
        project_root = _normalize_absolute_path(
            environment_override,
            field_name="project_root",
        )

        if not project_root.exists():
            raise SettingsValidationError(
                "AIMF_PROJECT_ROOT does not exist: "
                f"{project_root}."
            )

        if not project_root.is_dir():
            raise SettingsValidationError(
                "AIMF_PROJECT_ROOT must reference a directory: "
                f"{project_root}."
            )

        return project_root

    if start_path is None:
        starting_location = Path(__file__)
    else:
        starting_location = Path(
            start_path
        ).expanduser()

    starting_location = starting_location.resolve(
        strict=False
    )

    if starting_location.is_file():
        starting_location = (
            starting_location.parent
        )

    project_markers = (
        "pyproject.toml",
        "requirements.txt",
        ".git",
        "app.py",
    )

    candidates = (
        starting_location,
        *starting_location.parents,
    )

    for candidate in candidates:
        if any(
            (candidate / marker).exists()
            for marker in project_markers
        ):
            return candidate

    return Path(__file__).resolve().parent.parent


# ============================================================
# Settings factory
# ============================================================


def build_settings(
    *,
    environ: Mapping[str, str] | None = None,
    project_root: str | os.PathLike[str] | None = None,
) -> ApplicationSettings:
    """
    Build validated settings from defaults and environment overrides.

    Args:
        environ:
            Optional environment mapping. Supplying a mapping makes the
            factory deterministic and easy to test. When omitted,
            ``os.environ`` is used.

        project_root:
            Optional explicit project-root override. This argument takes
            precedence over automatic project-root discovery, but the
            ``AIMF_PROJECT_ROOT`` value in the supplied environment mapping
            takes precedence over this argument.

    Returns:
        Immutable ApplicationSettings instance.
    """

    source_environment: Mapping[str, str]

    if environ is None:
        source_environment = os.environ
    else:
        source_environment = environ

    configured_project_root = source_environment.get(
        ENV_PROJECT_ROOT
    )

    if configured_project_root is not None:
        resolved_project_root = (
            _normalize_absolute_path(
                configured_project_root,
                field_name="project_root",
            )
        )
    elif project_root is not None:
        resolved_project_root = (
            _normalize_absolute_path(
                project_root,
                field_name="project_root",
            )
        )
    else:
        resolved_project_root = (
            discover_project_root()
        )

    data_directory = _resolve_configured_directory(
        source_environment.get(
            ENV_DATA_DIRECTORY
        ),
        default_name=(
            DEFAULT_DATA_DIRECTORY_NAME
        ),
        project_root=resolved_project_root,
        field_name="data_directory",
    )

    report_directory = _resolve_configured_directory(
        source_environment.get(
            ENV_REPORT_DIRECTORY
        ),
        default_name=(
            DEFAULT_REPORT_DIRECTORY_NAME
        ),
        project_root=resolved_project_root,
        field_name="report_directory",
    )

    log_directory = _resolve_configured_directory(
        source_environment.get(
            ENV_LOG_DIRECTORY
        ),
        default_name=(
            DEFAULT_LOG_DIRECTORY_NAME
        ),
        project_root=resolved_project_root,
        field_name="log_directory",
    )

    default_database_path = (
        resolved_project_root
        / DEFAULT_DATABASE_DIRECTORY_NAME
        / DEFAULT_DATABASE_FILENAME
    )

    default_database_url = (
        f"sqlite:///{default_database_path.as_posix()}"
    )

    environment = ApplicationEnvironment.parse(
        source_environment.get(
            ENV_ENVIRONMENT,
            DEFAULT_ENVIRONMENT,
        )
    )

    default_debug = (
        environment
        is ApplicationEnvironment.DEVELOPMENT
    )

    debug = _read_boolean_setting(
        source_environment,
        ENV_DEBUG,
        default=default_debug,
    )

    feature_flags = FeatureFlags(
        enable_pdf_reports=(
            _read_boolean_setting(
                source_environment,
                ENV_ENABLE_PDF_REPORTS,
                default=True,
            )
        ),
        enable_excel_reports=(
            _read_boolean_setting(
                source_environment,
                ENV_ENABLE_EXCEL_REPORTS,
                default=True,
            )
        ),
        enable_ai_advisor=(
            _read_boolean_setting(
                source_environment,
                ENV_ENABLE_AI_ADVISOR,
                default=True,
            )
        ),
        enable_advanced_analytics=(
            _read_boolean_setting(
                source_environment,
                ENV_ENABLE_ADVANCED_ANALYTICS,
                default=True,
            )
        ),
    )

    return ApplicationSettings(
        application_name=source_environment.get(
            ENV_APPLICATION_NAME,
            DEFAULT_APPLICATION_NAME,
        ),
        application_version=source_environment.get(
            ENV_APPLICATION_VERSION,
            DEFAULT_APPLICATION_VERSION,
        ),
        environment=environment,
        project_root=resolved_project_root,
        data_directory=data_directory,
        report_directory=report_directory,
        log_directory=log_directory,
        log_level=source_environment.get(
            ENV_LOG_LEVEL,
            DEFAULT_LOG_LEVEL,
        ),
        database_url=source_environment.get(
            ENV_DATABASE_URL,
            default_database_url,
        ),
        debug=debug,
        feature_flags=feature_flags,
    )


def _resolve_configured_directory(
    configured_value: str | None,
    *,
    default_name: str,
    project_root: Path,
    field_name: str,
) -> Path:
    """
    Resolve an optional configured directory.
    """

    value: str | os.PathLike[str]

    if configured_value is None:
        value = default_name
    else:
        value = configured_value

    return _normalize_absolute_path(
        value,
        field_name=field_name,
        base_directory=project_root,
    )


def _read_boolean_setting(
    environment: Mapping[str, str],
    variable_name: str,
    *,
    default: bool,
) -> bool:
    """
    Read an optional boolean environment setting.
    """

    value = environment.get(
        variable_name
    )

    if value is None:
        return default

    return _parse_boolean(
        value,
        field_name=variable_name,
    )


# ============================================================
# Default settings accessor
# ============================================================

_settings_instance: ApplicationSettings | None = None


def get_settings(
    *,
    reload: bool = False,
) -> ApplicationSettings:
    """
    Return the process-wide immutable settings instance.

    Args:
        reload:
            Rebuild settings from the current environment when True.

    Returns:
        Cached ApplicationSettings instance.
    """

    global _settings_instance

    if reload or _settings_instance is None:
        _settings_instance = build_settings()

    return _settings_instance


def reset_settings_cache() -> None:
    """
    Clear the cached settings instance.

    This helper is primarily intended for isolated tests and controlled
    application reconfiguration.
    """

    global _settings_instance
    _settings_instance = None


__all__ = [
    "ApplicationEnvironment",
    "ApplicationSettings",
    "FeatureFlags",
    "SettingsDirectoryError",
    "SettingsError",
    "SettingsValidationError",
    "build_settings",
    "discover_project_root",
    "get_settings",
    "reset_settings_cache",
]