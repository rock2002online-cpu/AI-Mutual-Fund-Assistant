"""
Tests for the generic SQLAlchemy BaseRepository.
"""

from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from repositories.base_repository import BaseRepository
from repositories.exceptions import (
    RepositoryNotFoundError,
    RepositoryValidationError,
)


class RepositoryBase(DeclarativeBase):
    """Declarative base used only by repository tests."""


class ExampleEntity(RepositoryBase):
    """Simple ORM model used to test generic repository behavior."""

    __tablename__ = "repository_test_entities"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite session."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
    )

    RepositoryBase.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )

    database_session = session_factory()

    try:
        yield database_session
    finally:
        database_session.close()
        RepositoryBase.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def repository(
    session: Session,
) -> BaseRepository[ExampleEntity]:
    """Provide a repository for the example entity."""

    return BaseRepository(
        session=session,
        model=ExampleEntity,
    )


def test_repository_requires_session() -> None:
    """A repository cannot be created without a session."""

    with pytest.raises(
        RepositoryValidationError,
        match="session cannot be None",
    ):
        BaseRepository(
            session=None,  # type: ignore[arg-type]
            model=ExampleEntity,
        )


def test_repository_requires_model(
    session: Session,
) -> None:
    """A repository cannot be created without an ORM model."""

    with pytest.raises(
        RepositoryValidationError,
        match="model cannot be None",
    ):
        BaseRepository(
            session=session,
            model=None,  # type: ignore[arg-type]
        )


def test_repository_exposes_session_and_model(
    session: Session,
    repository: BaseRepository[ExampleEntity],
) -> None:
    """The configured session and model should be exposed."""

    assert repository.session is session
    assert repository.model is ExampleEntity


def test_add_persists_entity(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Adding an entity should assign its generated primary key."""

    entity = ExampleEntity(name="Example")

    result = repository.add(entity)

    assert result is entity
    assert result.id is not None
    assert result.name == "Example"


def test_add_rejects_none(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Adding None should raise a validation error."""

    with pytest.raises(
        RepositoryValidationError,
        match="entity cannot be None",
    ):
        repository.add(None)  # type: ignore[arg-type]


def test_get_by_id_returns_entity(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """An existing entity should be retrievable by primary key."""

    entity = repository.add(
        ExampleEntity(name="Existing"),
    )

    result = repository.get_by_id(entity.id)

    assert result is entity
    assert result.name == "Existing"


def test_get_by_id_raises_when_missing(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """A missing primary key should raise RepositoryNotFoundError."""

    with pytest.raises(
        RepositoryNotFoundError,
        match=r"ExampleEntity with id=999 was not found",
    ):
        repository.get_by_id(999)


def test_get_all_returns_all_entities(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """All persisted entities should be returned."""

    repository.add(ExampleEntity(name="First"))
    repository.add(ExampleEntity(name="Second"))

    result = repository.get_all()

    assert len(result) == 2
    assert [entity.name for entity in result] == [
        "First",
        "Second",
    ]


def test_get_all_returns_empty_list(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """An empty table should return an empty list."""

    assert repository.get_all() == []


def test_count_returns_number_of_entities(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Count should report the total persisted rows."""

    assert repository.count() == 0

    repository.add(ExampleEntity(name="First"))
    repository.add(ExampleEntity(name="Second"))

    assert repository.count() == 2


def test_exists_returns_true_for_existing_entity(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Exists should return True for a stored primary key."""

    entity = repository.add(
        ExampleEntity(name="Existing"),
    )

    assert repository.exists(entity.id) is True


def test_exists_returns_false_for_missing_entity(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Exists should return False for an unknown primary key."""

    assert repository.exists(999) is False


def test_delete_removes_entity(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Deleting an entity should remove it from the database."""

    entity = repository.add(
        ExampleEntity(name="Delete me"),
    )

    entity_id = entity.id

    repository.delete(entity)

    assert repository.exists(entity_id) is False
    assert repository.count() == 0


def test_delete_rejects_none(
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Deleting None should raise a validation error."""

    with pytest.raises(
        RepositoryValidationError,
        match="entity cannot be None",
    ):
        repository.delete(None)  # type: ignore[arg-type]


def test_refresh_restores_database_state(
    session: Session,
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Refresh should reload an entity from the database."""

    entity = repository.add(
        ExampleEntity(name="Original"),
    )

    session.execute(
        ExampleEntity.__table__.update()
        .where(ExampleEntity.id == entity.id)
        .values(name="Updated in database")
    )

    repository.refresh(entity)

    assert entity.name == "Updated in database"


def test_flush_persists_pending_changes(
    session: Session,
    repository: BaseRepository[ExampleEntity],
) -> None:
    """Flush should send pending session changes to the database."""

    entity = ExampleEntity(name="Pending")

    session.add(entity)

    assert entity.id is None

    repository.flush()

    assert entity.id is not None