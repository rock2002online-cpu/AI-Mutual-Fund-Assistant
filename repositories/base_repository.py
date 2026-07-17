"""
Generic SQLAlchemy repository.

This repository provides reusable CRUD operations for all ORM models.

Repositories should not commit transactions directly. Transaction boundaries
are managed by the Unit of Work (implemented later).
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from repositories.exceptions import (
    RepositoryIntegrityError,
    RepositoryNotFoundError,
    RepositoryOperationError,
    RepositoryValidationError,
)

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Generic repository for SQLAlchemy ORM models."""

    def __init__(
        self,
        session: Session,
        model: type[ModelType],
    ) -> None:
        if session is None:
            raise RepositoryValidationError(
                "session cannot be None."
            )

        if model is None:
            raise RepositoryValidationError(
                "model cannot be None."
            )

        self._session = session
        self._model = model

    @property
    def session(self) -> Session:
        return self._session

    @property
    def model(self) -> type[ModelType]:
        return self._model

    def add(self, entity: ModelType) -> ModelType:
        """Add an entity to the current session."""

        if entity is None:
            raise RepositoryValidationError(
                "entity cannot be None."
            )

        try:
            self.session.add(entity)
            self.session.flush()
            self.session.refresh(entity)
            return entity

        except IntegrityError as exc:
            raise RepositoryIntegrityError(str(exc)) from exc

        except SQLAlchemyError as exc:
            raise RepositoryOperationError(str(exc)) from exc

    def get_by_id(self, entity_id: Any) -> ModelType:
        """Retrieve an entity by primary key."""

        entity = self.session.get(
            self.model,
            entity_id,
        )

        if entity is None:
            raise RepositoryNotFoundError(
                f"{self.model.__name__} "
                f"with id={entity_id} was not found."
            )

        return entity

    def get_all(self) -> list[ModelType]:
        """Return all entities."""

        return (
            self.session.query(self.model)
            .all()
        )

    def count(self) -> int:
        """Return total number of rows."""

        return (
            self.session.query(self.model)
            .count()
        )

    def exists(self, entity_id: Any) -> bool:
        """Return True if the entity exists."""

        return (
            self.session.get(
                self.model,
                entity_id,
            )
            is not None
        )

    def delete(self, entity: ModelType) -> None:
        """Delete an entity."""

        if entity is None:
            raise RepositoryValidationError(
                "entity cannot be None."
            )

        try:
            self.session.delete(entity)
            self.session.flush()

        except SQLAlchemyError as exc:
            raise RepositoryOperationError(
                str(exc)
            ) from exc

    def refresh(self, entity: ModelType) -> None:
        """Refresh an entity."""

        self.session.refresh(entity)

    def flush(self) -> None:
        """Flush pending SQL statements."""

        self.session.flush()

    def get_or_none(self, entity_id: Any) -> ModelType | None:
        """Return an entity by primary key or None."""

        return self.session.get(
            self.model,
            entity_id,
        )

    def first(self) -> ModelType | None:
        """Return the first entity or None."""

        return (
            self.session.query(self.model)
            .first()
        )

    def find_by(self, **filters: Any) -> list[ModelType]:
        """Return entities matching the supplied filters."""

        return (
            self.session.query(self.model)
            .filter_by(**filters)
            .all()
        )

    def list(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ModelType]:
        """Return entities using optional pagination."""

        query = (
            self.session.query(self.model)
            .offset(offset)
        )

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    def update(
        self,
        entity: ModelType,
    ) -> ModelType:
        """Flush updates for an existing entity."""

        if entity is None:
            raise RepositoryValidationError(
                "entity cannot be None."
            )

        try:
            self.session.flush()
            self.session.refresh(entity)
            return entity

        except IntegrityError as exc:
            raise RepositoryIntegrityError(str(exc)) from exc

        except SQLAlchemyError as exc:
            raise RepositoryOperationError(str(exc)) from exc