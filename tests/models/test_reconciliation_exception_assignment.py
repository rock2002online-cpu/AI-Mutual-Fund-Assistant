"""Tests for reconciliation exception assignment history."""

from datetime import datetime, timezone

from models.reconciliation_exception_assignment import (
    ReconciliationExceptionAssignment,
)
import models

def test_reconciliation_exception_assignment_records_ownership_change() -> None:
    """An assignment record should preserve an ownership change."""

    assigned_at = datetime(
        2026,
        7,
        26,
        10,
        0,
        tzinfo=timezone.utc,
    )

    assignment = ReconciliationExceptionAssignment(
        id=1,
        exception_id=55,
        previous_assigned_to="operations-team",
        assigned_to="reconciliation-manager",
        assigned_at=assigned_at,
        reason="Escalated for supervisory review.",
    )

    assert assignment.id == 1
    assert assignment.exception_id == 55
    assert (
        assignment.previous_assigned_to
        == "operations-team"
    )
    assert (
        assignment.assigned_to
        == "reconciliation-manager"
    )
    assert assignment.assigned_at == assigned_at
    assert assignment.reason == (
        "Escalated for supervisory review."
    )
def test_reconciliation_exception_assignment_is_publicly_exported() -> None:
    """The ORM registry should expose assignment history."""

    assert (
        models.ReconciliationExceptionAssignment
        is ReconciliationExceptionAssignment
    )