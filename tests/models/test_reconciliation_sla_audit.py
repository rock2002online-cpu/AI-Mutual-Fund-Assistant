"""Tests for the reconciliation SLA audit model."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    inspect,
)

from models.reconciliation_sla_audit import (
    ReconciliationSLAAudit,
)


def test_reconciliation_sla_audit_has_required_columns(
) -> None:
    """An SLA audit should preserve monitoring and escalation totals."""

    mapper = inspect(
        ReconciliationSLAAudit
    )

    assert ReconciliationSLAAudit.__tablename__ == (
        "reconciliation_sla_audits"
    )
    assert set(mapper.columns.keys()) >= {
        "id",
        "portfolio_id",
        "monitored_at",
        "assignment_breach_count",
        "investigation_breach_count",
        "resolution_breach_count",
        "escalated_count",
        "created_at",
        "updated_at",
    }


def test_reconciliation_sla_audit_required_columns_are_not_nullable(
) -> None:
    """Every SLA audit should contain a complete monitoring summary."""

    mapper = inspect(
        ReconciliationSLAAudit
    )

    required_columns = {
        "portfolio_id",
        "monitored_at",
        "assignment_breach_count",
        "investigation_breach_count",
        "resolution_breach_count",
        "escalated_count",
    }

    for column_name in required_columns:
        assert (
            mapper.columns[column_name].nullable
            is False
        )


def test_reconciliation_sla_audit_portfolio_has_foreign_key(
) -> None:
    """An SLA audit should belong to an existing portfolio."""

    mapper = inspect(
        ReconciliationSLAAudit
    )
    portfolio_column = (
        mapper.columns["portfolio_id"]
    )
    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in (
            portfolio_column.foreign_keys
        )
    }

    assert foreign_keys == {
        "portfolios.id",
    }
    assert portfolio_column.index is True


def test_reconciliation_sla_audit_monitored_at_is_indexed(
) -> None:
    """Monitoring history should support efficient time-based queries."""

    mapper = inspect(
        ReconciliationSLAAudit
    )

    assert (
        mapper.columns["monitored_at"].index
        is True
    )


def test_reconciliation_sla_audit_counts_have_database_defaults(
) -> None:
    """Audit counters should default to zero at the database layer."""

    mapper = inspect(
        ReconciliationSLAAudit
    )

    counter_columns = {
        "assignment_breach_count",
        "investigation_breach_count",
        "resolution_breach_count",
        "escalated_count",
    }

    for column_name in counter_columns:
        column = mapper.columns[column_name]

        assert column.default is not None
        assert column.server_default is not None
        assert str(
            column.server_default.arg
        ) == "0"


def test_reconciliation_sla_audit_has_non_negative_count_constraints(
) -> None:
    """SLA audit counters must never contain negative values."""

    constraint_names = {
        constraint.name
        for constraint in (
            ReconciliationSLAAudit
            .__table__
            .constraints
        )
        if isinstance(
            constraint,
            CheckConstraint,
        )
    }

    assert constraint_names >= {
        "ck_reconciliation_sla_audits_assignment_count",
        "ck_reconciliation_sla_audits_investigation_count",
        "ck_reconciliation_sla_audits_resolution_count",
        "ck_reconciliation_sla_audits_escalated_count",
    }


def test_reconciliation_sla_audit_records_monitoring_summary(
) -> None:
    """An audit entity should retain all monitoring totals."""

    monitored_at = datetime(
        2026,
        7,
        27,
        18,
        0,
        tzinfo=timezone.utc,
    )

    audit = ReconciliationSLAAudit(
        id=1,
        portfolio_id=501,
        monitored_at=monitored_at,
        assignment_breach_count=2,
        investigation_breach_count=3,
        resolution_breach_count=4,
        escalated_count=5,
    )

    assert audit.id == 1
    assert audit.portfolio_id == 501
    assert audit.monitored_at == monitored_at
    assert audit.assignment_breach_count == 2
    assert audit.investigation_breach_count == 3
    assert audit.resolution_breach_count == 4
    assert audit.escalated_count == 5