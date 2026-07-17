"""
Centralized SQLAlchemy database configuration.

This module provides the database infrastructure for the
AI Mutual Fund Assistant enterprise platform.

Responsibilities
----------------
- Database URL validation
- SQLAlchemy engine creation
- SQLite-specific connection configuration
- Session factory creation
- Transaction-scoped session management
- Connection health checks
- Lazy process-wide database initialization
- Safe resource disposal
- Enterprise exception handling

The module does not define ORM models or repositories.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Any, Final, Generator, Mapping

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import ApplicationSettings, get_settings


# ============================================================
# Constants
# ============================================================

DEFAULT_SQLITE_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_POOL_PRE_PING: Final[bool] = True
DEFAULT_POOL_RECYCLE_SECONDS: Final[int] = 1_800
DEFAULT_SESSION_AUTOFLUSH: Final[bool] = False
DEFAULT_SESSION_EXPIRE_ON_COMMIT: Final[bool] = False

SQLITE_DIALECT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "sqlite",
        "sqlite+pysqlite",
    }
)


# ============================================================
# Exceptions
# ============================================================


class DatabaseError(RuntimeError):
    """
    Base exception for database configuration and runtime failures.
    """


class DatabaseConfigurationError(DatabaseError):
    """
    Raised when database configuration is invalid.
    """


class DatabaseConnectionError(DatabaseError):
    """
    Raised when a database connection cannot be established.
    """


class DatabaseSessionError(DatabaseError):
    """
    Raised when a database session operation fails.
    """


class DatabaseHealthCheckError(DatabaseError):
    """
    Raised when a database health check cannot be completed.
    """


# ============================================================
# Immutable database configuration
# ============================================================


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """
    Immutable SQLAlchemy database configuration.

    Attributes:
        url:
            SQLAlchemy-compatible database URL.

        echo:
            Whether SQLAlchemy should emit SQL statements.

        pool_pre_ping:
            Whether pooled connections should be validated before use.

        pool_recycle_seconds:
            Maximum connection lifetime before recycling.

        sqlite_timeout_seconds:
            SQLite connection timeout.

        session_autoflush:
            Whether sessions automatically flush pending changes.

        session_expire_on_commit:
            Whether ORM instances expire after commit.
    """

    url: str
    echo: bool = False
    pool_pre_ping: bool = DEFAULT_POOL_PRE_PING
    pool_recycle_seconds: int = DEFAULT_POOL_RECYCLE_SECONDS
    sqlite_timeout_seconds: float = DEFAULT_SQLITE_TIMEOUT_SECONDS
    session_autoflush: bool = DEFAULT_SESSION_AUTOFLUSH
    session_expire_on_commit: bool = (
        DEFAULT_SESSION_EXPIRE_ON_COMMIT
    )

    def __post_init__(self) -> None:
        """
        Validate configuration values after construction.
        """

        normalized_url = _validate_database_url(self.url)

        if not isinstance(self.echo, bool):
            raise TypeError(
                "echo must be a boolean."
            )

        if not isinstance(self.pool_pre_ping, bool):
            raise TypeError(
                "pool_pre_ping must be a boolean."
            )

        if not isinstance(
            self.pool_recycle_seconds,
            int,
        ):
            raise TypeError(
                "pool_recycle_seconds must be an integer."
            )

        if self.pool_recycle_seconds < -1:
            raise DatabaseConfigurationError(
                "pool_recycle_seconds must be -1 or greater."
            )

        if not isinstance(
            self.sqlite_timeout_seconds,
            (int, float),
        ):
            raise TypeError(
                "sqlite_timeout_seconds must be numeric."
            )

        if self.sqlite_timeout_seconds <= 0:
            raise DatabaseConfigurationError(
                "sqlite_timeout_seconds must be greater than zero."
            )

        if not isinstance(
            self.session_autoflush,
            bool,
        ):
            raise TypeError(
                "session_autoflush must be a boolean."
            )

        if not isinstance(
            self.session_expire_on_commit,
            bool,
        ):
            raise TypeError(
                "session_expire_on_commit must be a boolean."
            )

        object.__setattr__(
            self,
            "url",
            normalized_url,
        )
        object.__setattr__(
            self,
            "sqlite_timeout_seconds",
            float(self.sqlite_timeout_seconds),
        )

    @property
    def sqlalchemy_url(self) -> URL:
        """
        Return the parsed SQLAlchemy URL.
        """

        try:
            return make_url(self.url)
        except Exception as exc:
            raise DatabaseConfigurationError(
                f"Invalid database URL: {self.url!r}."
            ) from exc

    @property
    def dialect_name(self) -> str:
        """
        Return the configured SQLAlchemy dialect name.
        """

        return self.sqlalchemy_url.drivername

    @property
    def is_sqlite(self) -> bool:
        """
        Return True when the configured database uses SQLite.
        """

        return (
            self.dialect_name
            in SQLITE_DIALECT_NAMES
            or self.dialect_name.startswith("sqlite+")
        )

    @property
    def is_memory_database(self) -> bool:
        """
        Return True for an in-memory SQLite database.
        """

        if not self.is_sqlite:
            return False

        database_name = self.sqlalchemy_url.database

        return database_name in {
            None,
            "",
            ":memory:",
        }

    @classmethod
    def from_application_settings(
        cls,
        settings: ApplicationSettings,
        *,
        echo: bool | None = None,
    ) -> DatabaseConfig:
        """
        Build database configuration from application settings.

        Args:
            settings:
                Validated application settings.

            echo:
                Optional SQL echo override. When omitted, debug mode is
                used only outside production.

        Returns:
            Immutable DatabaseConfig instance.
        """

        if not isinstance(
            settings,
            ApplicationSettings,
        ):
            raise TypeError(
                "settings must be an ApplicationSettings instance."
            )

        resolved_echo = (
            settings.debug and not settings.is_production
            if echo is None
            else echo
        )

        return cls(
            url=settings.database_url,
            echo=resolved_echo,
        )


# ============================================================
# Engine construction
# ============================================================


def create_database_engine(
    config: DatabaseConfig,
) -> Engine:
    """
    Create a SQLAlchemy engine from validated configuration.

    Args:
        config:
            Immutable database configuration.

    Returns:
        Configured SQLAlchemy Engine.

    Raises:
        TypeError:
            When config is not a DatabaseConfig instance.

        DatabaseConfigurationError:
            When engine creation fails because configuration is invalid.
    """

    if not isinstance(config, DatabaseConfig):
        raise TypeError(
            "config must be a DatabaseConfig instance."
        )

    engine_kwargs: dict[str, Any] = {
        "echo": config.echo,
        "future": True,
        "pool_pre_ping": config.pool_pre_ping,
    }

    if config.is_sqlite:
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": config.sqlite_timeout_seconds,
        }

        if config.is_memory_database:
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs["pool_recycle"] = (
                config.pool_recycle_seconds
            )
    else:
        engine_kwargs["pool_recycle"] = (
            config.pool_recycle_seconds
        )

    try:
        return create_engine(
            config.url,
            **engine_kwargs,
        )
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        raise DatabaseConfigurationError(
            "Unable to create SQLAlchemy engine for "
            f"{_redact_database_url(config.url)}."
        ) from exc


def create_session_factory(
    engine: Engine,
    *,
    autoflush: bool = DEFAULT_SESSION_AUTOFLUSH,
    expire_on_commit: bool = (
        DEFAULT_SESSION_EXPIRE_ON_COMMIT
    ),
) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy session factory.

    Args:
        engine:
            SQLAlchemy engine bound to new sessions.

        autoflush:
            Whether pending changes flush automatically.

        expire_on_commit:
            Whether ORM instances expire after commit.

    Returns:
        Configured SQLAlchemy sessionmaker.

    Raises:
        TypeError:
            When arguments have invalid types.
    """

    if not isinstance(engine, Engine):
        raise TypeError(
            "engine must be a SQLAlchemy Engine."
        )

    if not isinstance(autoflush, bool):
        raise TypeError(
            "autoflush must be a boolean."
        )

    if not isinstance(expire_on_commit, bool):
        raise TypeError(
            "expire_on_commit must be a boolean."
        )

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=autoflush,
        expire_on_commit=expire_on_commit,
    )


