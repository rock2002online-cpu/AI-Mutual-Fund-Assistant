"""Tests for the portfolio tax-lot view orchestration."""

from unittest.mock import MagicMock, patch

from views.tax_lot_view import render_tax_lot_section


@patch(
    "views.tax_lot_view.render_tax_lot_analytics"
)
@patch(
    "views.tax_lot_view.TaxLotService"
)
@patch(
    "views.tax_lot_view.PortfolioTaxLotService"
)
@patch(
    "views.tax_lot_view.UnitOfWork"
)
def test_render_tax_lot_section_analyzes_portfolio(
    mock_unit_of_work_class,
    mock_portfolio_tax_lot_service_class,
    mock_tax_lot_service_class,
    mock_render_tax_lot_analytics,
) -> None:
    """Load portfolio transactions and render their tax lots."""

    unit_of_work = MagicMock()
    mock_unit_of_work_class.return_value.__enter__.return_value = (
        unit_of_work
    )

    tax_lot_service = (
        mock_tax_lot_service_class.return_value
    )

    analysis = MagicMock()

    portfolio_tax_lot_service = (
        mock_portfolio_tax_lot_service_class.return_value
    )
    (
        portfolio_tax_lot_service
        .analyze_portfolio
        .return_value
    ) = analysis

    render_tax_lot_section(
        portfolio_id=1,
    )

    mock_portfolio_tax_lot_service_class.assert_called_once_with(
        transaction_repository=unit_of_work.transactions,
        tax_lot_service=tax_lot_service,
    )

    portfolio_tax_lot_service.analyze_portfolio.assert_called_once_with(
        portfolio_id=1,
    )

    mock_render_tax_lot_analytics.assert_called_once_with(
        analysis
    )