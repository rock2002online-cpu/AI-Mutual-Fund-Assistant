"""
Tests for UnitOfWork.
"""

from __future__ import annotations

import pytest

from repositories.unit_of_work import UnitOfWork


def test_unit_of_work_creates_session() -> None:
    """Entering the context should create a session."""

    with UnitOfWork() as uow:
        assert uow.session is not None


def test_unit_of_work_creates_repositories() -> None:
    """Repositories should be available inside the context."""

    with UnitOfWork() as uow:
        assert uow.funds is not None
        assert uow.portfolios is not None


def test_commit_without_context_raises() -> None:
    """Calling commit before entering should fail."""

    uow = UnitOfWork()

    with pytest.raises(RuntimeError):
        uow.commit()


def test_rollback_without_context_raises() -> None:
    """Calling rollback before entering should fail."""

    uow = UnitOfWork()

    with pytest.raises(RuntimeError):
        uow.rollback()