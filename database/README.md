# Database design

This project uses PostgreSQL with SQLAlchemy ORM and Alembic migrations.

## Core entities

- users
- sessions
- accounts
- transactions
- categories
- budgets
- budget_items
- assets
- liabilities
- investments
- investment_transactions
- subscriptions
- financial_goals
- net_worth_snapshots
- notifications
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
- All updates to balances happen inside a database transaction.
- Transaction statuses are explicit and audited.
- Pending transactions cannot impact official balances until confirmation.
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
