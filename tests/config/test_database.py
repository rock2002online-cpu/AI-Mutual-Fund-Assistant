"""
Unit tests for centralized SQLAlchemy database configuration.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import (
    DatabaseConfig,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseHealthCheckError,
    DatabaseManager,
    DatabaseSessionError,
    build_database_manager,
    check_database_health,
    create_database_engine,
    create_session_factory,
    database_configuration_summary,
    database_session,
    get_database_manager,
    reset_database_manager,
)
from config.settings import (
    ApplicationEnvironment,
    build_settings,
)


@pytest.fixture(autouse=True)
def clear_global_database_manager() -> Generator[None, None, None]:
    """
    Ensure global database state does not leak between tests.
    """

    reset_database_manager()

    yield

    reset_database_manager()


def make_memory_config(
    **overrides: object,
) -> DatabaseConfig:
    """
    Create a reusable in-memory SQLite configuration.
    """

    values: dict[str, object] = {
        "url": "sqlite+pysqlite:///:memory:",
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle_seconds": 1_800,
        "sqlite_timeout_seconds": 30.0,
        "session_autoflush": False,
        "session_expire_on_commit": False,
    }

    values.update(overrides)

    return DatabaseConfig(**values)  # type: ignore[arg-type]


def test_database_config_accepts_valid_sqlite_url() -> None:
    config = DatabaseConfig(
        url="sqlite+pysqlite:///:memory:"
    )

    assert config.url == "sqlite+pysqlite:///:memory:"
    assert config.dialect_name == "sqlite+pysqlite"
    assert config.is_sqlite is True
    assert config.is_memory_database is True


def test_database_config_strips_url_whitespace() -> None:
    config = DatabaseConfig(
        url="  sqlite+pysqlite:///:memory:  "
    )

    assert config.url == "sqlite+pysqlite:///:memory:"


def test_database_config_defaults_are_correct() -> None:
    config = make_memory_config()

    assert config.echo is False
    assert config.pool_pre_ping is True
    assert config.pool_recycle_seconds == 1_800
    assert config.sqlite_timeout_seconds == 30.0
    assert config.session_autoflush is False
    assert config.session_expire_on_commit is False


def test_database_config_is_immutable() -> None:
    config = make_memory_config()

    with pytest.raises(FrozenInstanceError):
        config.echo = True  # type: ignore[misc]


def test_database_config_rejects_non_string_url() -> None:
    with pytest.raises(
        TypeError,
        match="url must be a string",
    ):
        DatabaseConfig(url=123)  # type: ignore[arg-type]


def test_database_config_rejects_empty_url() -> None:
    with pytest.raises(
        DatabaseConfigurationError,
        match="url must not be empty",
    ):
        DatabaseConfig(url="   ")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("echo", "false"),
        ("pool_pre_ping", 1),
        ("session_autoflush", "false"),
        ("session_expire_on_commit", 0),
    ],
)
def test_database_config_rejects_non_boolean_fields(
    field_name: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "url": "sqlite+pysqlite:///:memory:",
        field_name: value,
    }

    with pytest.raises(
        TypeError,
        match=f"{field_name} must be a boolean",
    ):
        DatabaseConfig(**arguments)  # type: ignore[arg-type]


def test_database_config_rejects_non_integer_pool_recycle() -> None:
    with pytest.raises(
        TypeError,
        match="pool_recycle_seconds must be an integer",
    ):
        make_memory_config(
            pool_recycle_seconds=10.5
        )


def test_database_config_allows_negative_one_pool_recycle() -> None:
    config = make_memory_config(
        pool_recycle_seconds=-1
    )

    assert config.pool_recycle_seconds == -1


def test_database_config_rejects_pool_recycle_below_negative_one() -> None:
    with pytest.raises(
        DatabaseConfigurationError,
        match="must be -1 or greater",
    ):
        make_memory_config(
            pool_recycle_seconds=-2
        )


def test_database_config_rejects_non_numeric_sqlite_timeout() -> None:
    with pytest.raises(
        TypeError,
        match="sqlite_timeout_seconds must be numeric",
    ):
        make_memory_config(
            sqlite_timeout_seconds="30"
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        0.0,
        -1,
        -0.5,
    ],
)
def test_database_config_rejects_non_positive_sqlite_timeout(
    value: float,
) -> None:
    with pytest.raises(
        DatabaseConfigurationError,
        match="must be greater than zero",
    ):
        make_memory_config(
            sqlite_timeout_seconds=value
        )


def test_database_config_normalizes_sqlite_timeout_to_float() -> None:
    config = make_memory_config(
        sqlite_timeout_seconds=15
    )

    assert config.sqlite_timeout_seconds == 15.0
    assert isinstance(
        config.sqlite_timeout_seconds,
        float,
    )


def test_database_config_identifies_file_sqlite_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "application.db"

    config = DatabaseConfig(
        url=f"sqlite:///{database_path.as_posix()}"
    )

    assert config.is_sqlite is True
    assert config.is_memory_database is False


def test_database_config_identifies_non_sqlite_database() -> None:
    config = DatabaseConfig(
        url="postgresql://user:password@localhost/database"
    )

    assert config.is_sqlite is False
    assert config.is_memory_database is False
    assert config.dialect_name == "postgresql"


def test_database_config_from_application_settings(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_ENVIRONMENT": "testing",
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    config = DatabaseConfig.from_application_settings(
        settings
    )

    assert config.url == "sqlite+pysqlite:///:memory:"
    assert config.echo is False


def test_database_config_from_application_settings_enables_echo_in_debug(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_ENVIRONMENT": "development",
            "AIMF_DEBUG": "true",
        },
        project_root=tmp_path,
    )

    config = DatabaseConfig.from_application_settings(
        settings
    )

    assert config.echo is True


def test_database_config_from_application_settings_disables_echo_in_production(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_ENVIRONMENT": "production",
            "AIMF_DEBUG": "true",
        },
        project_root=tmp_path,
    )

    config = DatabaseConfig.from_application_settings(
        settings
    )

    assert (
        settings.environment
        is ApplicationEnvironment.PRODUCTION
    )
    assert config.echo is False


def test_database_config_from_application_settings_supports_echo_override(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    config = DatabaseConfig.from_application_settings(
        settings,
        echo=True,
    )

    assert config.echo is True


def test_database_config_from_application_settings_rejects_wrong_type() -> None:
    with pytest.raises(
        TypeError,
        match="settings must be an ApplicationSettings instance",
    ):
        DatabaseConfig.from_application_settings(
            {}  # type: ignore[arg-type]
        )


def test_create_database_engine_returns_engine() -> None:
    engine = create_database_engine(
        make_memory_config()
    )

    try:
        assert isinstance(engine, Engine)
    finally:
        engine.dispose()


def test_create_database_engine_uses_static_pool_for_memory_sqlite() -> None:
    engine = create_database_engine(
        make_memory_config()
    )

    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()


def test_create_database_engine_supports_file_sqlite(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "application.db"

    config = DatabaseConfig(
        url=f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(config)

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            ).scalar_one()

        assert result == 1
    finally:
        engine.dispose()


def test_create_database_engine_rejects_wrong_config_type() -> None:
    with pytest.raises(
        TypeError,
        match="config must be a DatabaseConfig instance",
    ):
        create_database_engine(
            {}  # type: ignore[arg-type]
        )


def test_create_database_engine_wraps_unknown_dialect() -> None:
    config = DatabaseConfig(
        url="unknown_database_driver://localhost/database"
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="Unable to create SQLAlchemy engine",
    ):
        create_database_engine(config)


def test_create_session_factory_returns_sessionmaker() -> None:
    engine = create_database_engine(
        make_memory_config()
    )

    try:
        factory = create_session_factory(engine)
        session = factory()

        try:
            assert isinstance(session, Session)
            assert session.autoflush is False
            assert session.expire_on_commit is False
        finally:
            session.close()
    finally:
        engine.dispose()


def test_create_session_factory_supports_session_options() -> None:
    engine = create_database_engine(
        make_memory_config()
    )

    try:
        factory = create_session_factory(
            engine,
            autoflush=True,
            expire_on_commit=True,
        )

        session = factory()

        try:
            assert session.autoflush is True
            assert session.expire_on_commit is True
        finally:
            session.close()
    finally:
        engine.dispose()


def test_create_session_factory_rejects_invalid_engine() -> None:
    with pytest.raises(
        TypeError,
        match="engine must be a SQLAlchemy Engine",
    ):
        create_session_factory(
            object()  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("argument_name", "value"),
    [
        ("autoflush", "false"),
        ("expire_on_commit", 0),
    ],
)
def test_create_session_factory_rejects_invalid_boolean_options(
    argument_name: str,
    value: object,
) -> None:
    engine = create_database_engine(
        make_memory_config()
    )

    arguments: dict[str, object] = {
        argument_name: value,
    }

    try:
        with pytest.raises(
            TypeError,
            match=f"{argument_name} must be a boolean",
        ):
            create_session_factory(
                engine,
                **arguments,  # type: ignore[arg-type]
            )
    finally:
        engine.dispose()


def test_database_manager_initializes_without_connecting() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        assert manager.is_disposed is False
        assert isinstance(manager.engine, Engine)
        assert manager.config.is_memory_database is True
    finally:
        manager.dispose()


def test_database_manager_rejects_invalid_config() -> None:
    with pytest.raises(
        TypeError,
        match="config must be a DatabaseConfig instance",
    ):
        DatabaseManager(
            {}  # type: ignore[arg-type]
        )


def test_database_manager_connect_succeeds() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        assert manager.connect() is None
    finally:
        manager.dispose()


def test_database_manager_health_check_succeeds() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        assert manager.health_check() is True
    finally:
        manager.dispose()


def test_database_manager_new_session_returns_session() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        session = manager.new_session()

        try:
            assert isinstance(session, Session)
        finally:
            session.close()
    finally:
        manager.dispose()


def test_database_manager_session_scope_commits_transaction() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        with manager.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE investments (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL
                    )
                    """
                )
            )

        with manager.session_scope() as session:
            session.execute(
                text(
                    """
                    INSERT INTO investments (id, name)
                    VALUES (1, 'Index Fund')
                    """
                )
            )

        with manager.engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT name
                    FROM investments
                    WHERE id = 1
                    """
                )
            ).scalar_one()

        assert result == "Index Fund"
    finally:
        manager.dispose()


def test_database_manager_session_scope_rolls_back_caller_exception() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        with manager.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE transactions (
                        id INTEGER PRIMARY KEY,
                        amount REAL NOT NULL
                    )
                    """
                )
            )

        with pytest.raises(
            ValueError,
            match="caller failure",
        ):
            with manager.session_scope() as session:
                session.execute(
                    text(
                        """
                        INSERT INTO transactions (id, amount)
                        VALUES (1, 1000.0)
                        """
                    )
                )

                raise ValueError("caller failure")

        with manager.engine.connect() as connection:
            count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM transactions
                    """
                )
            ).scalar_one()

        assert count == 0
    finally:
        manager.dispose()


def test_database_manager_session_scope_wraps_sqlalchemy_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    session = MagicMock()
    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    monkeypatch.setattr(
        manager,
        "new_session",
        lambda: session,
    )

    try:
        with pytest.raises(
            DatabaseSessionError,
            match="transaction failed",
        ):
            with manager.session_scope():
                pass

        session.rollback.assert_called_once()
        session.close.assert_called_once()
    finally:
        manager.dispose()


def test_database_manager_session_scope_closes_session_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    session = MagicMock()

    monkeypatch.setattr(
        manager,
        "new_session",
        lambda: session,
    )

    try:
        with manager.session_scope() as active_session:
            assert active_session is session

        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.close.assert_called_once()
    finally:
        manager.dispose()


def test_database_manager_dispose_is_idempotent() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    manager.dispose()
    manager.dispose()

    assert manager.is_disposed is True


@pytest.mark.parametrize(
    "operation",
    [
        "engine",
        "session_factory",
        "connect",
        "health_check",
        "new_session",
    ],
)
def test_database_manager_rejects_operations_after_disposal(
    operation: str,
) -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    manager.dispose()

    with pytest.raises(
        DatabaseConnectionError,
        match="has been disposed",
    ):
        attribute = getattr(manager, operation)

        if callable(attribute):
            attribute()


def test_build_database_manager_from_explicit_config() -> None:
    config = make_memory_config()

    manager = build_database_manager(
        config=config
    )

    try:
        assert manager.config is config
        assert manager.health_check() is True
    finally:
        manager.dispose()


def test_build_database_manager_from_settings(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    manager = build_database_manager(
        settings=settings
    )

    try:
        assert manager.config.url == (
            "sqlite+pysqlite:///:memory:"
        )
        assert manager.health_check() is True
    finally:
        manager.dispose()


def test_build_database_manager_rejects_settings_and_config(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={},
        project_root=tmp_path,
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="either settings or config, not both",
    ):
        build_database_manager(
            settings=settings,
            config=make_memory_config(),
        )


def test_get_database_manager_returns_cached_instance(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    first = get_database_manager(
        settings=settings
    )
    second = get_database_manager()

    assert first is second


def test_get_database_manager_reload_replaces_instance(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    first = get_database_manager(
        settings=settings
    )

    second = get_database_manager(
        reload=True,
        settings=settings,
    )

    assert first is not second
    assert first.is_disposed is True
    assert second.is_disposed is False


def test_reset_database_manager_disposes_cached_manager(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    manager = get_database_manager(
        settings=settings
    )

    reset_database_manager()

    assert manager.is_disposed is True


def test_database_session_uses_global_manager(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        environ={
            "AIMF_DATABASE_URL": (
                "sqlite+pysqlite:///:memory:"
            ),
            "AIMF_DEBUG": "false",
        },
        project_root=tmp_path,
    )

    manager = get_database_manager(
        settings=settings
    )

    with manager.engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL
                )
                """
            )
        )

    with database_session() as session:
        session.execute(
            text(
                """
                INSERT INTO users (id, username)
                VALUES (1, 'investor')
                """
            )
        )

    with manager.engine.connect() as connection:
        username = connection.execute(
            text(
                """
                SELECT username
                FROM users
                WHERE id = 1
                """
            )
        ).scalar_one()

    assert username == "investor"


