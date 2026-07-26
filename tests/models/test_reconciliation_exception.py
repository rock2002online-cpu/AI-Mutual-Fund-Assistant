"""Tests for reconciliation exception persistence models."""

from sqlalchemy import inspect

import models
from models.reconciliation_audit import (
    ReconciliationAuditItem,
)
from models.reconciliation_exception import (
    ReconciliationException,
)


def test_reconciliation_exception_schema() -> None:
    """Exceptions should preserve evidence, ownership, and lifecycle state."""

    assert (
        ReconciliationException.__tablename__
        == "reconciliation_exceptions"
    )

    mapper = inspect(
        ReconciliationException
    )

    assert {
        column.key
        for column in mapper.columns
    } == {
        "id",
        "audit_item_id",
        "portfolio_id",
        "fund_id",
        "exception_type",
        "status",
        "opened_at",
        "assigned_to",
        "assigned_at",
        "investigation_started_at",
        "resolved_at",
        "resolution_notes",
        "created_at",
        "updated_at",
    }


def test_reconciliation_exception_is_publicly_exported() -> None:
    """The ORM registry should expose reconciliation exceptions."""

    assert (
        models.ReconciliationException
        is ReconciliationException
    )


def test_reconciliation_exception_references_audit_item() -> None:
    """An exception should retain access to its audit evidence."""

    mapper = inspect(
        ReconciliationException
    )

    relationship = mapper.relationships[
        "audit_item"
    ]

    assert (
        relationship.mapper.class_
        is ReconciliationAuditItem
    )

    assert {
        column.key
        for column in relationship.local_columns
    } == {
        "audit_item_id",
    }