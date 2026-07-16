"""
Typed models used by the reporting layer.

The reporting module does not recalculate analytics.

Instead, it aggregates existing service results into immutable
report objects that can be consumed by:

- PDF reports
- Excel exports
- Dashboard downloads
- Future REST APIs

This preserves the project's service-oriented architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.advanced_analytics_service import (
    AdvancedAnalyticsServiceResult,
)
from services.analytics.history_analytics import (
    HistoryAnalyticsResult,
)
from services.analytics.performance import (
    PortfolioPerformanceMetrics,
)


# ============================================================
# Report Metadata
# ============================================================


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """
    Metadata describing a generated report.
    """

    title: str
    version: str
    generated_at: datetime
    application_name: str = "AI Mutual Fund Assistant"


# ============================================================
# Portfolio Report
# ============================================================


@dataclass(frozen=True, slots=True)
class PortfolioReport:
    """
    Complete portfolio report.

    This object aggregates existing analytics services instead of
    duplicating calculations.
    """

    metadata: ReportMetadata

    performance: PortfolioPerformanceMetrics

    history: HistoryAnalyticsResult | None = None

    advanced_analytics: (
        AdvancedAnalyticsServiceResult | None
    ) = None

    ai_summary: dict[str, Any] = field(
        default_factory=dict
    )

    notes: tuple[str, ...] = ()

    warnings: tuple[str, ...] = ()