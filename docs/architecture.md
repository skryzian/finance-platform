# System architecture

## Overview

The platform is structured as a monorepo with a single shared backend service and separate client applications for web and Android.

## Runtime architecture

```text
WEB APP (Next.js)      MOBILE APP (Expo)
        |                    |
        +---------|----------+
                  |
                  v
             REST API (FastAPI)
                  |
          +-------+--------+----------+
          |                |          |
          v                v          v
     PostgreSQL        Redis      Providers
          |                         (optional)
          v
    Object storage abstraction
          ^
          |
  Notification outbox worker
```

## Separation of concerns

- Web: user dashboard, analytics, settings, and configuration
- Mobile: mobile-first access, pending detections, review workflows, and notifications
- Backend: authentication, profiles, international settings, financial ledger/sync, sourced valuations, scoped AI retrieval, notification delivery, and optional M-Pesa integration
- Database: PostgreSQL is the source of truth for accounts, categories, immutable transactions, budgets, balance-sheet records, dated market prices, FX observations, and sync events
- Storage: non-relational binary assets such as profile images and supporting media

## Persistence model

- PostgreSQL keeps the relational financial data model.
- Alembic migrations own the server schema. Account balances are derived from opening balances and immutable ledger entries; income, expense, transfer, and reversal semantics are enforced by the API and database constraints.
- Mobile synchronization uses authenticated push/pull endpoints, client IDs, server versions, stable transaction idempotency keys, and per-user cursors. Conflicts are returned rather than silently overwritten.
- Valuation observations are stored with effective dates, provider identifiers, retrieval times, and an explicit historical data state. The API does not treat daily prices or ECB reference rates as live quotes.
- Redis is reserved for caches, rate limiting, and optional queues.
- Notifications are persisted in a PostgreSQL outbox and dispatched by the API or worker; configured external providers are opt-in. Provider acceptance is not proof of end-user delivery.
- AI retrieval requires an explicit per-user data-access choice and returns bounded context from only that user's ledger plus sourced valuation observations. Model access remains server-side and optional.
- M-Pesa callbacks reconcile against a platform-managed merchant shortcode. They do not connect to personal wallets; live STK payments remain disabled unless an owner configures and explicitly enables them.
- File/object storage handles profile photos and future document attachments.

## Security model

- Passwords never stored as plain text.
- JWTs are short-lived and used for access.
- Refresh tokens are stored with hashes and can be revoked.
- Authenticated requests use HTTP Bearer tokens.
- File uploads are validated before acceptance.

## Deployment model

- Local: Docker Compose for backend, database, and Redis
- Production: Vercel for web, Render/AWS/GCP for backend, managed PostgreSQL, object storage, and managed Redis
