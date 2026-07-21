"""
Unit tests for centralized application logging configuration.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.logging import (
    LoggingConfig,
    LoggingConfigurationError,
    LoggingInitializationError,
    LoggingManager,
    MaximumLevelFilter,
    SensitiveDataFilter,
    build_logging_manager,
    configure_logging,
    get_logger,
    get_logging_manager,
    redact_sensitive_data,
    reset_logging_manager,
)
from config.settings import build_settings


@pytest.fixture(autouse=True)
def clear_global_logging_manager() -> Generator[None, None, None]:
    """
    Prevent global logging state from leaking between tests.
    """

    reset_logging_manager()

    yield

    reset_logging_manager()


def make_logging_config(
    tmp_path: Path,
    **overrides: object,
) -> LoggingConfig:
    """
    Build a reusable logging configuration.
    """

    values: dict[str, object] = {
        "logger_name": "test_ai_mutual_fund_assistant",
        "log_level": "DEBUG",
        "log_directory": tmp_path / "logs",
        "console_enabled": False,
        "file_enabled": True,
        "application_log_filename": "application.log",
        "error_log_filename": "error.log",
        "max_bytes": 1024 * 1024,
        "backup_count": 3,
        "propagate": False,
    }

    values.update(overrides)

    return LoggingConfig(**values)  # type: ignore[arg-type]


def flush_logger_handlers(
    logger: logging.Logger,
) -> None:
    """
    Flush every handler attached to a logger.
    """

    for handler in logger.handlers:
        handler.flush()


def test_logging_config_accepts_valid_values(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    assert config.logger_name == (
        "test_ai_mutual_fund_assistant"
    )
    assert config.log_level == "DEBUG"
    assert config.console_enabled is False
    assert config.file_enabled is True
    assert config.max_bytes == 1024 * 1024
    assert config.backup_count == 3
    assert config.propagate is False


def test_logging_config_is_immutable(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    with pytest.raises(FrozenInstanceError):
        config.log_level = "INFO"  # type: ignore[misc]


def test_logging_config_normalizes_logger_name(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        logger_name="  portfolio.application  ",
    )

    assert config.logger_name == "portfolio.application"


def test_logging_config_normalizes_log_level(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        log_level="  warning  ",
    )

    assert config.log_level == "WARNING"
    assert config.numeric_log_level == logging.WARNING


def test_logging_config_resolves_log_directory(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "nested" / ".." / "logs"

    config = make_logging_config(
        tmp_path,
        log_directory=directory,
    )

    assert config.log_directory.is_absolute()
    assert config.log_directory == directory.resolve()


def test_logging_config_builds_log_paths(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    assert config.application_log_path == (
        config.log_directory / "application.log"
    )
    assert config.error_log_path == (
        config.log_directory / "error.log"
    )


def test_logging_config_rejects_non_string_logger_name(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="logger_name must be a string",
    ):
        make_logging_config(
            tmp_path,
            logger_name=123,
        )


def test_logging_config_rejects_empty_logger_name(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="logger_name must not be empty",
    ):
        make_logging_config(
            tmp_path,
            logger_name="   ",
        )


def test_logging_config_rejects_non_string_log_level(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="log_level must be a string",
    ):
        make_logging_config(
            tmp_path,
            log_level=20,
        )


def test_logging_config_rejects_invalid_log_level(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="Unsupported log level",
    ):
        make_logging_config(
            tmp_path,
            log_level="VERBOSE",
        )


@pytest.mark.parametrize(
    "level",
    [
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    ],
)
def test_logging_config_accepts_supported_log_levels(
    tmp_path: Path,
    level: str,
) -> None:
    config = make_logging_config(
        tmp_path,
        log_level=level,
    )

    assert config.log_level == level


def test_logging_config_rejects_invalid_log_directory_type(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="log_directory must be a string or Path",
    ):
        make_logging_config(
            tmp_path,
            log_directory=object(),
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("console_enabled", "true"),
        ("file_enabled", 1),
        ("propagate", None),
    ],
)
def test_logging_config_rejects_non_boolean_fields(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    arguments = {
        field_name: value,
    }

    with pytest.raises(
        TypeError,
        match=f"{field_name} must be a boolean",
    ):
        make_logging_config(
            tmp_path,
            **arguments,
        )


def test_logging_config_rejects_non_integer_max_bytes(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="max_bytes must be an integer",
    ):
        make_logging_config(
            tmp_path,
            max_bytes=100.5,
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        -100,
    ],
)
def test_logging_config_rejects_non_positive_max_bytes(
    tmp_path: Path,
    value: int,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="max_bytes must be greater than zero",
    ):
        make_logging_config(
            tmp_path,
            max_bytes=value,
        )


def test_logging_config_rejects_non_integer_backup_count(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="backup_count must be an integer",
    ):
        make_logging_config(
            tmp_path,
            backup_count=2.5,
        )


def test_logging_config_rejects_negative_backup_count(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="backup_count must be zero or greater",
    ):
        make_logging_config(
            tmp_path,
            backup_count=-1,
        )


def test_logging_config_accepts_zero_backup_count(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        backup_count=0,
    )

    assert config.backup_count == 0


@pytest.mark.parametrize(
    "field_name",
    [
        "application_log_filename",
        "error_log_filename",
    ],
)
def test_logging_config_rejects_empty_log_filename(
    tmp_path: Path,
    field_name: str,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match=f"{field_name} must not be empty",
    ):
        make_logging_config(
            tmp_path,
            **{field_name: "   "},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "application_log_filename",
        "error_log_filename",
    ],
)
def test_logging_config_rejects_filename_with_directory(
    tmp_path: Path,
    field_name: str,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="must contain only a filename",
    ):
        make_logging_config(
            tmp_path,
            **{field_name: "nested/output.log"},
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "application_log_filename",
        "error_log_filename",
    ],
)
def test_logging_config_requires_log_extension(
    tmp_path: Path,
    field_name: str,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match=r"must use the \.log extension",
    ):
        make_logging_config(
            tmp_path,
            **{field_name: "output.txt"},
        )


def test_logging_config_rejects_duplicate_log_filenames(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="must be different",
    ):
        make_logging_config(
            tmp_path,
            application_log_filename="shared.log",
            error_log_filename="shared.log",
        )


def test_logging_config_rejects_empty_log_format(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="log_format must not be empty",
    ):
        make_logging_config(
            tmp_path,
            log_format="   ",
        )


def test_logging_config_rejects_empty_date_format(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        LoggingConfigurationError,
        match="date_format must not be empty",
    ):
        make_logging_config(
            tmp_path,
            date_format="   ",
        )


def test_logging_config_from_application_settings(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_LOG_LEVEL": "WARNING",
        },
        project_root=tmp_path,
    )

    config = LoggingConfig.from_application_settings(
        settings,
        logger_name="portfolio",
        console_enabled=False,
        file_enabled=True,
    )

    assert config.logger_name == "portfolio"
    assert config.log_level == "WARNING"
    assert config.log_directory == (
        settings.log_directory.resolve()
    )
    assert config.console_enabled is False
    assert config.file_enabled is True


def test_logging_config_from_application_settings_rejects_wrong_type() -> None:
    with pytest.raises(
        TypeError,
        match="settings must be an ApplicationSettings instance",
    ):
        LoggingConfig.from_application_settings(
            {}  # type: ignore[arg-type]
        )


def test_sensitive_data_redaction_for_password_assignment() -> None:
    result = redact_sensitive_data(
        "password=super-secret"
    )

    assert "super-secret" not in result
    assert "***REDACTED***" in result


def test_sensitive_data_redaction_for_quoted_secret() -> None:
    result = redact_sensitive_data(
        'secret: "hidden-value"'
    )

    assert "hidden-value" not in result
    assert '"***REDACTED***"' in result


def test_sensitive_data_redaction_for_api_key() -> None:
    result = redact_sensitive_data(
        "api_key=my-api-key"
    )

    assert "my-api-key" not in result
    assert "***REDACTED***" in result


def test_sensitive_data_redaction_for_bearer_token() -> None:
    result = redact_sensitive_data(
        "Authorization: Bearer abc.def.ghi"
    )

    assert "abc.def.ghi" not in result
    assert "Bearer ***REDACTED***" in result


def test_sensitive_data_redaction_for_database_url() -> None:
    result = redact_sensitive_data(
        "Connecting to "
        "postgresql://portfolio:password123@localhost/database"
    )

    assert "password123" not in result
    assert "***REDACTED***" in result


def test_sensitive_data_redaction_preserves_safe_text() -> None:
    message = "Portfolio refresh completed successfully."

    assert redact_sensitive_data(message) == message


def test_sensitive_data_redaction_accepts_non_string() -> None:
    result = redact_sensitive_data(
        {
            "token": "sensitive-token",
        }
    )

    assert isinstance(result, str)
    assert "sensitive-token" not in result


def test_sensitive_data_filter_redacts_record_message() -> None:
    record = logging.LogRecord(
        name="portfolio",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="password=%s",
        args=("secret-value",),
        exc_info=None,
    )

    log_filter = SensitiveDataFilter()

    assert log_filter.filter(record) is True
    assert "secret-value" not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()
    assert record.args == ()


def test_sensitive_data_filter_handles_formatting_failure() -> None:
    record = logging.LogRecord(
        name="portfolio",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="%s %s",
        args=("only-one-value",),
        exc_info=None,
    )

    log_filter = SensitiveDataFilter()

    assert log_filter.filter(record) is True
    assert record.args == ()
    assert "Unable to safely format" in str(record.msg)


def test_maximum_level_filter_accepts_matching_level() -> None:
    log_filter = MaximumLevelFilter(logging.WARNING)

    record = logging.LogRecord(
        name="portfolio",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="warning",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(record) is True


def test_maximum_level_filter_accepts_lower_level() -> None:
    log_filter = MaximumLevelFilter(logging.WARNING)

    record = logging.LogRecord(
        name="portfolio",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="information",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(record) is True


def test_maximum_level_filter_rejects_higher_level() -> None:
    log_filter = MaximumLevelFilter(logging.WARNING)

    record = logging.LogRecord(
        name="portfolio",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="error",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(record) is False


def test_maximum_level_filter_rejects_non_integer_level() -> None:
    with pytest.raises(
        TypeError,
        match="maximum_level must be an integer",
    ):
        MaximumLevelFilter(
            "WARNING"  # type: ignore[arg-type]
        )


def test_logging_manager_rejects_invalid_config() -> None:
    with pytest.raises(
        TypeError,
        match="config must be a LoggingConfig instance",
    ):
        LoggingManager(
            {}  # type: ignore[arg-type]
        )


def test_logging_manager_starts_uninitialized(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    assert manager.is_initialized is False


def test_logging_manager_logger_property_requires_initialization(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    with pytest.raises(
        LoggingInitializationError,
        match="has not been initialized",
    ):
        _ = manager.logger


def test_logging_manager_initializes_logger(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        logger = manager.initialize()

        assert manager.is_initialized is True
        assert manager.logger is logger
        assert logger.name == (
            "test_ai_mutual_fund_assistant"
        )
        assert logger.level == logging.DEBUG
        assert logger.propagate is False
    finally:
        manager.shutdown()


def test_logging_manager_initialize_is_idempotent(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        first = manager.initialize()
        first_handlers = tuple(first.handlers)

        second = manager.initialize()
        second_handlers = tuple(second.handlers)

        assert first is second
        assert first_handlers == second_handlers
    finally:
        manager.shutdown()


def test_logging_manager_force_initialize_rebuilds_handlers(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        logger = manager.initialize()
        first_handlers = tuple(logger.handlers)

        rebuilt = manager.initialize(force=True)
        second_handlers = tuple(rebuilt.handlers)

        assert rebuilt is logger
        assert first_handlers != second_handlers
        assert len(second_handlers) == 2
    finally:
        manager.shutdown()


def test_logging_manager_creates_log_directory(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    assert config.log_directory.exists() is False

    try:
        manager.initialize()

        assert config.log_directory.exists() is True
        assert config.log_directory.is_dir() is True
    finally:
        manager.shutdown()


def test_logging_manager_rejects_log_path_that_is_file(
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / "logs"
    invalid_path.write_text(
        "not a directory",
        encoding="utf-8",
    )

    config = make_logging_config(
        tmp_path,
        log_directory=invalid_path,
    )
    manager = LoggingManager(config)

    with pytest.raises(
        LoggingInitializationError,
        match="Unable to initialize logging",
    ):
        manager.initialize()


def test_logging_manager_console_only_configuration(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        console_enabled=True,
        file_enabled=False,
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()

        assert len(logger.handlers) == 1
        assert isinstance(
            logger.handlers[0],
            logging.StreamHandler,
        )
    finally:
        manager.shutdown()


def test_logging_manager_file_only_configuration(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        console_enabled=False,
        file_enabled=True,
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()

        assert len(logger.handlers) == 2
    finally:
        manager.shutdown()


def test_logging_manager_adds_null_handler_when_all_outputs_disabled(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        console_enabled=False,
        file_enabled=False,
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()

        assert len(logger.handlers) == 1
        assert isinstance(
            logger.handlers[0],
            logging.NullHandler,
        )
    finally:
        manager.shutdown()


def test_logging_manager_writes_debug_and_info_to_application_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.debug("debug message")
        logger.info("information message")
        flush_logger_handlers(logger)

        content = config.application_log_path.read_text(
            encoding="utf-8"
        )

        assert "debug message" in content
        assert "information message" in content
    finally:
        manager.shutdown()


def test_logging_manager_writes_warning_to_application_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.warning("warning message")
        flush_logger_handlers(logger)

        content = config.application_log_path.read_text(
            encoding="utf-8"
        )

        assert "warning message" in content
    finally:
        manager.shutdown()


def test_logging_manager_excludes_error_from_application_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.error("error-only message")
        flush_logger_handlers(logger)

        if config.application_log_path.exists():
            application_content = (
                config.application_log_path.read_text(
                    encoding="utf-8"
                )
            )
        else:
            application_content = ""

        assert "error-only message" not in application_content
    finally:
        manager.shutdown()


def test_logging_manager_writes_error_to_error_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.error("database failure")
        flush_logger_handlers(logger)

        content = config.error_log_path.read_text(
            encoding="utf-8"
        )

        assert "database failure" in content
    finally:
        manager.shutdown()


def test_logging_manager_writes_critical_to_error_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.critical("critical failure")
        flush_logger_handlers(logger)

        content = config.error_log_path.read_text(
            encoding="utf-8"
        )

        assert "critical failure" in content
    finally:
        manager.shutdown()


def test_logging_manager_excludes_info_from_error_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.info("normal event")
        flush_logger_handlers(logger)

        if config.error_log_path.exists():
            content = config.error_log_path.read_text(
                encoding="utf-8"
            )
        else:
            content = ""

        assert "normal event" not in content
    finally:
        manager.shutdown()


def test_logging_manager_redacts_sensitive_data_in_application_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.info(
            "Using api_key=%s",
            "highly-sensitive-key",
        )
        flush_logger_handlers(logger)

        content = config.application_log_path.read_text(
            encoding="utf-8"
        )

        assert "highly-sensitive-key" not in content
        assert "***REDACTED***" in content
    finally:
        manager.shutdown()


def test_logging_manager_redacts_sensitive_data_in_error_log(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.error(
            "Authentication failed token=%s",
            "private-token",
        )
        flush_logger_handlers(logger)

        content = config.error_log_path.read_text(
            encoding="utf-8"
        )

        assert "private-token" not in content
        assert "***REDACTED***" in content
    finally:
        manager.shutdown()


def test_logging_manager_get_logger_returns_parent(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        parent = manager.initialize()

        assert manager.get_logger() is parent
        assert (
            manager.get_logger(parent.name)
            is parent
        )
    finally:
        manager.shutdown()


def test_logging_manager_get_logger_returns_child(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        parent = manager.initialize()
        child = manager.get_logger(
            "services.portfolio"
        )

        assert child.name == (
            f"{parent.name}.services.portfolio"
        )
        assert child.parent is parent
    finally:
        manager.shutdown()


def test_logging_manager_get_logger_accepts_full_child_name(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        parent = manager.initialize()
        full_name = f"{parent.name}.repositories"

        child = manager.get_logger(full_name)

        assert child.name == full_name
    finally:
        manager.shutdown()


def test_logging_manager_get_logger_rejects_empty_name(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        manager.initialize()

        with pytest.raises(
            LoggingConfigurationError,
            match="name must not be empty",
        ):
            manager.get_logger("   ")
    finally:
        manager.shutdown()


def test_logging_manager_get_logger_initializes_automatically(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    try:
        child = manager.get_logger(
            "services.analytics"
        )

        assert manager.is_initialized is True
        assert child.name.endswith(
            ".services.analytics"
        )
    finally:
        manager.shutdown()


def test_logging_manager_shutdown_removes_handlers(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    logger = manager.initialize()

    assert logger.handlers

    manager.shutdown()

    assert manager.is_initialized is False
    assert logger.handlers == []


def test_logging_manager_shutdown_is_idempotent(
    tmp_path: Path,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    manager.initialize()
    manager.shutdown()
    manager.shutdown()

    assert manager.is_initialized is False


def test_build_logging_manager_from_explicit_config(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    manager = build_logging_manager(
        config=config
    )

    assert manager.config is config
    assert manager.is_initialized is False


def test_build_logging_manager_from_settings(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_LOG_LEVEL": "ERROR",
        },
        project_root=tmp_path,
    )

    manager = build_logging_manager(
        settings=settings
    )

    assert manager.config.log_level == "ERROR"
    assert manager.config.log_directory == (
        settings.log_directory.resolve()
    )


def test_build_logging_manager_rejects_settings_and_config(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    with pytest.raises(
        LoggingConfigurationError,
        match="either settings or config, not both",
    ):
        build_logging_manager(
            settings=settings,
            config=make_logging_config(tmp_path),
        )


def test_get_logging_manager_returns_cached_instance(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    first = get_logging_manager(
        config=config
    )
    second = get_logging_manager()

    assert first is second
    assert first.is_initialized is True


def test_get_logging_manager_reload_replaces_instance(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    first = get_logging_manager(
        config=config
    )

    second = get_logging_manager(
        reload=True,
        config=config,
    )

    assert first is not second
    assert first.is_initialized is False
    assert second.is_initialized is True


def test_get_logging_manager_rejects_settings_and_config(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    with pytest.raises(
        LoggingConfigurationError,
        match="either settings or config, not both",
    ):
        get_logging_manager(
            settings=settings,
            config=make_logging_config(tmp_path),
        )


def test_configure_logging_returns_global_logger(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    logger = configure_logging(
        config=config
    )

    assert isinstance(logger, logging.Logger)
    assert logger.name == config.logger_name


def test_configure_logging_force_rebuilds_manager(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    first_logger = configure_logging(
        config=config
    )
    first_handlers = tuple(first_logger.handlers)

    second_logger = configure_logging(
        config=config,
        force=True,
    )
    second_handlers = tuple(second_logger.handlers)

    assert first_logger is second_logger
    assert first_handlers != second_handlers


def test_global_get_logger_returns_child_logger(
    tmp_path: Path,
) -> None:
    config = make_logging_config(tmp_path)

    configure_logging(
        config=config
    )

    child = get_logger(
        "services.reporting"
    )

    assert child.name == (
        f"{config.logger_name}.services.reporting"
    )


def test_reset_logging_manager_shuts_down_cached_manager(
    tmp_path: Path,
) -> None:
    manager = get_logging_manager(
        config=make_logging_config(tmp_path)
    )

    assert manager.is_initialized is True

    reset_logging_manager()

    assert manager.is_initialized is False


def test_initialize_wraps_handler_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LoggingManager(
        make_logging_config(tmp_path)
    )

    monkeypatch.setattr(
        manager,
        "_create_application_file_handler",
        MagicMock(
            side_effect=OSError(
                "handler creation failed"
            )
        ),
    )

    with pytest.raises(
        LoggingInitializationError,
        match="Unable to initialize logging",
    ):
        manager.initialize()


def test_initialize_cleans_handlers_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = LoggingManager(
        make_logging_config(
            tmp_path,
            console_enabled=True,
            file_enabled=True,
        )
    )

    monkeypatch.setattr(
        manager,
        "_create_application_file_handler",
        MagicMock(
            side_effect=OSError(
                "handler creation failed"
            )
        ),
    )

    logger = logging.getLogger(
        manager.config.logger_name
    )

    with pytest.raises(
        LoggingInitializationError,
    ):
        manager.initialize()

    assert logger.handlers == []
    assert manager.is_initialized is False


def test_logging_manager_respects_configured_level(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        log_level="WARNING",
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.info("excluded message")
        logger.warning("included message")
        flush_logger_handlers(logger)

        content = config.application_log_path.read_text(
            encoding="utf-8"
        )

        assert "excluded message" not in content
        assert "included message" in content
    finally:
        manager.shutdown()


def test_logging_manager_uses_custom_format(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        log_format="%(levelname)s:%(message)s",
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.info("custom format message")
        flush_logger_handlers(logger)

        content = config.application_log_path.read_text(
            encoding="utf-8"
        )

        assert "INFO:custom format message" in content
    finally:
        manager.shutdown()


def test_logging_manager_uses_custom_filenames(
    tmp_path: Path,
) -> None:
    config = make_logging_config(
        tmp_path,
        application_log_filename="portfolio.log",
        error_log_filename="failures.log",
    )
    manager = LoggingManager(config)

    try:
        logger = manager.initialize()
        logger.info("portfolio event")
        logger.error("failure event")
        flush_logger_handlers(logger)

        assert (
            config.log_directory / "portfolio.log"
        ).exists()
        assert (
            config.log_directory / "failures.log"
        ).exists()
    finally:
        manager.shutdown()