def test_check_database_health_with_explicit_manager() -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    try:
        assert check_database_health(manager) is True
    finally:
        manager.dispose()


def test_check_database_health_rejects_wrong_manager_type() -> None:
    with pytest.raises(
        TypeError,
        match="manager must be a DatabaseManager instance",
    ):
        check_database_health(
            object()  # type: ignore[arg-type]
        )


def test_database_configuration_summary_contains_safe_values() -> None:
    config = DatabaseConfig(
        url=(
            "postgresql://portfolio_user:"
            "secret_password@localhost/portfolio"
        ),
        echo=True,
        pool_pre_ping=True,
        pool_recycle_seconds=900,
        session_autoflush=True,
        session_expire_on_commit=True,
    )

    summary = database_configuration_summary(
        config
    )

    assert summary["dialect"] == "postgresql"
    assert summary["is_sqlite"] is False
    assert summary["is_memory_database"] is False
    assert summary["echo"] is True
    assert summary["pool_pre_ping"] is True
    assert summary["pool_recycle_seconds"] == 900
    assert summary["session_autoflush"] is True
    assert summary["session_expire_on_commit"] is True
    assert "secret_password" not in str(summary["url"])
    assert "***" in str(summary["url"])


def test_database_configuration_summary_rejects_wrong_type() -> None:
    with pytest.raises(
        TypeError,
        match="config must be a DatabaseConfig instance",
    ):
        database_configuration_summary(
            {}  # type: ignore[arg-type]
        )


def test_database_health_check_wraps_sqlalchemy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    monkeypatch.setattr(
        manager._engine,
        "connect",
        MagicMock(
            side_effect=SQLAlchemyError(
                "connection failed"
            )
        ),
    )

    try:
        with pytest.raises(
            DatabaseHealthCheckError,
            match="health check failed",
        ):
            manager.health_check()
    finally:
        manager.dispose()


def test_database_connect_wraps_sqlalchemy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseManager(
        make_memory_config()
    )

    monkeypatch.setattr(
        manager._engine,
        "connect",
        MagicMock(
            side_effect=SQLAlchemyError(
                "connection failed"
            )
        ),
    )

    try:
        with pytest.raises(
            DatabaseConnectionError,
            match="Unable to connect",
        ):
            manager.connect()
    finally:
        manager.dispose()