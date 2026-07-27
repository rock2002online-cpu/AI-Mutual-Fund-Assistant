"""Tests for automated reconciliation SLA monitoring."""

from datetime import datetime, timedelta, timezone

from models.reconciliation_exception import (
    ReconciliationException,
)
from services.reconciliation_sla_monitoring_service import (
    ReconciliationSLAMonitoringService,
)
from unittest.mock import Mock

from repositories.reconciliation_exception_repository import (
    ReconciliationExceptionRepository,
)
import pytest

def test_find_assignment_breaches_returns_overdue_unassigned_exception(
) -> None:
    """An overdue unassigned exception should breach its assignment SLA."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=101,
        audit_item_id=201,
        portfolio_id=301,
        fund_id=401,
        exception_type="unit_mismatch",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=3),
        assigned_to=None,
        assigned_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_assignment_breaches(
        exceptions=[exception],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
    )

    assert breached == [exception]
def test_find_assignment_breaches_excludes_exception_within_sla(
) -> None:
    """An unassigned exception within its assignment SLA is not breached."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=102,
        audit_item_id=202,
        portfolio_id=302,
        fund_id=402,
        exception_type="missing_position",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(minutes=90),
        assigned_to=None,
        assigned_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_assignment_breaches(
        exceptions=[exception],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
    )

    assert breached == []
def test_find_assignment_breaches_includes_exception_at_sla_deadline(
) -> None:
    """An unassigned exception at its SLA deadline should be breached."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    exception = ReconciliationException(
        id=103,
        audit_item_id=203,
        portfolio_id=303,
        fund_id=403,
        exception_type="missing_tax_lots",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=2),
        assigned_to=None,
        assigned_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_assignment_breaches(
        exceptions=[exception],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
    )

    assert breached == [exception]
def test_find_assignment_breaches_rejects_zero_assignment_sla(
) -> None:
    """Assignment SLA must be a positive duration."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    with pytest.raises(
        ValueError,
        match="assignment_sla must be positive",
    ):
        service.find_assignment_breaches(
            exceptions=[],
            as_of=as_of,
            assignment_sla=timedelta(0),
        )
def test_find_assignment_breaches_returns_oldest_breach_first(
) -> None:
    """Assignment breaches should be ordered from oldest to newest."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    newer_exception = ReconciliationException(
        id=104,
        audit_item_id=204,
        portfolio_id=304,
        fund_id=404,
        exception_type="unit_mismatch",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=3),
        assigned_to=None,
        assigned_at=None,
    )
    older_exception = ReconciliationException(
        id=105,
        audit_item_id=205,
        portfolio_id=305,
        fund_id=405,
        exception_type="missing_position",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=5),
        assigned_to=None,
        assigned_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_assignment_breaches(
        exceptions=[
            newer_exception,
            older_exception,
        ],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
    )

    assert breached == [
        older_exception,
        newer_exception,
    ]
def test_find_investigation_breaches_returns_overdue_assigned_exception(
) -> None:
    """An assigned exception should breach when investigation starts late."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    assigned_at = as_of - timedelta(hours=3)

    exception = ReconciliationException(
        id=106,
        audit_item_id=206,
        portfolio_id=306,
        fund_id=406,
        exception_type="unit_mismatch",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=4),
        assigned_to="operations-owner",
        assigned_at=assigned_at,
        investigation_started_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_investigation_breaches(
        exceptions=[exception],
        as_of=as_of,
        investigation_sla=timedelta(hours=2),
    )

    assert breached == [exception]
def test_find_investigation_breaches_rejects_zero_investigation_sla(
) -> None:
    """Investigation SLA must be a positive duration."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    with pytest.raises(
        ValueError,
        match="investigation_sla must be positive",
    ):
        service.find_investigation_breaches(
            exceptions=[],
            as_of=as_of,
            investigation_sla=timedelta(0),
        )
def test_find_investigation_breaches_returns_oldest_assignment_first(
) -> None:
    """Investigation breaches should be ordered by oldest assignment."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    newer_exception = ReconciliationException(
        id=107,
        audit_item_id=207,
        portfolio_id=307,
        fund_id=407,
        exception_type="unit_mismatch",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=5),
        assigned_to="newer-owner",
        assigned_at=as_of - timedelta(hours=3),
        investigation_started_at=None,
    )
    older_exception = ReconciliationException(
        id=108,
        audit_item_id=208,
        portfolio_id=308,
        fund_id=408,
        exception_type="missing_position",
        status="open",
        priority="normal",
        opened_at=as_of - timedelta(hours=7),
        assigned_to="older-owner",
        assigned_at=as_of - timedelta(hours=5),
        investigation_started_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_investigation_breaches(
        exceptions=[
            newer_exception,
            older_exception,
        ],
        as_of=as_of,
        investigation_sla=timedelta(hours=2),
    )

    assert breached == [
        older_exception,
        newer_exception,
    ]
def test_find_resolution_breaches_returns_overdue_investigation(
) -> None:
    """An investigating exception should breach when resolution is late."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    investigation_started_at = (
        as_of - timedelta(hours=5)
    )

    exception = ReconciliationException(
        id=109,
        audit_item_id=209,
        portfolio_id=309,
        fund_id=409,
        exception_type="unit_mismatch",
        status="investigating",
        priority="normal",
        opened_at=as_of - timedelta(hours=8),
        assigned_to="operations-owner",
        assigned_at=as_of - timedelta(hours=7),
        investigation_started_at=(
            investigation_started_at
        ),
        resolved_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_resolution_breaches(
        exceptions=[exception],
        as_of=as_of,
        resolution_sla=timedelta(hours=4),
    )

    assert breached == [exception]
def test_find_resolution_breaches_rejects_zero_resolution_sla(
) -> None:
    """Resolution SLA must be a positive duration."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    with pytest.raises(
        ValueError,
        match="resolution_sla must be positive",
    ):
        service.find_resolution_breaches(
            exceptions=[],
            as_of=as_of,
            resolution_sla=timedelta(0),
        )
