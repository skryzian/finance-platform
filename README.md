# Finance Platform

This monorepo contains the Phase 1 foundation for a global personal finance platform, initially configured with Kenya/KES defaults, designed for web, Android, and a shared backend.

## Project overview

- Web frontend: Next.js + React + TypeScript + Tailwind CSS
- Mobile app: React Native + Expo
- Backend: FastAPI + SQLAlchemy + Pydantic + Alembic + PostgreSQL
- Cache: Redis
- Container orchestration: Docker Compose

## Phase 1 scope

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
- Restricted AI provider/tool boundary with audit data models; no AI or market feed is enabled by default
- OpenAI Financial Copilot foundation (server-only credentials, authenticated API, opt-in history, quotas, web/mobile UI)
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
   `Copy-Item backend/.env.example backend/.env`
   `Copy-Item web/.env.local.example web/.env.local`
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

Creating or syncing the Blueprint provisions resources in Render. Automatic deploys from later commits are disabled. The API and web service names determine the configured `.onrender.com` URLs, so update `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` if Render assigns different URLs.

## Phase 1 validation

- `POST /auth/register` creates a user
- `POST /auth/login` returns access and refresh tokens
- `GET /profile` returns the authenticated user
- `POST /profile/photo` stores a profile image reference
- `GET /health` returns service health

## Notes

The intelligence upgrade gap analysis, database additions, API list, provider boundaries, and deferred integration work are documented in [docs/intelligence-phase1-gap-analysis.md](docs/intelligence-phase1-gap-analysis.md). OpenAI configuration, data/privacy boundaries, and Copilot setup are in [docs/openai-phase1.md](docs/openai-phase1.md). No real-time prices, news, products, or promotions are fabricated. Market ingestion, alert delivery, data-aware AI tools, SMS analysis, and trade execution are not implemented in this phase. Existing SMS confirmation and core financial modules remain governed by their original phase roadmap.

The mobile local database, encryption setup, repository usage, and offline Phase 1 limits are described in [docs/offline-phase1.md](docs/offline-phase1.md). SQLCipher requires an Expo native development build; Expo Go is not sufficient for this configuration.

## Troubleshooting

- If Compose reports a missing `env` file, create the backend and web files from their examples as shown in Quick start.
- If PostgreSQL is not ready, wait and rerun `docker compose up`.
- If the backend fails to start, verify that `backend/.env` uses `postgres` as its database host; the provided example is configured for Compose.
- If the frontend cannot connect to the backend, verify that `web/.env.local` sets `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- If the mobile app cannot resolve the API, check the Expo environment values and the device network.
- Run backend migrations before starting a backend manually: `python -m alembic upgrade head`.