# ============================================================
# Database manager
# ============================================================


class DatabaseManager:
    """
    Coordinate engine and session lifecycle.

    The manager owns one SQLAlchemy engine and one session factory.
    It supports explicit connection checks, context-managed sessions,
    transactional commits, rollbacks, and disposal.
    """

    def __init__(
        self,
        config: DatabaseConfig,
    ) -> None:
        """
        Initialize the manager without opening a connection.
        """

        if not isinstance(config, DatabaseConfig):
            raise TypeError(
                "config must be a DatabaseConfig instance."
            )

        self._config = config
        self._engine = create_database_engine(config)
        self._session_factory = create_session_factory(
            self._engine,
            autoflush=config.session_autoflush,
            expire_on_commit=(
                config.session_expire_on_commit
            ),
        )
        self._disposed = False
        self._lock = RLock()

    @property
    def config(self) -> DatabaseConfig:
        """
        Return immutable database configuration.
        """

        return self._config

    @property
    def engine(self) -> Engine:
        """
        Return the active SQLAlchemy engine.

        Raises:
            DatabaseConnectionError:
                When the manager has already been disposed.
        """

        self._ensure_active()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        """
        Return the active SQLAlchemy session factory.
        """

        self._ensure_active()
        return self._session_factory

    @property
    def is_disposed(self) -> bool:
        """
        Return whether the manager has been disposed.
        """

        return self._disposed

    def connect(self) -> None:
        """
        Verify that the database accepts connections.

        Raises:
            DatabaseConnectionError:
                When connection establishment fails.
        """

        self._ensure_active()

        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(
                "Unable to connect to database "
                f"{_redact_database_url(self._config.url)}."
            ) from exc

    def health_check(self) -> bool:
        """
        Run a lightweight database health check.

        Returns:
            True when the database responds successfully.

        Raises:
            DatabaseHealthCheckError:
                When the check cannot be executed.
        """

        self._ensure_active()

        try:
            with self._engine.connect() as connection:
                result = connection.execute(
                    text("SELECT 1")
                ).scalar_one()

            return result == 1
        except SQLAlchemyError as exc:
            raise DatabaseHealthCheckError(
                "Database health check failed for "
                f"{_redact_database_url(self._config.url)}."
            ) from exc

    def new_session(self) -> Session:
        """
        Create a new unmanaged SQLAlchemy session.

        Callers using this method are responsible for closing the session.

        Returns:
            New SQLAlchemy Session.
        """

        self._ensure_active()

        try:
            return self._session_factory()
        except SQLAlchemyError as exc:
            raise DatabaseSessionError(
                "Unable to create database session."
            ) from exc

    @contextmanager
    def session_scope(
        self,
    ) -> Generator[Session, None, None]:
        """
        Provide a transaction-scoped session.

        The session commits when the context exits successfully.
        It rolls back on any exception and always closes.

        Yields:
            Active SQLAlchemy Session.

        Raises:
            DatabaseSessionError:
                When SQLAlchemy fails during the transaction.

            Exception:
                Non-SQLAlchemy exceptions raised by caller code are
                rolled back and re-raised unchanged.
        """

        session = self.new_session()

        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()

            raise DatabaseSessionError(
                "Database session transaction failed."
            ) from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """
        Dispose the engine and release pooled connections.

        This method is idempotent.
        """

        with self._lock:
            if self._disposed:
                return

            try:
                self._engine.dispose()
            except SQLAlchemyError as exc:
                raise DatabaseConnectionError(
                    "Unable to dispose database engine."
                ) from exc

            self._disposed = True

    def _ensure_active(self) -> None:
        """
        Ensure the manager has not been disposed.
        """

        if self._disposed:
            raise DatabaseConnectionError(
                "Database manager has been disposed."
            )


