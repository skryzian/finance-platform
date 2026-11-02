# Finance Platform

This monorepo contains a personal finance platform with an authoritative server ledger, web finance workflows, offline mobile persistence/synchronization, and opt-in sourced daily valuations. Kenya/KES remains the default locale; provider coverage and availability are explicit, not universal or real-time.

## Project overview

- Web frontend: Next.js + React + TypeScript + Tailwind CSS
- Mobile app: React Native + Expo
- Backend: FastAPI + SQLAlchemy + Pydantic + Alembic + PostgreSQL
- Cache: Redis
- Container orchestration: Docker Compose

## Implemented foundation and finance capabilities

- Monorepo structure
- Docker-based local environment
- PostgreSQL and Redis
- FastAPI backend foundation
- Next.js web app foundation
- React Native / Expo app foundation
- Database connection and migrations
- User model and authentication foundation
- Profile picture storage architecture
- Country, currency, timezone, locale, and display-format settings
- Market asset/provider contracts, user watchlists, configurable alert rules, and sourced opportunity records
- Restricted AI provider/tool boundary with audit data models; AI remains disabled by default and market refreshes are explicitly user-triggered
- OpenAI Financial Copilot foundation (server-only credentials, authenticated API, opt-in history, quotas, web/mobile UI)
- Authoritative accounts/categories/transactions/budgets/assets/liabilities APIs with immutable ledger entries, transfer neutrality, reversals, idempotency, and currency-scoped reports
- Authenticated web account, transaction, category, budget, report, and dated market/FX history workflows
- Mobile SQLCipher-configured local repository and user-initiated account/category/transaction synchronization with server cursors and explicit conflict resolution
- Dated historical Alpha Vantage price observations and Frankfurter/ECB reference-rate history; no automatic FX conversion or claim of live quotes
- Opt-in AI retrieval scoped to the user's ledger and sourced valuations; in-app and configurable email/SMS/push notification outbox
- Optional Daraja C2B callbacks and STK Push against an owner-managed platform shortcode; live payments are disabled by default
- Environment configuration and docs

## Directory structure

- `backend/` — FastAPI application and database models
- `web/` — Next.js dashboard frontend
- `mobile/` — Expo React Native app
- `database/` — database design docs and SQL artifacts
- `infrastructure/` — deployment and infrastructure assets
- `docs/` — technical documentation
- `docker-compose.yml` — local development runtime
- `.env.example` — environment placeholders

## Quick start

1. Create local environment files from the service templates:
   `Copy-Item .env.example .env`
   `Copy-Item backend/.env.example backend/.env`
   `Copy-Item web/.env.local.example web/.env.local`
   Set a unique local `POSTGRES_PASSWORD` in the root `.env` before starting Docker Compose. The example file intentionally contains placeholders, not usable service credentials.
2. Start the stack from the repository root:
   `docker compose up --build`
3. Backend health check:
   `http://localhost:8000/health`
4. Web app:
   `http://localhost:3000`
5. API docs:
   `http://localhost:8000/docs`

## Render demo deployment

`render.yaml` defines a free-tier demo with web, API, and managed PostgreSQL services. The web image is built for production; Docker Compose overrides its command to retain local development mode. This infrastructure is for demos and testing only, not production use with real financial data.

Render Free web services spin down after 15 minutes without traffic and can take about a minute to start again. Their local files are ephemeral, and the workspace's free instance hours are shared across services. The free PostgreSQL database is limited to 1 GB, has no backups, and expires 30 days after creation. It becomes inaccessible then and is deleted, with its data, after a further 14-day upgrade grace period. Export any demo data you want to keep before expiration. See [Render's free instance limitations](https://render.com/docs/free). Do not use this setup for production or real financial data.

Creating or syncing the Blueprint provisions resources in Render. Automatic deploys from later commits are disabled. Render may add a suffix to service URLs; keep `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` aligned with the actual API and web URLs shown in the dashboard.

## Phase 1 validation

- `POST /auth/register` creates a user
- `POST /auth/login` returns access and refresh tokens
- `GET /profile` returns the authenticated user
- `POST /profile/photo` stores a profile image reference
- `GET /health` returns service health

## Finance APIs and data-source setup

- Finance ledger: `/api/finance` (accounts, categories, transactions/reversals, budgets, reports)
- Offline sync: `/api/finance/sync/push` and `/api/finance/sync/pull`
- Historical prices/FX: `/api/markets/prices`, `/api/markets/prices/refresh`, `/api/markets/exchange-rates`, and `/api/markets/exchange-rates/refresh`
- Migrations: run `python -m alembic upgrade head` before serving requests.
- Alpha Vantage requires a server-side `ALPHA_VANTAGE_API_KEY` in `backend/.env`; never place it in a client app or send it in chat. Frankfurter/ECB daily rates require no API key.
- Alpha Vantage equity/ETF currency is user-entered because that daily response does not provide authoritative quote-currency metadata; crypto market currency is provider-reported. Historical data is not a live quote. Review provider terms before commercial redistribution.
- Phase 6 integrations are optional and disabled until configured. Setup, provider semantics, callback operations, notification outbox processing, and AI consent/data scope are documented in [docs/phase6-integrations.md](docs/phase6-integrations.md). A platform-managed M-Pesa shortcode is not a connection to a user's personal wallet.

## Notes

The intelligence upgrade gap analysis, database additions, API list, and provider boundaries are documented in [docs/intelligence-phase1-gap-analysis.md](docs/intelligence-phase1-gap-analysis.md). OpenAI configuration, data/privacy boundaries, and Copilot setup are in [docs/openai-phase1.md](docs/openai-phase1.md). No real-time prices, news, products, or promotions are fabricated. Sourced daily price/FX history is implemented; SMS analysis, bank connections, and trade execution remain out of scope. Existing SMS confirmation and core financial modules remain governed by their original phase roadmap.

The mobile local database, encryption setup, repository usage, and offline Phase 1 limits are described in [docs/offline-phase1.md](docs/offline-phase1.md). SQLCipher requires an Expo native development build; Expo Go is not sufficient for this configuration.

## Troubleshooting

- If Compose reports a missing `env` file, create the root, backend, and web files from their examples as shown in Quick start.
- If Compose reports that `POSTGRES_PASSWORD` is required, set a unique local value in the root `.env`; do not commit that file.
- If PostgreSQL is not ready, wait and rerun `docker compose up`.
- If the backend fails to start, verify that `backend/.env` uses `postgres` as its database host; the provided example is configured for Compose.
- If the frontend cannot connect to the backend, verify that `web/.env.local` sets `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- If the mobile app cannot resolve the API, check the Expo environment values and the device network.
- Run backend migrations before starting a backend manually: `python -m alembic upgrade head`.
