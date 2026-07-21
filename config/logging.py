"""
Centralized production logging configuration.

This module provides logging infrastructure for the AI Mutual Fund
Assistant application.

Responsibilities
----------------
- Console and rotating-file logging
- Application and error log separation
- Configurable log levels
- Sensitive-value redaction
- Thread-safe initialization
- Reusable named loggers
- Safe handler cleanup
- Integration with ApplicationSettings
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock
from typing import Final, Iterable

from config.settings import ApplicationSettings, get_settings


# ============================================================
# Constants
# ============================================================

DEFAULT_LOGGER_NAME: Final[str] = "ai_mutual_fund_assistant"
DEFAULT_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)
DEFAULT_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

DEFAULT_APPLICATION_LOG_FILENAME: Final[str] = "application.log"
DEFAULT_ERROR_LOG_FILENAME: Final[str] = "error.log"

DEFAULT_MAX_BYTES: Final[int] = 10 * 1024 * 1024
DEFAULT_BACKUP_COUNT: Final[int] = 5

VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    }
)

SENSITIVE_FIELD_NAMES: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "authorization",
    "database_url",
)

_REDACTED_VALUE: Final[str] = "***REDACTED***"


# ============================================================
# Exceptions
# ============================================================


class LoggingConfigurationError(RuntimeError):
    """
    Raised when logging configuration is invalid.
    """


class LoggingInitializationError(RuntimeError):
    """
    Raised when logging infrastructure cannot be initialized.
    """


# ============================================================
# Configuration
# ============================================================


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """
    Immutable logging configuration.

    Attributes:
        logger_name:
            Root application logger name.

        log_level:
            Minimum application log level.

        log_directory:
            Directory containing generated log files.

        console_enabled:
            Whether console output is enabled.

        file_enabled:
            Whether rotating file output is enabled.

        application_log_filename:
            Filename for general application logs.

        error_log_filename:
            Filename for ERROR and CRITICAL logs.

        max_bytes:
            Maximum size of each rotating log file.

        backup_count:
            Number of rotated files retained.

        log_format:
            Python logging format string.

        date_format:
            Timestamp format string.

        propagate:
            Whether records propagate to ancestor loggers.
    """

    logger_name: str = DEFAULT_LOGGER_NAME
    log_level: str = "INFO"
    log_directory: Path = Path("logs")
    console_enabled: bool = True
    file_enabled: bool = True
    application_log_filename: str = (
        DEFAULT_APPLICATION_LOG_FILENAME
    )
    error_log_filename: str = DEFAULT_ERROR_LOG_FILENAME
    max_bytes: int = DEFAULT_MAX_BYTES
    backup_count: int = DEFAULT_BACKUP_COUNT
    log_format: str = DEFAULT_LOG_FORMAT
    date_format: str = DEFAULT_DATE_FORMAT
    propagate: bool = False

    def __post_init__(self) -> None:
        """
        Validate and normalize logging configuration.
        """

        normalized_name = _validate_non_empty_string(
            self.logger_name,
            field_name="logger_name",
        )

        normalized_level = _normalize_log_level(
            self.log_level
        )

        normalized_directory = _normalize_path(
            self.log_directory,
            field_name="log_directory",
        )

        application_filename = _validate_log_filename(
            self.application_log_filename,
            field_name="application_log_filename",
        )

        error_filename = _validate_log_filename(
            self.error_log_filename,
            field_name="error_log_filename",
        )

        if application_filename == error_filename:
            raise LoggingConfigurationError(
                "application_log_filename and "
                "error_log_filename must be different."
            )

        for field_name in (
            "console_enabled",
            "file_enabled",
            "propagate",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, bool):
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        if not isinstance(self.max_bytes, int):
            raise TypeError(
                "max_bytes must be an integer."
            )

        if self.max_bytes <= 0:
            raise LoggingConfigurationError(
                "max_bytes must be greater than zero."
            )

        if not isinstance(self.backup_count, int):
            raise TypeError(
                "backup_count must be an integer."
            )

        if self.backup_count < 0:
            raise LoggingConfigurationError(
                "backup_count must be zero or greater."
            )

        normalized_format = _validate_non_empty_string(
            self.log_format,
            field_name="log_format",
        )

        normalized_date_format = _validate_non_empty_string(
            self.date_format,
            field_name="date_format",
        )

        object.__setattr__(
            self,
            "logger_name",
            normalized_name,
        )
        object.__setattr__(
            self,
            "log_level",
            normalized_level,
        )
        object.__setattr__(
            self,
            "log_directory",
            normalized_directory,
        )
        object.__setattr__(
            self,
            "application_log_filename",
            application_filename,
        )
        object.__setattr__(
            self,
            "error_log_filename",
            error_filename,
        )
        object.__setattr__(
            self,
            "log_format",
            normalized_format,
        )
        object.__setattr__(
            self,
            "date_format",
            normalized_date_format,
        )

    @property
    def numeric_log_level(self) -> int:
        """
        Return the numeric Python logging level.
        """

        return logging._nameToLevel[self.log_level]

    @property
    def application_log_path(self) -> Path:
        """
        Return the full application log path.
        """

        return (
            self.log_directory
            / self.application_log_filename
        )

    @property
    def error_log_path(self) -> Path:
        """
        Return the full error log path.
        """

        return (
            self.log_directory
            / self.error_log_filename
        )

    @classmethod
    def from_application_settings(
        cls,
        settings: ApplicationSettings,
        *,
        logger_name: str = DEFAULT_LOGGER_NAME,
        console_enabled: bool = True,
        file_enabled: bool = True,
    ) -> LoggingConfig:
        """
        Create logging configuration from application settings.
        """

        if not isinstance(
            settings,
            ApplicationSettings,
        ):
            raise TypeError(
                "settings must be an ApplicationSettings instance."
            )

        return cls(
            logger_name=logger_name,
            log_level=settings.log_level,
            log_directory=settings.log_directory,
            console_enabled=console_enabled,
            file_enabled=file_enabled,
        )


# ============================================================
# Filters
# ============================================================


class SensitiveDataFilter(logging.Filter):
    """
    Redact sensitive values from log messages.

    The filter modifies the formatted message arguments before handlers
    emit the record. Common password, token, API-key, authorization and
    database credential patterns are protected.
    """

    _assignment_pattern: Final[re.Pattern[str]] = re.compile(
        rf"""
        (?P<key_quote>["']?)
        (?P<key>
            {"|".join(re.escape(name) for name in SENSITIVE_FIELD_NAMES)}
        )
        (?P=key_quote)
        (?P<separator>\s*[:=]\s*)
        (?P<quote>["']?)
        (?P<value>
            (?!Bearer\b)
            [^\s,;)"']+
        )
        (?P=quote)
        """,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    _bearer_pattern: Final[re.Pattern[str]] = re.compile(
        r"\bBearer\s+[A-Za-z0-9._~+/=-]+",
        flags=re.IGNORECASE,
    )

    _url_password_pattern: Final[re.Pattern[str]] = re.compile(
        r"(?P<prefix>://[^:/@\s]+:)"
        r"(?P<password>[^@\s]+)"
        r"(?P<suffix>@)",
    )

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        """
        Redact sensitive content and allow the record.
        """

        try:
            message = record.getMessage()
            record.msg = redact_sensitive_data(message)
            record.args = ()
        except Exception:
            record.msg = (
                "Unable to safely format original log message."
            )
            record.args = ()

        return True


class MaximumLevelFilter(logging.Filter):
    """
    Allow records only up to a configured maximum level.
    """

    def __init__(
        self,
        maximum_level: int,
    ) -> None:
        super().__init__()

        if not isinstance(maximum_level, int):
            raise TypeError(
                "maximum_level must be an integer."
            )

        self._maximum_level = maximum_level

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        """
        Return True when the record is below or equal to the maximum.
        """

        return record.levelno <= self._maximum_level


# ============================================================
# Logging manager
# ============================================================


class LoggingManager:
    """
    Manage application logging lifecycle.

    A LoggingManager configures one parent application logger and
    creates child loggers through ``get_logger``.
    """

    def __init__(
        self,
        config: LoggingConfig,
    ) -> None:
        if not isinstance(config, LoggingConfig):
            raise TypeError(
                "config must be a LoggingConfig instance."
            )

        self._config = config
        self._logger: logging.Logger | None = None
        self._initialized = False
        self._lock = RLock()

    @property
    def config(self) -> LoggingConfig:
        """
        Return immutable logging configuration.
        """

        return self._config

    @property
    def is_initialized(self) -> bool:
        """
        Return whether logging has been initialized.
        """

        return self._initialized

    @property
    def logger(self) -> logging.Logger:
        """
        Return the configured application logger.
        """

        if not self._initialized or self._logger is None:
            raise LoggingInitializationError(
                "Logging manager has not been initialized."
            )

        return self._logger

    def initialize(
        self,
        *,
        force: bool = False,
    ) -> logging.Logger:
        """
        Initialize application logging.

        Args:
            force:
                Remove existing handlers and rebuild the logger.

        Returns:
            Configured application logger.
        """

        with self._lock:
            if self._initialized and not force:
                return self.logger

            logger = logging.getLogger(
                self._config.logger_name
            )

            try:
                if force or logger.handlers:
                    _close_and_remove_handlers(logger)

                logger.setLevel(
                    self._config.numeric_log_level
                )
                logger.propagate = self._config.propagate

                formatter = logging.Formatter(
                    fmt=self._config.log_format,
                    datefmt=self._config.date_format,
                )

                sensitive_filter = SensitiveDataFilter()

                if self._config.console_enabled:
                    console_handler = (
                        self._create_console_handler(
                            formatter=formatter,
                            sensitive_filter=sensitive_filter,
                        )
                    )
                    logger.addHandler(console_handler)

                if self._config.file_enabled:
                    self._ensure_log_directory()

                    application_handler = (
                        self._create_application_file_handler(
                            formatter=formatter,
                            sensitive_filter=sensitive_filter,
                        )
                    )
                    error_handler = (
                        self._create_error_file_handler(
                            formatter=formatter,
                            sensitive_filter=sensitive_filter,
                        )
                    )

                    logger.addHandler(application_handler)
                    logger.addHandler(error_handler)

                if not logger.handlers:
                    logger.addHandler(logging.NullHandler())

                self._logger = logger
                self._initialized = True

                logger.debug(
                    "Logging initialized for %s.",
                    self._config.logger_name,
                )

                return logger
            except (
                OSError,
                ValueError,
                TypeError,
            ) as exc:
                _close_and_remove_handlers(logger)

                raise LoggingInitializationError(
                    "Unable to initialize logging."
                ) from exc
            except Exception as exc:
                _close_and_remove_handlers(logger)

                raise LoggingInitializationError(
                    "Unable to initialize logging."
                ) from exc

    def get_logger(
        self,
        name: str | None = None,
    ) -> logging.Logger:
        """
        Return the application logger or one of its child loggers.
        """

        parent = (
            self.initialize()
            if not self._initialized
            else self.logger
        )

        if name is None:
            return parent

        normalized_name = _validate_non_empty_string(
            name,
            field_name="name",
        )

        if normalized_name == self._config.logger_name:
            return parent

        if normalized_name.startswith(
            f"{self._config.logger_name}."
        ):
            return logging.getLogger(normalized_name)

        return parent.getChild(normalized_name)

    def shutdown(self) -> None:
        """
        Flush, close and remove all managed handlers.

        This operation is idempotent.
        """

        with self._lock:
            if self._logger is not None:
                _close_and_remove_handlers(
                    self._logger
                )

            self._logger = None
            self._initialized = False

    def _ensure_log_directory(self) -> None:
        """
        Create and validate the configured log directory.
        """

        directory = self._config.log_directory

        if directory.exists() and not directory.is_dir():
            raise LoggingInitializationError(
                "Configured log path is not a directory: "
                f"{directory}"
            )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _create_console_handler(
        self,
        *,
        formatter: logging.Formatter,
        sensitive_filter: logging.Filter,
    ) -> logging.Handler:
        """
        Create the console handler.
        """

        handler = logging.StreamHandler()
        handler.setLevel(
            self._config.numeric_log_level
        )
        handler.setFormatter(formatter)
        handler.addFilter(sensitive_filter)

        return handler

    def _create_application_file_handler(
        self,
        *,
        formatter: logging.Formatter,
        sensitive_filter: logging.Filter,
    ) -> RotatingFileHandler:
        """
        Create the rotating general application handler.
        """

        handler = RotatingFileHandler(
            filename=self._config.application_log_path,
            maxBytes=self._config.max_bytes,
            backupCount=self._config.backup_count,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(
            self._config.numeric_log_level
        )
        handler.setFormatter(formatter)
        handler.addFilter(
            MaximumLevelFilter(logging.WARNING)
        )
        handler.addFilter(sensitive_filter)

        return handler

    def _create_error_file_handler(
        self,
        *,
        formatter: logging.Formatter,
        sensitive_filter: logging.Filter,
    ) -> RotatingFileHandler:
        """
        Create the rotating error handler.
        """

        handler = RotatingFileHandler(
            filename=self._config.error_log_path,
            maxBytes=self._config.max_bytes,
            backupCount=self._config.backup_count,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(logging.ERROR)
        handler.setFormatter(formatter)
        handler.addFilter(sensitive_filter)

        return handler


# ============================================================
# Global logging lifecycle
# ============================================================

_logging_manager: LoggingManager | None = None
_logging_manager_lock = RLock()


def build_logging_manager(
    *,
    settings: ApplicationSettings | None = None,
    config: LoggingConfig | None = None,
) -> LoggingManager:
    """
    Build a new logging manager.
    """

    if settings is not None and config is not None:
        raise LoggingConfigurationError(
            "Provide either settings or config, not both."
        )

    if config is not None:
        resolved_config = config
    else:
        resolved_settings = (
            get_settings()
            if settings is None
            else settings
        )
        resolved_config = (
            LoggingConfig.from_application_settings(
                resolved_settings
            )
        )

    return LoggingManager(resolved_config)


def get_logging_manager(
    *,
    reload: bool = False,
    settings: ApplicationSettings | None = None,
    config: LoggingConfig | None = None,
) -> LoggingManager:
    """
    Return the process-wide logging manager.
    """

    global _logging_manager

    if settings is not None and config is not None:
        raise LoggingConfigurationError(
            "Provide either settings or config, not both."
        )

    with _logging_manager_lock:
        if reload and _logging_manager is not None:
            _logging_manager.shutdown()
            _logging_manager = None

        if _logging_manager is None:
            _logging_manager = build_logging_manager(
                settings=settings,
                config=config,
            )
            _logging_manager.initialize()

        return _logging_manager


def configure_logging(
    *,
    settings: ApplicationSettings | None = None,
    config: LoggingConfig | None = None,
    force: bool = False,
) -> logging.Logger:
    """
    Configure and return the global application logger.
    """

    manager = get_logging_manager(
        reload=force,
        settings=settings,
        config=config,
    )

    return manager.logger


def get_logger(
    name: str | None = None,
) -> logging.Logger:
    """
    Return the global application logger or a child logger.
    """

    return get_logging_manager().get_logger(name)


def reset_logging_manager() -> None:
    """
    Shut down and clear the global logging manager.
    """

    global _logging_manager

    with _logging_manager_lock:
        if _logging_manager is not None:
            _logging_manager.shutdown()

        _logging_manager = None


# ============================================================
# Redaction helpers
# ============================================================


def redact_sensitive_data(
    value: object,
) -> str:
    """
    Return a string with common sensitive values redacted.
    """

    text = str(value)

    text = SensitiveDataFilter._bearer_pattern.sub(
        f"Bearer {_REDACTED_VALUE}",
        text,
    )

    text = SensitiveDataFilter._url_password_pattern.sub(
        rf"\g<prefix>{_REDACTED_VALUE}\g<suffix>",
        text,
    )

    def replace_assignment(
        match: re.Match[str],
    ) -> str:
        key = match.group("key")
        separator = match.group("separator")
        quote = match.group("quote")

        return (
            f"{key}{separator}"
            f"{quote}{_REDACTED_VALUE}{quote}"
        )

    return SensitiveDataFilter._assignment_pattern.sub(
        replace_assignment,
        text,
    )


# ============================================================
# Helpers
# ============================================================


def _normalize_log_level(
    value: object,
) -> str:
    """
    Validate and normalize a logging level.
    """

    if not isinstance(value, str):
        raise TypeError(
            "log_level must be a string."
        )

    normalized_value = value.strip().upper()

    if normalized_value not in VALID_LOG_LEVELS:
        allowed = ", ".join(
            sorted(VALID_LOG_LEVELS)
        )

        raise LoggingConfigurationError(
            f"Unsupported log level {value!r}. "
            f"Allowed values: {allowed}."
        )

    return normalized_value


def _validate_non_empty_string(
    value: object,
    *,
    field_name: str,
) -> str:
    """
    Validate and normalize a required string.
    """

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise LoggingConfigurationError(
            f"{field_name} must not be empty."
        )

    return normalized_value


def _normalize_path(
    value: object,
    *,
    field_name: str,
) -> Path:
    """
    Validate and normalize a filesystem path.
    """

    if not isinstance(value, (str, Path)):
        raise TypeError(
            f"{field_name} must be a string or Path."
        )

    normalized_path = Path(value).expanduser()

    if not str(normalized_path).strip():
        raise LoggingConfigurationError(
            f"{field_name} must not be empty."
        )

    return normalized_path.resolve()


def _validate_log_filename(
    value: object,
    *,
    field_name: str,
) -> str:
    """
    Validate a log filename without directory components.
    """

    normalized_value = _validate_non_empty_string(
        value,
        field_name=field_name,
    )

    path = Path(normalized_value)

    if path.name != normalized_value:
        raise LoggingConfigurationError(
            f"{field_name} must contain only a filename."
        )

    if path.suffix.lower() != ".log":
        raise LoggingConfigurationError(
            f"{field_name} must use the .log extension."
        )

    return normalized_value


def _close_and_remove_handlers(
    logger: logging.Logger,
) -> None:
    """
    Flush, close and remove all handlers from a logger.
    """

    handlers: Iterable[logging.Handler] = tuple(
        logger.handlers
    )

    for handler in handlers:
        logger.removeHandler(handler)

        try:
            handler.flush()
        finally:
            handler.close()


__all__ = [
    "LoggingConfig",
    "LoggingConfigurationError",
    "LoggingInitializationError",
    "LoggingManager",
    "MaximumLevelFilter",
    "SensitiveDataFilter",
    "build_logging_manager",
    "configure_logging",
    "get_logger",
    "get_logging_manager",
    "redact_sensitive_data",
    "reset_logging_manager",
]