# ============================================================
# Process-wide database manager
# ============================================================

_database_manager: DatabaseManager | None = None
_database_manager_lock = RLock()


def build_database_manager(
    *,
    settings: ApplicationSettings | None = None,
    config: DatabaseConfig | None = None,
) -> DatabaseManager:
    """
    Build a new database manager.

    Args:
        settings:
            Optional application settings used when config is absent.

        config:
            Optional explicit database configuration.

    Returns:
        New DatabaseManager instance.

    Raises:
        DatabaseConfigurationError:
            When both settings and config are supplied.
    """

    if settings is not None and config is not None:
        raise DatabaseConfigurationError(
            "Provide either settings or config, not both."
        )

    resolved_config: DatabaseConfig

    if config is not None:
        resolved_config = config
    else:
        resolved_settings = (
            get_settings()
            if settings is None
            else settings
        )
        resolved_config = (
            DatabaseConfig.from_application_settings(
                resolved_settings
            )
        )

    return DatabaseManager(resolved_config)


def get_database_manager(
    *,
    reload: bool = False,
    settings: ApplicationSettings | None = None,
) -> DatabaseManager:
    """
    Return the process-wide database manager.

    Args:
        reload:
            Dispose and rebuild the cached manager.

        settings:
            Optional settings used only when constructing a new manager.

    Returns:
        Cached DatabaseManager instance.
    """

    global _database_manager

    with _database_manager_lock:
        if reload and _database_manager is not None:
            _database_manager.dispose()
            _database_manager = None

        if _database_manager is None:
            _database_manager = build_database_manager(
                settings=settings
            )

        return _database_manager


