# Database and Architecture Review

> **Implementation update:** This review captured the pre-ledger baseline. The server now has Alembic-owned finance tables for accounts, categories, immutable transactions, budgets, assets/liabilities, per-user sync state/events, daily FX observations, and market-price history. Migrations 000004–000006 add the ledger, offline sync, and sourced valuations. The mobile schema is version 2 with push/pull sync and conflict snapshots. Historical notes below describe the earlier baseline; PostgreSQL production migration/concurrency validation and native SQLCipher device validation remain outstanding.

## Current architecture

The repository is a monorepo with a Next.js web client, an Expo mobile client, and a FastAPI/SQLAlchemy backend. PostgreSQL is the intended server database, Redis is used by the AI quota limiter, and profile-file storage currently resolves to a local filesystem provider. Mobile has an independent SQLite/SQLCipher database and repository.

The server migration chain has three revisions:

1. `20240925_000001_create_users_sessions`
2. `20260925_000002_intelligence_foundation`
3. `20260926_000003_ai_copilot`

Server models include users/sessions, country/currency/exchange references, market assets/providers, watchlists, alerts/opportunities, and AI audit/conversation/usage records. The corresponding imports are in [models/__init__.py](./backend/app/models/__init__.py). There are no backend ORM models or migrations for accounts, categories, transactions, budgets, assets, liabilities, holdings, subscriptions, financial goals, or net-worth snapshots.

The mobile schema in [localDatabase.ts](./mobile/src/database/localDatabase.ts#L20) does define several of those entities, and [localFinanceRepository.ts](./mobile/src/repositories/localFinanceRepository.ts#L122) has local CRUD primitives. However, the web/mobile screens do not connect those records to the backend, and there is no synchronization API or conflict-resolution workflow.

## Confirmed findings

### 1. Architecture documentation overstates server-side implementation

[database/README.md](./database/README.md) lists finance entities and an ERD as if they were the implemented source-of-truth schema. That list is not reflected in backend models or Alembic revisions. The architecture description in [docs/architecture.md](./docs/architecture.md) also claims account logic and relational financial records that are not implemented server-side. Align these documents with the actual Phase 1 scope or clearly label planned/local-only schema.

### 2. There is no authoritative ledger or financial transaction boundary

No server transaction/account endpoints or models exist. The mobile local repository accepts both opening and current balance as input and stores transaction rows separately; the reviewed code does not calculate an account balance from transactions, implement transfers, or produce authoritative reports. It cannot guarantee that displayed balance equals underlying entries.

Before server finance APIs are added, define transaction semantics (debit/credit sign, pending/posted/reversed states, account currency, transfer pairing, effective/created time, idempotency key) and enforce writes in database transactions. A transfer must have two balanced legs and must not change consolidated net worth. Prefer an append-only ledger plus explicit reversals over destructive edits to posted entries.

### 3. Schema creation and migrations have competing ownership

[main.py](./backend/app/main.py#L21) calls `Base.metadata.create_all()` at application startup, while the backend Dockerfile runs `alembic upgrade head` before serving. `create_all` is not a migration mechanism: it does not apply column changes or migration data operations, can mask a missing migration in some environments, and makes startup behavior depend on model import state. Keep schema evolution owned by Alembic; remove runtime DDL after a controlled migration/compatibility plan.

### 4. Local SQLite security and sync limits

The mobile initializer configures SQLCipher and fails if `PRAGMA cipher_version` is absent, which is a good fail-closed design. The key is generated and stored through SecureStore. However, this has not been validated in an Android/iOS native build. No remote sync service, durable operation queue, idempotent server write, pull cursor, or conflict UI exists; the offline documentation correctly marks these as deferred.

### 5. Currency and precision

The backend [currency.py](./backend/app/utils/currency.py) accepts decimal strings/Decimal and rejects floats; `quantize_amount` supports 0-8 decimal places. Currency metadata includes decimal places. No server finance fields currently use this helper because the finance ledger is absent. Mobile stores monetary strings, but the reviewed operations do not implement rounding policy, FX valuation, or calculation tests. The FX model has `Numeric(20, 8)` and timestamps but no unique pair/effective-time constraint, provider freshness policy, or integration.

## Data integrity and performance

### Positive foundations

- User IDs and ownership filters are present for existing private data.
- Existing watchlists, alert dedupe, and user/email uniqueness use database constraints.
- Foreign keys and delete policies exist on several server entities.
- Mobile account/transaction rows have user scopes, tombstones, sync metadata, and unique operation IDs.

### Missing for real financial records

- Idempotency enforcement and duplicate external-import detection on a server endpoint.
- Atomic account/transaction/transfer operations with ledger invariant tests.
- Server-side tenant ownership constraints and tests across every new endpoint.
- Referential constraints, check constraints for amount/status/currency, and uniqueness rules for future ledger and FX records.
- Pagination/cursor contracts and indexes for high-volume transaction history.
- Tested backup, restore, retention, and deletion procedures.
- A documented policy for timestamps: UTC storage, user/account timezone for display, and stable effective-date semantics.

## Sample invariant checks (not executed against an implemented server ledger)

For an account with opening balance 1,000 KES, a 300 KES income, a 100 KES expense, and a 200 KES transfer to another owned account:

- The source and destination account balances should change by `-200` and `+200` for the transfer.
- Consolidated cash should be 1,200 KES after the income/expense, not 1,400 KES.
- A transfer should not count as income or expense.
- Net worth should equal total assets less total liabilities, with each currency translated at a dated, sourced rate if a consolidated-currency view is offered.

No backend API/model exists to run these calculations against. The existing decimal helper tests do not establish financial correctness.

## Recommended target boundary

```text
Clients (web / mobile)
        |
Authenticated API + request validation + rate limits
        |
Application services (ledger invariants, idempotency, audit)
        |
PostgreSQL (users, accounts, immutable entries, transfers, valuations)
        |                         |
Alembic-only schema changes     Outbox/background workers
                                  |
                         FX/market/notification providers
```

Keep the server authoritative for synchronized finances. The offline mobile store should be a protected cache/operation queue with explicit conflict semantics, not an independent competing source of truth.

## Verification limits

The backend tests use SQLite and do not test Alembic migrations against PostgreSQL. No live database was inspected or modified. Existing `.db` files were not opened because this audit did not require reading local data.
