"""Tests for reconciliation exception orchestration."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock
import pytest
from models.reconciliation_audit import (
    ReconciliationAuditItem,
    ReconciliationAuditSnapshot,
)
from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)
from services.reconciliation_exception_service import (
    ReconciliationExceptionService,
)
from models.reconciliation_exception import (
    ReconciliationException,
)
from repositories.reconciliation_exception_assignment_repository import (
    ReconciliationExceptionAssignmentRepository,
)

def test_open_for_snapshot_creates_unit_mismatch_exception() -> None:
    """A unit mismatch should create an actionable exception."""

    opened_at = datetime(
        2026,
        7,
        25,
        10,
        0,
        tzinfo=timezone.utc,
    )
    audit_item = ReconciliationAuditItem(
        id=20,
        snapshot_id=10,
        fund_id=30,
        fund_name="Exception Equity Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("95.000000"),
        unit_variance=Decimal("5.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("950.00"),
        cost_basis_variance=Decimal("50.00"),
        status="unit_mismatch",
    )
    snapshot = ReconciliationAuditSnapshot(
        id=10,
        portfolio_id=40,
        recorded_at=opened_at,
        is_reconciled=False,
        total_count=1,
        matched_count=0,
        unit_mismatch_count=1,
        missing_position_count=0,
        missing_tax_lot_count=0,
        cost_basis_variance_count=0,
        items=[
            audit_item,
        ],
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_audit_item_id.return_value = None
    repository.add.side_effect = (
        lambda exception: exception
    )

    service = ReconciliationExceptionService(
        repository=repository,
    )

    created = service.open_for_snapshot(
        snapshot=snapshot,
        opened_at=opened_at,
    )

    assert len(created) == 1

    exception = created[0]

    assert exception.audit_item_id == audit_item.id
    assert exception.portfolio_id == snapshot.portfolio_id
    assert exception.fund_id == audit_item.fund_id
    assert exception.exception_type == "unit_mismatch"
    assert exception.status == "open"
    assert exception.opened_at == opened_at
    assert exception.investigation_started_at is None
    assert exception.resolved_at is None
    assert exception.resolution_notes is None

    repository.get_by_audit_item_id.assert_called_once_with(
        audit_item.id
    )
    repository.add.assert_called_once_with(
        exception
    )
@pytest.mark.parametrize(
    "item_status",
    [
        "missing_position",
        "missing_tax_lots",
    ],
)
def test_open_for_snapshot_creates_structural_exception(
    item_status: str,
) -> None:
    """Missing position or tax-lot evidence should be actionable."""

    opened_at = datetime(
        2026,
        7,
        25,
        11,
        0,
        tzinfo=timezone.utc,
    )
    audit_item = ReconciliationAuditItem(
        id=21,
        snapshot_id=11,
        fund_id=31,
        fund_name="Structural Exception Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("0.000000"),
        unit_variance=Decimal("100.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("0.00"),
        cost_basis_variance=Decimal("1000.00"),
        status=item_status,
    )
    snapshot = ReconciliationAuditSnapshot(
        id=11,
        portfolio_id=41,
        recorded_at=opened_at,
        is_reconciled=False,
        total_count=1,
        matched_count=0,
        unit_mismatch_count=0,
        missing_position_count=(
            1
            if item_status == "missing_position"
            else 0
        ),
        missing_tax_lot_count=(
            1
            if item_status == "missing_tax_lots"
            else 0
        ),
        cost_basis_variance_count=0,
        items=[
            audit_item,
        ],
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_audit_item_id.return_value = None
    repository.add.side_effect = (
        lambda exception: exception
    )

    service = ReconciliationExceptionService(
        repository=repository,
    )

    created = service.open_for_snapshot(
        snapshot=snapshot,
        opened_at=opened_at,
    )

    assert len(created) == 1
    assert created[0].exception_type == item_status
    assert created[0].audit_item_id == audit_item.id
    assert created[0].status == "open"

    repository.add.assert_called_once_with(
        created[0]
    )
def test_open_for_snapshot_ignores_cost_basis_only_variance() -> None:
    """Matched units with cost-basis variance should remain informational."""

    opened_at = datetime(
        2026,
        7,
        25,
        12,
        0,
        tzinfo=timezone.utc,
    )
    audit_item = ReconciliationAuditItem(
        id=22,
        snapshot_id=12,
        fund_id=32,
        fund_name="Cost Basis Information Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("100.000000"),
        unit_variance=Decimal("0.000000"),
        position_cost_basis=Decimal("1100.00"),
        transaction_cost_basis=Decimal("1000.00"),
        cost_basis_variance=Decimal("100.00"),
        status="matched",
    )
    snapshot = ReconciliationAuditSnapshot(
        id=12,
        portfolio_id=42,
        recorded_at=opened_at,
        is_reconciled=True,
        total_count=1,
        matched_count=1,
        unit_mismatch_count=0,
        missing_position_count=0,
        missing_tax_lot_count=0,
        cost_basis_variance_count=1,
        items=[
            audit_item,
        ],
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
    )

    created = service.open_for_snapshot(
        snapshot=snapshot,
        opened_at=opened_at,
    )

    assert created == []

    repository.get_by_audit_item_id.assert_not_called()
    repository.add.assert_not_called()
def test_open_for_snapshot_does_not_duplicate_exception() -> None:
    """Existing audit evidence should not create another exception."""

    opened_at = datetime(
        2026,
        7,
        25,
        13,
        0,
        tzinfo=timezone.utc,
    )
    audit_item = ReconciliationAuditItem(
        id=23,
        snapshot_id=13,
        fund_id=33,
        fund_name="Idempotent Exception Fund",
        position_units=Decimal("100.000000"),
        transaction_units=Decimal("95.000000"),
        unit_variance=Decimal("5.000000"),
        position_cost_basis=Decimal("1000.00"),
        transaction_cost_basis=Decimal("950.00"),
        cost_basis_variance=Decimal("50.00"),
        status="unit_mismatch",
    )
    snapshot = ReconciliationAuditSnapshot(
        id=13,
        portfolio_id=43,
        recorded_at=opened_at,
        is_reconciled=False,
        total_count=1,
        matched_count=0,
        unit_mismatch_count=1,
        missing_position_count=0,
        missing_tax_lot_count=0,
        cost_basis_variance_count=0,
        items=[
            audit_item,
        ],
    )
    existing = Mock(
        spec=ReconciliationException,
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_audit_item_id.return_value = (
        existing
    )

    service = ReconciliationExceptionService(
        repository=repository,
    )

    created = service.open_for_snapshot(
        snapshot=snapshot,
        opened_at=opened_at,
    )

    assert created == []

    repository.get_by_audit_item_id.assert_called_once_with(
        audit_item.id
    )
    repository.add.assert_not_called()
def test_start_investigation_transitions_open_exception() -> None:
    """An open exception should transition to investigating."""

    started_at = datetime(
        2026,
        7,
        25,
        14,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=50,
        audit_item_id=23,
        portfolio_id=43,
        fund_id=33,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception
    repository.update.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    updated = service.start_investigation(
        exception_id=exception.id,
        started_at=started_at,
    )

    assert updated is exception
    assert exception.status == "investigating"
    assert (
        exception.investigation_started_at
        == started_at
    )
    assert exception.resolved_at is None
    assert exception.resolution_notes is None

    repository.get_by_id.assert_called_once_with(
        exception.id
    )
    repository.update.assert_called_once_with(
        exception
    )
def test_start_investigation_rejects_resolved_exception() -> None:
    """A resolved exception must not return to investigating."""

    exception = ReconciliationException(
        id=51,
        audit_item_id=24,
        portfolio_id=44,
        fund_id=34,
        exception_type="unit_mismatch",
        status="resolved",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        investigation_started_at=datetime(
            2026,
            7,
            25,
            14,
            0,
            tzinfo=timezone.utc,
        ),
        resolved_at=datetime(
            2026,
            7,
            25,
            15,
            0,
            tzinfo=timezone.utc,
        ),
        resolution_notes="Unit balance was corrected.",
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match=(
            "only open exceptions can be "
            "moved to investigating"
        ),
    ):
        service.start_investigation(
            exception_id=exception.id,
            started_at=datetime(
                2026,
                7,
                25,
                16,
                0,
                tzinfo=timezone.utc,
            ),
        )

    assert exception.status == "resolved"
    repository.update.assert_not_called()
def test_resolve_transitions_investigating_exception() -> None:
    """An investigating exception should transition to resolved."""

    resolved_at = datetime(
        2026,
        7,
        25,
        17,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=52,
        audit_item_id=25,
        portfolio_id=45,
        fund_id=35,
        exception_type="missing_position",
        status="investigating",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        investigation_started_at=datetime(
            2026,
            7,
            25,
            14,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception
    repository.update.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    updated = service.resolve(
        exception_id=exception.id,
        resolved_at=resolved_at,
        resolution_notes=(
            "The missing position was rebuilt "
            "from authoritative transaction units."
        ),
    )

    assert updated is exception
    assert exception.status == "resolved"
    assert exception.resolved_at == resolved_at
    assert exception.resolution_notes == (
        "The missing position was rebuilt "
        "from authoritative transaction units."
    )

    repository.get_by_id.assert_called_once_with(
        exception.id
    )
    repository.update.assert_called_once_with(
        exception
    )
def test_resolve_rejects_open_exception() -> None:
    """An open exception must be investigated before resolution."""

    exception = ReconciliationException(
        id=53,
        audit_item_id=26,
        portfolio_id=46,
        fund_id=36,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match=(
            "only investigating exceptions "
            "can be resolved"
        ),
    ):
        service.resolve(
            exception_id=exception.id,
            resolved_at=datetime(
                2026,
                7,
                25,
                17,
                0,
                tzinfo=timezone.utc,
            ),
            resolution_notes=(
                "Attempted premature resolution."
            ),
        )

    assert exception.status == "open"
    assert exception.resolved_at is None
    assert exception.resolution_notes is None
    repository.update.assert_not_called()
@pytest.mark.parametrize(
    "resolution_notes",
    [
        "",
        "   ",
    ],
)
def test_resolve_requires_resolution_notes(
    resolution_notes: str,
) -> None:
    """Resolution should require meaningful explanatory notes."""

    exception = ReconciliationException(
        id=54,
        audit_item_id=27,
        portfolio_id=47,
        fund_id=37,
        exception_type="unit_mismatch",
        status="investigating",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        investigation_started_at=datetime(
            2026,
            7,
            25,
            14,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match="resolution_notes cannot be empty",
    ):
        service.resolve(
            exception_id=exception.id,
            resolved_at=datetime(
                2026,
                7,
                25,
                17,
                0,
                tzinfo=timezone.utc,
            ),
            resolution_notes=resolution_notes,
        )

    assert exception.status == "investigating"
    assert exception.resolved_at is None
    assert exception.resolution_notes is None
    repository.update.assert_not_called()
def test_assign_sets_owner_on_open_exception() -> None:
    """An open exception should be assignable to an operational owner."""

    assigned_at = datetime(
        2026,
        7,
        25,
        18,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=55,
        audit_item_id=28,
        portfolio_id=48,
        fund_id=38,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception
    repository.update.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    updated = service.assign(
        exception_id=exception.id,
        assigned_to="operations-team",
        assigned_at=assigned_at,
    )

    assert updated is exception
    assert exception.status == "open"
    assert exception.assigned_to == "operations-team"
    assert exception.assigned_at == assigned_at

    repository.get_by_id.assert_called_once_with(
        exception.id
    )
    repository.update.assert_called_once_with(
        exception
    )
@pytest.mark.parametrize(
    "assigned_to",
    [
        "",
        "   ",
    ],
)
def test_assign_requires_operational_owner(
    assigned_to: str,
) -> None:
    """Assignment should require a meaningful owner."""

    exception = ReconciliationException(
        id=56,
        audit_item_id=29,
        portfolio_id=49,
        fund_id=39,
        exception_type="missing_tax_lots",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match="assigned_to cannot be empty",
    ):
        service.assign(
            exception_id=exception.id,
            assigned_to=assigned_to,
            assigned_at=datetime(
                2026,
                7,
                25,
                18,
                30,
                tzinfo=timezone.utc,
            ),
        )

    assert exception.assigned_to is None
    assert exception.assigned_at is None
    repository.update.assert_not_called()
def test_assign_rejects_resolved_exception() -> None:
    """A resolved exception must not receive a new assignment."""

    exception = ReconciliationException(
        id=57,
        audit_item_id=30,
        portfolio_id=50,
        fund_id=40,
        exception_type="unit_mismatch",
        status="resolved",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        investigation_started_at=datetime(
            2026,
            7,
            25,
            14,
            0,
            tzinfo=timezone.utc,
        ),
        resolved_at=datetime(
            2026,
            7,
            25,
            17,
            0,
            tzinfo=timezone.utc,
        ),
        resolution_notes=(
            "The unit discrepancy was corrected."
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match="resolved exceptions cannot be assigned",
    ):
        service.assign(
            exception_id=exception.id,
            assigned_to="operations-team",
            assigned_at=datetime(
                2026,
                7,
                25,
                18,
                45,
                tzinfo=timezone.utc,
            ),
        )

    assert exception.assigned_to is None
    assert exception.assigned_at is None
    repository.update.assert_not_called()
def test_assign_rejects_already_assigned_exception() -> None:
    """Initial assignment must not silently replace an owner."""

    original_assigned_at = datetime(
        2026,
        7,
        25,
        18,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=58,
        audit_item_id=31,
        portfolio_id=51,
        fund_id=41,
        exception_type="missing_position",
        status="open",
        opened_at=datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        assigned_to="operations-team",
        assigned_at=original_assigned_at,
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    service = ReconciliationExceptionService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match="exception is already assigned",
    ):
        service.assign(
            exception_id=exception.id,
            assigned_to="reconciliation-manager",
            assigned_at=datetime(
                2026,
                7,
                25,
                19,
                0,
                tzinfo=timezone.utc,
            ),
        )

    assert exception.assigned_to == "operations-team"
    assert exception.assigned_at == original_assigned_at
    repository.update.assert_not_called()
def test_assign_records_immutable_assignment_history() -> None:
    """Initial ownership should create an immutable history record."""

    assigned_at = datetime(
        2026,
        7,
        26,
        11,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=59,
        audit_item_id=32,
        portfolio_id=52,
        fund_id=42,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception
    repository.update.return_value = exception

    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )
    assignment_repository.add.side_effect = (
        lambda assignment: assignment
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    updated = service.assign(
        exception_id=exception.id,
        assigned_to="operations-team",
        assigned_at=assigned_at,
    )

    assert updated is exception

    assignment_repository.add.assert_called_once()

    assignment = (
        assignment_repository.add.call_args.args[0]
    )

    assert assignment.exception_id == exception.id
    assert assignment.previous_assigned_to is None
    assert assignment.assigned_to == "operations-team"
    assert assignment.assigned_at == assigned_at
    assert assignment.reason is None
def test_reassign_changes_owner_and_records_history() -> None:
    """Controlled reassignment should preserve the ownership change."""

    original_assigned_at = datetime(
        2026,
        7,
        26,
        10,
        0,
        tzinfo=timezone.utc,
    )
    reassigned_at = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=60,
        audit_item_id=33,
        portfolio_id=53,
        fund_id=43,
        exception_type="missing_position",
        status="open",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        assigned_to="operations-team",
        assigned_at=original_assigned_at,
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception
    repository.update.return_value = exception

    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )
    assignment_repository.add.side_effect = (
        lambda assignment: assignment
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    updated = service.reassign(
        exception_id=exception.id,
        assigned_to="reconciliation-manager",
        reassigned_at=reassigned_at,
        reason="Escalated for supervisory review.",
    )

    assert updated is exception
    assert (
        exception.assigned_to
        == "reconciliation-manager"
    )
    assert exception.assigned_at == reassigned_at

    repository.update.assert_called_once_with(
        exception
    )
    assignment_repository.add.assert_called_once()

    assignment = (
        assignment_repository.add.call_args.args[0]
    )

    assert assignment.exception_id == exception.id
    assert (
        assignment.previous_assigned_to
        == "operations-team"
    )
    assert (
        assignment.assigned_to
        == "reconciliation-manager"
    )
    assert assignment.assigned_at == reassigned_at
    assert assignment.reason == (
        "Escalated for supervisory review."
    )
@pytest.mark.parametrize(
    "reason",
    [
        "",
        "   ",
    ],
)
def test_reassign_requires_reason(
    reason: str,
) -> None:
    """Reassignment should require an audit explanation."""

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    with pytest.raises(
        ValueError,
        match="reason cannot be empty",
    ):
        service.reassign(
            exception_id=60,
            assigned_to="reconciliation-manager",
            reassigned_at=datetime(
                2026,
                7,
                26,
                12,
                30,
                tzinfo=timezone.utc,
            ),
            reason=reason,
        )

    repository.get_by_id.assert_not_called()
    repository.update.assert_not_called()
    assignment_repository.add.assert_not_called()
@pytest.mark.parametrize(
    "assigned_to",
    [
        "",
        "   ",
    ],
)
def test_reassign_requires_operational_owner(
    assigned_to: str,
) -> None:
    """Reassignment should require a meaningful destination owner."""

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    with pytest.raises(
        ValueError,
        match="assigned_to cannot be empty",
    ):
        service.reassign(
            exception_id=60,
            assigned_to=assigned_to,
            reassigned_at=datetime(
                2026,
                7,
                26,
                13,
                0,
                tzinfo=timezone.utc,
            ),
            reason="Transferred to the specialist team.",
        )

    repository.get_by_id.assert_not_called()
    repository.update.assert_not_called()
    assignment_repository.add.assert_not_called()
def test_reassign_rejects_unassigned_exception() -> None:
    """An unassigned exception must use initial assignment."""

    exception = ReconciliationException(
        id=61,
        audit_item_id=34,
        portfolio_id=54,
        fund_id=44,
        exception_type="unit_mismatch",
        status="open",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    with pytest.raises(
        ValueError,
        match="exception is not currently assigned",
    ):
        service.reassign(
            exception_id=exception.id,
            assigned_to="reconciliation-manager",
            reassigned_at=datetime(
                2026,
                7,
                26,
                13,
                30,
                tzinfo=timezone.utc,
            ),
            reason="Transferred for specialist review.",
        )

    assert exception.assigned_to is None
    assert exception.assigned_at is None
    repository.update.assert_not_called()
    assignment_repository.add.assert_not_called()
def test_reassign_rejects_same_owner() -> None:
    """Reassignment must transfer ownership to a different owner."""

    original_assigned_at = datetime(
        2026,
        7,
        26,
        10,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=62,
        audit_item_id=35,
        portfolio_id=55,
        fund_id=45,
        exception_type="missing_tax_lots",
        status="investigating",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        assigned_to="operations-team",
        assigned_at=original_assigned_at,
        investigation_started_at=datetime(
            2026,
            7,
            26,
            10,
            30,
            tzinfo=timezone.utc,
        ),
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    with pytest.raises(
        ValueError,
        match="new owner must be different",
    ):
        service.reassign(
            exception_id=exception.id,
            assigned_to="operations-team",
            reassigned_at=datetime(
                2026,
                7,
                26,
                14,
                0,
                tzinfo=timezone.utc,
            ),
            reason="Attempted duplicate ownership transfer.",
        )

    assert exception.assigned_to == "operations-team"
    assert exception.assigned_at == original_assigned_at
    repository.update.assert_not_called()
    assignment_repository.add.assert_not_called()
def test_reassign_rejects_resolved_exception() -> None:
    """A resolved exception must not be reassigned."""

    original_assigned_at = datetime(
        2026,
        7,
        26,
        10,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=63,
        audit_item_id=36,
        portfolio_id=56,
        fund_id=46,
        exception_type="unit_mismatch",
        status="resolved",
        opened_at=datetime(
            2026,
            7,
            26,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        assigned_to="operations-team",
        assigned_at=original_assigned_at,
        investigation_started_at=datetime(
            2026,
            7,
            26,
            10,
            30,
            tzinfo=timezone.utc,
        ),
        resolved_at=datetime(
            2026,
            7,
            26,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        resolution_notes="The unit discrepancy was corrected.",
    )

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_by_id.return_value = exception

    assignment_repository = Mock(
        spec=ReconciliationExceptionAssignmentRepository,
    )

    service = ReconciliationExceptionService(
        repository=repository,
        assignment_repository=assignment_repository,
    )

    with pytest.raises(
        ValueError,
        match="resolved exceptions cannot be reassigned",
    ):
        service.reassign(
            exception_id=exception.id,
            assigned_to="reconciliation-manager",
            reassigned_at=datetime(
                2026,
                7,
                26,
                14,
                30,
                tzinfo=timezone.utc,
            ),
            reason="Attempted transfer after resolution.",
        )

    assert exception.assigned_to == "operations-team"
    assert exception.assigned_at == original_assigned_at
    repository.update.assert_not_called()
    assignment_repository.add.assert_not_called()