def reset_database_manager() -> None:
    """
    Dispose and clear the cached database manager.
    """

    global _database_manager

    with _database_manager_lock:
        if _database_manager is not None:
            _database_manager.dispose()

        _database_manager = None


@contextmanager
def database_session() -> Generator[Session, None, None]:
    """
    Provide a transaction-scoped session from the global manager.
    """

    with get_database_manager().session_scope() as session:
        yield session


def check_database_health(
    manager: DatabaseManager | None = None,
) -> bool:
    """
    Check database connectivity.

    Args:
        manager:
            Optional manager. The global manager is used when omitted.

    Returns:
        True when the database responds successfully.
    """

    resolved_manager = (
        get_database_manager()
        if manager is None
        else manager
    )

    if not isinstance(
        resolved_manager,
        DatabaseManager,
    ):
        raise TypeError(
            "manager must be a DatabaseManager instance."
        )

    return resolved_manager.health_check()


# ============================================================
# Helpers
# ============================================================


def _validate_database_url(
    value: object,
) -> str:
    """
    Validate and normalize a SQLAlchemy database URL.
    """

    if not isinstance(value, str):
        raise TypeError(
            "url must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise DatabaseConfigurationError(
            "url must not be empty."
        )

    try:
        parsed_url = make_url(normalized_value)
    except Exception as exc:
        raise DatabaseConfigurationError(
            f"Invalid database URL: {normalized_value!r}."
        ) from exc

    if not parsed_url.drivername:
        raise DatabaseConfigurationError(
            "Database URL must include a dialect."
        )

    return normalized_value


def _redact_database_url(
    value: str,
) -> str:
    """
    Return a safely redacted database URL for error messages.
    """

    try:
        parsed_url = make_url(value)
        return parsed_url.render_as_string(
            hide_password=True
        )
    except Exception:
        return "<invalid-database-url>"


def database_configuration_summary(
    config: DatabaseConfig,
) -> Mapping[str, object]:
    """
    Return a non-sensitive database configuration summary.
    """

    if not isinstance(config, DatabaseConfig):
        raise TypeError(
            "config must be a DatabaseConfig instance."
        )

    return {
        "url": _redact_database_url(config.url),
        "dialect": config.dialect_name,
        "is_sqlite": config.is_sqlite,
        "is_memory_database": (
            config.is_memory_database
        ),
        "echo": config.echo,
        "pool_pre_ping": config.pool_pre_ping,
        "pool_recycle_seconds": (
            config.pool_recycle_seconds
        ),
        "session_autoflush": (
            config.session_autoflush
        ),
        "session_expire_on_commit": (
            config.session_expire_on_commit
        ),
    }


__all__ = [
    "DatabaseConfig",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseHealthCheckError",
    "DatabaseManager",
    "DatabaseSessionError",
    "build_database_manager",
    "check_database_health",
    "create_database_engine",
    "create_session_factory",
    "database_configuration_summary",
    "database_session",
    "get_database_manager",
    "reset_database_manager",
]