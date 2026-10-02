# Intelligence Upgrade: Phase 1 Gap Analysis

## Existing foundation inspected

| Area | Existing state before this upgrade | Phase 1 change |
|---|---|---|
| Authentication | FastAPI JWT registration/login and bearer dependency | Preserved; new private APIs reuse `get_current_user` |
| Profile images | Upload route and storage interface | Unchanged |
| Financial accounts and transactions | No implemented finance domain models yet | Deferred; this upgrade does not replace or simulate them |
| Market assets | A market asset model existed but was not imported into ORM metadata and had no API | Registered, linked to exchange records, and exposed via authenticated lookup |
| Watchlists | Missing | Added user-owned lists and asset items, with ownership checks and duplicate constraints |
| Alerting | No persistent alert/rule foundation | Added configurable rules, alert records, deduplication, and delivery records |
| Opportunities | Missing | Added sourced, evidence/risk-bearing opportunity records and separate per-user review state |
| External providers | Missing | Added typed provider contracts and explicit registry; no provider or market data is fabricated |
| AI | No AI integration existed in inspected source | Added provider boundary and explicit tool allowlist; no model is enabled by default |
| Notifications | No delivery architecture existed | Added alert-delivery persistence and channel contract; sending is deferred |
| Internationalization | Country/currency/exchange-rate models and settings API existed | Preserved; added exchange reference and currency-aware fields in the intelligence foundation |
| Web/mobile | Starter Next.js and Expo shells existed | Unchanged in this backend/data Phase 1 |
| Deployment | Docker Compose and backend Dockerfile existed; startup used `create_all` | Backend container now applies Alembic revisions before serving |

## Phase 1 architecture

- PostgreSQL remains the source of truth.
- External financial data enters only through typed provider contracts and must carry provider, retrieval time, source, and data-state metadata.
- Market asset records describe instruments; no quote/history data is invented or seeded.
- Watchlists and alert preferences belong to a user. An alert is also user-scoped and deduplicated.
- Opportunities retain source evidence, verification state, risk notes, and a stable event fingerprint. Per-user review state is stored separately so one user's dismissal cannot change the global opportunity.
- AI is an optional adapter. It receives explicitly supplied context and may only access tools registered by the backend. The tool registry has no database-session exposure.
- This phase does not execute trades, apply for financial products, send alerts, or ingest external feeds.

## Database additions

The additive Alembic revision adds:

- International reference tables that existed as models but lacked a migration: `countries`, `currencies`, `exchange_rates`
- Market/provider catalog: `exchanges`, `market_assets`, `data_providers`, `data_quality_records`
- User monitoring: `watchlists`, `watchlist_items`, `alert_rules`, `alerts`, `alert_deliveries`
- Explainable opportunity records: `opportunities`, `opportunity_sources`, `opportunity_reviews`
- AI audit records: `ai_interactions`, `ai_tool_calls`

All existing authentication tables remain owned by the preceding migration.

## API additions

Authenticated endpoints:

- `GET /api/markets/assets`
- `GET /api/watchlists`
- `POST /api/watchlists`
- `GET /api/watchlists/{watchlist_id}/items`
- `POST /api/watchlists/{watchlist_id}/items`
- `GET /api/alert-rules`
- `POST /api/alert-rules`
- `GET /api/alerts`
- `GET /api/opportunities`
- `PUT /api/opportunities/{opportunity_id}/review` (user statuses only; does not verify source data)

Market asset lookup is read-only; ingestion/admin APIs are intentionally not exposed in this foundation phase.

## AI and provider contracts

Provider contracts live in `backend/app/providers/contracts.py`; they define market quote, exchange-rate, company, news, crypto, loan, and promotion capabilities. `ProviderRegistry` requires explicit registration and raises `ProviderUnavailable` when absent.

Notification delivery uses a separate provider contract in `backend/app/providers/notifications.py`; persistent delivery records are in `alert_deliveries`. No outbound notification provider is configured in this phase.

The AI boundary lives in `backend/app/ai/service.py`. `ToolRegistry` is an explicit allowlist. An unregistered tool cannot be invoked. No prompt endpoint is exposed until a real provider, data minimization policy, and interaction audit integration are configured.

## Setup and migration

From the repository root in PowerShell:

```powershell
Set-Location "C:\Users\Administrator\Desktop\New folder\finance-platform"
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item web\.env.local.example web\.env.local
docker compose up --build
```

The backend container runs `alembic upgrade head` before Uvicorn. For an existing database, back it up before applying the migration. Do not run the initial revision against a database that was created manually without checking its Alembic version state.

## Validation

Backend tests are in `backend/tests/`. With a supported Python runtime and dependencies installed:

```powershell
Set-Location "C:\Users\Administrator\Desktop\New folder\finance-platform\backend"
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

This environment previously reported Python 3.14 while the pinned Pydantic dependency was not available as a wheel, and Node/Docker were absent. The backend Docker image uses Python 3.12; run tests there or use local Python 3.12. The psycopg binary pin was updated to 3.2.13 to match the package versions present in the reported package index.

## Later phases

No Phase 2 market ingestion, NSE/NYSE/LSE adapters, price history, dividends, news, event correlation, loans/promotions catalog, crypto market feed, AI chat endpoint, scheduler, or alert dispatch is implemented here. Those integrations must each have a real provider, licensing/source policy, freshness rules, failure handling, and tests before their data is presented as current.
