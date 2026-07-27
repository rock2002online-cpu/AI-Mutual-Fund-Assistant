"""Notification interface for reconciliation SLA job outcomes."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from services.reconciliation_sla_automation_service import (
    ReconciliationSLAAutomationResult,
)


class ReconciliationSLANotifier(Protocol):
    """Deliver reconciliation SLA escalation notifications."""

    def notify_escalations(
        self,
        *,
        portfolio_id: int,
        scheduled_at: datetime,
        automation_result: (
            ReconciliationSLAAutomationResult
        ),
        attempts_used: int,
    ) -> None:
        """Notify recipients about successful SLA escalations."""

    def notify_failure(
        self,
        *,
        portfolio_id: int,
        scheduled_at: datetime,
        error: Exception,
        attempt_number: int,
        max_attempts: int,
    ) -> None:
        """Notify recipients about a failed scheduled SLA run."""


__all__ = [
    "ReconciliationSLANotifier",
]
