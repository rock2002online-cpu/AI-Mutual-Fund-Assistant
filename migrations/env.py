from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

# -------------------------------------------------------
# Project root
# -------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# -------------------------------------------------------
# Application imports
# -------------------------------------------------------

from config.database import get_database_manager
from models.base import Base

# Import all ORM models so they register with metadata.
import models  # noqa: F401

# -------------------------------------------------------
# Alembic Config
# -------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -------------------------------------------------------
# Metadata
# -------------------------------------------------------

target_metadata = Base.metadata

# -------------------------------------------------------
# Override URL from application configuration
# -------------------------------------------------------

database_manager = get_database_manager()

config.set_main_option(
    "sqlalchemy.url",
    database_manager.engine.url.render_as_string(
        hide_password=False
    ),
)

# -------------------------------------------------------
# Offline migrations
# -------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------
# Online migrations
# -------------------------------------------------------


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = database_manager.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# -------------------------------------------------------
# Entry point
# -------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()