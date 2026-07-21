"""Tests for PortfolioAnalyticsService."""

from models.portfolio_analytics import PortfolioAnalytics
from services.portfolio_analytics_service import PortfolioAnalyticsService


class FakePosition:
    def __init__(
        self,
        invested_amount: float,
        current_value: float,
    ) -> None:
        self.invested_amount = invested_amount
        self.current_value = current_value


class FakePositionService:
    def __init__(self, positions):
        self._positions = positions

    def get_positions(self, *, portfolio_id: int):
        return self._positions


def test_empty_portfolio() -> None:
    service = PortfolioAnalyticsService(
        position_service=FakePositionService([])
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert isinstance(
        analytics,
        PortfolioAnalytics,
    )

    assert analytics.invested_amount == 0.0
    assert analytics.current_value == 0.0
    assert analytics.number_of_positions == 0


def test_multiple_positions() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=1200,
        ),
        FakePosition(
            invested_amount=2000,
            current_value=2100,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.invested_amount == 3000
    assert analytics.current_value == 3300
    assert analytics.unrealized_gain == 300
    assert analytics.number_of_positions == 2

def test_single_position_has_full_concentration() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=1500,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 100.0
    assert analytics.diversification_score == 0.0


def test_two_equal_positions_have_lower_concentration() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 50.0
    assert analytics.diversification_score == 50.0


def test_concentration_uses_current_value_weights() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=3000,
        ),
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 75.0
    assert analytics.diversification_score == 25.0

def test_zero_current_value_produces_zero_scores() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=0,
        ),
        FakePosition(
            invested_amount=500,
            current_value=0,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 0.0
    assert analytics.diversification_score == 0.0


def test_service_requests_correct_portfolio() -> None:
    class RecordingPositionService:
        def __init__(self) -> None:
            self.requested_portfolio_id = None

        def get_positions(self, *, portfolio_id: int):
            self.requested_portfolio_id = portfolio_id
            return []

    position_service = RecordingPositionService()

    service = PortfolioAnalyticsService(
        position_service=position_service
    )

    service.calculate(
        portfolio_id=42,
    )

    assert position_service.requested_portfolio_id == 42

def test_two_equal_positions_use_hhi_scores() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 50.0
    assert analytics.diversification_score == 50.0


def test_unequal_positions_use_all_position_weights() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=3000,
        ),
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 62.5
    assert analytics.diversification_score == 37.5


def test_four_equal_positions_have_high_diversification() -> None:
    positions = [
        FakePosition(1000, 1000),
        FakePosition(1000, 1000),
        FakePosition(1000, 1000),
        FakePosition(1000, 1000),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 25.0
    assert analytics.diversification_score == 75.0

def test_concentration_uses_current_value_weights() -> None:
    positions = [
        FakePosition(
            invested_amount=1000,
            current_value=3000,
        ),
        FakePosition(
            invested_amount=1000,
            current_value=1000,
        ),
    ]

    service = PortfolioAnalyticsService(
        position_service=FakePositionService(
            positions
        )
    )

    analytics = service.calculate(
        portfolio_id=1,
    )

    assert analytics.concentration_score == 62.5
    assert analytics.diversification_score == 37.5
