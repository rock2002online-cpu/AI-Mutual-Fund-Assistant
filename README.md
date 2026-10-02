# AI Mutual Fund Assistant (InvestGPT)

A Python mutual fund portfolio application with a Streamlit dashboard, AMFI NAV integration, portfolio analytics, downloadable reports, and database-backed transaction and reconciliation services.

## Release status

Current implemented milestone: **Version 37.0 — scheduler recovery-audit querying**. The application metadata defaults to **37.0.0** in `config/settings.py`.

This documentation reflects main commit [`97cac92`](https://github.com/rock2002online-cpu/AI-Mutual-Fund-Assistant/commit/97cac92a16daaa32b6ffd9fac51aff6079279da9), merged via [PR #15](https://github.com/rock2002online-cpu/AI-Mutual-Fund-Assistant/pull/15). That PR reports **2,664 full project tests passed**, including six new recovery-audit query tests. This is the recorded release validation, not a guarantee about every environment or live data provider.

The dashboard is implemented. Database and scheduler capabilities also exist as application services; the default dashboard still loads holdings from Excel, and launching Streamlit does not automatically start an SLA scheduler.

## Implemented capabilities

### Dashboard and portfolio workflows

- Excel holdings loading, latest AMFI NAV download with a same-day CSV cache, investment/current value, profit/loss, and return calculations.
- Streamlit pages for Portfolio, Fund Explorer, SIP Calculator, AI Advisor, QA Dashboard, Analytics, and Reports.
- Holdings summaries, allocation charts, concentration/risk indicators, and portfolio health scores.
- Transaction import preview and persistence, filterable transaction history, XIRR cash-flow eligibility, and FIFO tax-lot analysis through database-backed services.
- Rule-based portfolio insights, recommendations, and executive summaries. The current advisor does not call the OpenAI API or provide a conversational LLM assistant.

### Analytics and reporting

- XIRR, CAGR, rolling returns, volatility, drawdown, benchmark comparison, and historical valuation charts, subject to available cash flows and history.
- Risk services for Sharpe, Sortino, beta, Treynor, Information Ratio, Jensen's alpha, Calmar, Omega, VaR/CVaR, and upside/downside capture.
- AMFI historical NAV retrieval and a current-holdings backtest; this backtest values today's units over historical dates rather than reconstructing historical trades.
- Portfolio snapshot history and Nifty 50 TRI benchmark-history support.
- Excel and PDF portfolio reports, with additional Excel reporting services for tax lots and reconciliation.

### Persistence, reconciliation, and scheduling

- SQLAlchemy models, repositories, a Unit of Work, SQLite defaults, and Alembic migrations.
- Transaction-derived holdings and positions; repository-backed portfolio loading when a Unit of Work factory is supplied to `PortfolioService`.
- Portfolio reconciliation, audit records, exception ownership, alerts, SLA monitoring, escalation, automation, and notifier interfaces.
- SLA scheduler registration, polling/lifecycle controls, status lookup, pause/resume, rescheduling, and manual execution.
- Execution history, configurable retention, failure isolation, missed-run coalescing, and JSON persistence for execution history, job state, and recovery audit history.
- Restored job states remain pending until runnable job objects are supplied for recovery. Recovery reports expose recovered, missing, and pending job IDs.
- Version 37.0 adds latest recovery-report lookup and history filtering by completion outcome and job ID. An empty latest-report lookup raises a validation error; job filters match recovered, missing, or pending IDs.

Scheduler jobs, persistence repositories, and notifier implementations must be configured by the calling application. There is no standalone scheduler deployment command or automatic email/Telegram delivery configured in `app.py`.

## Setup and run

Use **Python 3.10 or newer** (the code uses modern union types and slotted dataclasses). Run commands from the repository root.

```bash
git clone https://github.com/rock2002online-cpu/AI-Mutual-Fund-Assistant.git
cd AI-Mutual-Fund-Assistant
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies and the dashboard/test tools:

```bash
python -m pip install -r requirements.txt
python -m pip install streamlit pytest
```

`requirements.txt` currently lists pandas, openpyxl, requests, Plotly, ReportLab, SQLAlchemy, and Alembic. Streamlit and pytest are installed separately because they are not listed there. No OpenAI API key is required for the implemented advisor.

### Portfolio input and NAV access

The default loader reads `data/portfolio.xlsx`. Supply these columns:

| Column | Meaning |
| --- | --- |
| `Scheme Code` | AMFI scheme identifier |
| `Fund` | Fund name |
| `Units` | Units held |
| `Avg NAV` | Average purchase NAV per unit |

Review or replace the workbook included in the repository before using your own portfolio. The NAV service writes `data/nav_history.csv` and reuses it when its file modification date is today; otherwise it requests AMFI data. Current valuation and fund exploration therefore need network access when the cache is stale. Historical analytics need suitable history and benchmark inputs; missing inputs can leave metrics unavailable.

### Initialize database workflows

Before using transaction imports/history or tax-lot workflows, apply migrations and import the workbook and cached NAV records:

```bash
python -m alembic upgrade head
python scripts/bootstrap_enterprise_data.py
```

The bootstrap is idempotent and creates the primary portfolio, fund records, opening-balance transactions, and portfolio-related NAV history. It requires a populated `data/portfolio.xlsx` and `data/nav_history.csv`. Opening balances alone do not provide a complete historical cash-flow record for XIRR.

The default database is `database/ai_mutual_fund_assistant.db`. `config/settings.py` supports `AIMF_DATABASE_URL`, `AIMF_ENVIRONMENT`, application name/version, directory, logging, debug, and feature-flag overrides. `AIMF_APPLICATION_VERSION` can explicitly override the `37.0.0` default. These settings do not redirect every legacy CSV/Excel loader; the default portfolio and NAV loaders use the repository's `data/` directory.

### Start the dashboard

```bash
python -m streamlit run app.py
```

To record or refresh the current day's portfolio valuation snapshot:

```bash
python scripts/update_portfolio_history.py
```

This history update may retrieve live NAV data and write `data/portfolio_history.csv`.

## Testing

Run the deterministic test directories, excluding the legacy root-level live-data smoke scripts:

```bash
python -m pytest -q tests/config tests/models tests/repositories tests/services tests/scripts tests/dashboard tests/views tests/pages tests/integration
```

For settings and scheduler/recovery validation only:

```bash
python -m pytest -q tests/config/test_settings.py tests/services/test_reconciliation_sla_scheduler*.py tests/services/test_reconciliation_sla_*repository.py
```

`tests/test_nav.py` and `tests/test_valuation.py` execute live NAV requests at import time; `tests/test_loader.py` reads the workbook and prints output. An unrestricted `python -m pytest` collects those scripts as well, so it is not a reliably offline test command.

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit dashboard entry point |
| `pages/` | Multipage Streamlit entry points |
| `views/` | Page rendering and workflow orchestration |
| `dashboard/` | Shared components, charts, styling, QA, and report helpers |
| `services/` | Portfolio/NAV, analytics, AI rules, reporting, transactions, reconciliation, and scheduler services |
| `models/` | ORM entities and analytics/reconciliation data models |
| `repositories/` | Persistence repositories and Unit of Work |
| `config/` | Validated settings, database configuration, and logging |
| `migrations/`, `alembic.ini` | Database schema migrations |
| `scripts/` | Bootstrap, history update, and legacy utility entry points |
| `data/` | Portfolio workbook, NAV cache, valuation/backtest and benchmark CSVs |
| `database/` | Local SQLite database location (database files are ignored by Git) |
| `tests/` | Unit/integration tests and legacy smoke scripts |
| `requirements.txt` | Core dependencies |

PDF/Excel files written under `reports/` are generated outputs; the directory is not included in the current checkout. Stocks/ETF workflows, automated goal planning, AI fund ranking, conversational AI, and turnkey notification delivery are not claimed as completed features of this release.