def test_find_resolution_breaches_returns_oldest_investigation_first(
) -> None:
    """Resolution breaches should be ordered by investigation start time."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    newer_exception = ReconciliationException(
        id=110,
        audit_item_id=210,
        portfolio_id=310,
        fund_id=410,
        exception_type="unit_mismatch",
        status="investigating",
        priority="normal",
        opened_at=as_of - timedelta(hours=8),
        assigned_to="newer-owner",
        assigned_at=as_of - timedelta(hours=7),
        investigation_started_at=(
            as_of - timedelta(hours=5)
        ),
        resolved_at=None,
    )
    older_exception = ReconciliationException(
        id=111,
        audit_item_id=211,
        portfolio_id=311,
        fund_id=411,
        exception_type="missing_position",
        status="investigating",
        priority="normal",
        opened_at=as_of - timedelta(hours=11),
        assigned_to="older-owner",
        assigned_at=as_of - timedelta(hours=10),
        investigation_started_at=(
            as_of - timedelta(hours=8)
        ),
        resolved_at=None,
    )

    service = ReconciliationSLAMonitoringService()

    breached = service.find_resolution_breaches(
        exceptions=[
            newer_exception,
            older_exception,
        ],
        as_of=as_of,
        resolution_sla=timedelta(hours=4),
    )

    assert breached == [
        older_exception,
        newer_exception,
    ]
def test_monitor_returns_empty_result_when_no_exceptions_exist(
) -> None:
    """A monitoring run should return empty breach collections."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    result = service.monitor(
        exceptions=[],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.assignment_breaches == []
    assert result.investigation_breaches == []
    assert result.resolution_breaches == []
    assert result.as_of == as_of
def test_monitoring_result_reports_total_breach_count(
) -> None:
    """The monitoring result should expose its total breach count."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    result = service.monitor(
        exceptions=[],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.total_breaches == 0
def test_monitoring_result_reports_when_no_breaches_exist(
) -> None:
    """An empty monitoring result should report no SLA breaches."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    service = ReconciliationSLAMonitoringService()

    result = service.monitor(
        exceptions=[],
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.has_breaches is False
def test_monitor_portfolio_loads_active_exceptions_from_repository(
) -> None:
    """Portfolio monitoring should load active exceptions automatically."""

    as_of = datetime(
        2026,
        7,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )
    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    repository.get_active_for_portfolio.return_value = []

    service = ReconciliationSLAMonitoringService(
        repository=repository,
    )

    result = service.monitor_portfolio(
        portfolio_id=501,
        as_of=as_of,
        assignment_sla=timedelta(hours=2),
        investigation_sla=timedelta(hours=4),
        resolution_sla=timedelta(hours=24),
    )

    assert result.total_breaches == 0
    repository.get_active_for_portfolio.assert_called_once_with(
        501
    )
def test_monitor_portfolio_rejects_non_positive_portfolio_id(
) -> None:
    """Portfolio monitoring requires a positive portfolio identifier."""

    repository = Mock(
        spec=ReconciliationExceptionRepository,
    )
    service = ReconciliationSLAMonitoringService(
        repository=repository,
    )

    with pytest.raises(
        ValueError,
        match="portfolio_id must be positive",
    ):
        service.monitor_portfolio(
            portfolio_id=0,
            as_of=datetime(
                2026,
                7,
                26,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            assignment_sla=timedelta(hours=2),
            investigation_sla=timedelta(hours=4),
            resolution_sla=timedelta(hours=24),
        )

    repository.get_active_for_portfolio.assert_not_called()