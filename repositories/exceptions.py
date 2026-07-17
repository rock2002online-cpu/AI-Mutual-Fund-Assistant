"""
Repository-layer exception definitions.

These exceptions provide a clean boundary between the persistence layer and
the service layer. Application services should not need to depend directly on
SQLAlchemy-specific exceptions.
"""

from __future__ import annotations


class RepositoryError(Exception):
    """Base exception for all repository-layer errors."""


class RepositoryValidationError(RepositoryError):
    """Raised when invalid input is supplied to a repository operation."""


class RepositoryNotFoundError(RepositoryError):
    """Raised when a requested database record cannot be found."""


class RepositoryConflictError(RepositoryError):
    """Raised when an operation conflicts with an existing database record."""


class RepositoryIntegrityError(RepositoryError):
    """Raised when a database integrity constraint is violated."""


class RepositoryOperationError(RepositoryError):
    """Raised when a repository operation fails unexpectedly."""