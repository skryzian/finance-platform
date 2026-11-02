# Database design

This project uses PostgreSQL with SQLAlchemy ORM and Alembic migrations. The lists below distinguish planned finance-domain tables from tables currently created by backend migrations.

## Implemented server tables

The current migrations create users and sessions, country/currency/exchange reference data, market/provider catalogs, watchlists, alerts, opportunities, AI records, the financial ledger, sync state/events, daily FX observations, market-price history, user AI data-access consent, notification preferences/devices/feed/delivery outbox, and M-Pesa mappings/payment requests. Revisions `20261102_000004` through `20261102_000007` add the ledger, offline sync, sourced valuations, and Phase 6 integrations. See `backend/alembic/versions/` for the authoritative server schema.

## Remaining planned finance-domain tables

Investment holdings/trades, subscriptions, goals, net-worth snapshots, and import/reconciliation records remain planned. The mobile schema contains additional local cache tables; their presence does not imply server synchronization.

## Core entities

- users (including per-user AI data-access consent)
- sessions
- accounts
- transactions
- categories
- budgets
- budget_items
- assets
- liabilities
- exchange_rate_observations
- market_price_history
- user_sync_state
- sync_events
- investments
- investment_transactions
- subscriptions
- financial_goals
- net_worth_snapshots
- notifications
- notification_preferences
- push_devices
- notification_deliveries
- mpesa_account_mappings
- mpesa_c2b_payments
- mpesa_stk_requests
- audit_logs
- sms_messages
- pending_transactions
- transaction_imports
- imported_transactions
- profile_images

## ERD

```text
users
  1 ───< sessions
  1 ───< accounts
  1 ───< transactions
  1 ───< categories
  1 ───< budgets
  1 ───< budget_items
  1 ───< assets
  1 ───< liabilities
  1 ───< investments
  1 ───< investment_transactions
  1 ───< subscriptions
  1 ───< financial_goals
  1 ───< notifications
  1 ───< audit_logs
  1 ───< sms_messages
  1 ───< pending_transactions
  1 ───< transaction_imports
  1 ───< imported_transactions
  1 ───< profile_images

accounts
  1 ───< transactions

categories
  1 ───< transactions
  1 ───< budget_items

transactions
  1 ───< investment_transactions (optional referencing investment events)

investments
  1 ───< investment_transactions
```

## Design principles

- All monetary values use decimals with validation.
- Account balances are derived from opening balances and immutable ledger entries, not mutable balance columns.
- Income, expense, transfer, and reversal records are validated transactionally; transfers are currency-matched and balance-neutral in aggregate.
- Transaction writes require stable per-user idempotency keys; corrections use reversals rather than modifying posted ledger entries.
- Dated FX and market observations persist provider, effective date, retrieval time, and historical data state. Reports remain currency-scoped unless a sourced conversion is explicitly implemented.
- Profile images are stored outside PostgreSQL via a storage abstraction.

## Local development

Run PostgreSQL through Docker Compose:

```bash
docker compose up -d postgres
```

Then connect with:

```bash
psql postgresql://postgres:postgres@localhost:5432/finance_db
```
