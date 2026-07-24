"""Tests for reconciliation audit persistence models."""

from sqlalchemy import inspect

from models.reconciliation_audit import (
    ReconciliationAuditSnapshot,
)
from models.reconciliation_audit import (
    ReconciliationAuditItem,
    ReconciliationAuditSnapshot,
)
import models

def test_reconciliation_audit_snapshot_schema() -> None:
    """Audit snapshots should preserve reconciliation summary totals."""

    assert (
        ReconciliationAuditSnapshot.__tablename__
        == "reconciliation_audit_snapshots"
    )

    mapper = inspect(
        ReconciliationAuditSnapshot
    )

    assert {
        column.key
        for column in mapper.columns
    } == {
        "id",
        "portfolio_id",
        "recorded_at",
        "is_reconciled",
        "total_count",
        "matched_count",
        "unit_mismatch_count",
        "missing_position_count",
        "missing_tax_lot_count",
        "cost_basis_variance_count",
        "created_at",
        "updated_at",
    }
def test_reconciliation_audit_item_schema() -> None:
    """Audit items should preserve fund-level reconciliation evidence."""

    assert (
        ReconciliationAuditItem.__tablename__
        == "reconciliation_audit_items"
    )

    mapper = inspect(
        ReconciliationAuditItem
    )

    assert {
        column.key
        for column in mapper.columns
    } == {
        "id",
        "snapshot_id",
        "fund_id",
        "fund_name",
        "position_units",
        "transaction_units",
        "unit_variance",
        "position_cost_basis",
        "transaction_cost_basis",
        "cost_basis_variance",
        "status",
        "created_at",
        "updated_at",
    }
def test_reconciliation_audit_snapshot_owns_items() -> None:
    """Deleting a snapshot should cascade to its audit evidence."""

    snapshot_mapper = inspect(
        ReconciliationAuditSnapshot
    )
    item_mapper = inspect(
        ReconciliationAuditItem
    )

    snapshot_relationship = (
        snapshot_mapper.relationships["items"]
    )
    item_relationship = (
        item_mapper.relationships["snapshot"]
    )

    assert (
        snapshot_relationship.back_populates
        == "snapshot"
    )
    assert (
        item_relationship.back_populates
        == "items"
    )
    assert "delete-orphan" in (
        snapshot_relationship.cascade
    )
def test_reconciliation_audit_models_are_publicly_exported() -> None:
    """The ORM model registry should expose both audit entities."""

    assert (
        models.ReconciliationAuditSnapshot
        is ReconciliationAuditSnapshot
    )
    assert (
        models.ReconciliationAuditItem
        is ReconciliationAuditItem
    )
