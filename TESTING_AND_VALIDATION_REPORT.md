# Testing and Validation Report

**Assessment date:** 2026-11-02

> **Post-implementation validation:** Full backend suite: **47 passed**. Web lint and production build pass; mobile TypeScript check passes. Alembic upgrade to `20261102_000007`, downgrade to `20261102_000006`, and re-upgrade pass on disposable SQLite and PostgreSQL 16 databases. PostgreSQL concurrency/production-data tests, native Android/iOS builds, device-level SQLCipher checks, and live calls to external providers remain unverified. The baseline results below are historical.

## Original audit baseline (historical)

The following checks and conclusions describe the repository before the finance-ledger, sync, and sourced-valuation implementation. They are retained as audit history, not as the current implementation status.

| Check | Result | Notes |
|---|---|---|
| Backend pytest suite | **Passed: 21 tests** | Ran `pytest -q` using the project's backend virtual environment. The test database was created in a temporary directory outside the project, avoiding existing `.db` files. |
| Web production build | **Passed** | `npm run build` compiled Next.js 14.2.15, generated static pages, and performed TypeScript validity checks. |
| Web lint | **Passed** | `npm run lint` reported no ESLint warnings or errors. |
| Mobile TypeScript check | **Not run** | `mobile/node_modules/.bin/tsc` is absent. The attempted `npx tsc` found no local compiler; dependencies were not installed for this audit. No mobile type-check result is claimed. |
| Web dependency advisory scan | **Blocked** | `npm audit --omit=dev` returned `ENOLOCK`: the web project has no lockfile. No dependency vulnerability conclusion is made. |

The backend test run emitted 772 warnings, mainly from the installed pytest-asyncio/Starlette/httpx stack and deprecated FastAPI status constants. The suite passed despite these warnings; update/test the supported runtime and dependency set before treating warnings as harmless.

## Post-implementation verification (2026-11-02)

| Check | Result | Notes |
|---|---|---|
| Full backend suite | **Passed: 47 tests** | Includes authentication/security, ledger invariants, sync idempotency/conflicts/pagination/isolation, mocked valuation providers, AI consent/retrieval, notification delivery/device privacy, and mocked M-Pesa callbacks/STK flows. |
| Web lint | **Passed** | Next.js ESLint completed with no warnings or errors. |
| Web production build | **Passed** | Next.js build and TypeScript checks completed successfully. |
| Mobile TypeScript check | **Passed** | `npm exec -- tsc --noEmit`. |
| Alembic SQLite round trip | **Passed** | Upgrade to `20261102_000007`, downgrade to `20261102_000006`, then re-upgrade to `20261102_000007`. Disposable database removed afterward. |
| Alembic PostgreSQL 16 round trip | **Passed** | Starting from `20260926_000003`, upgrade to `20261102_000007`, downgrade to `20261102_000006`, then re-upgrade. Temporary local container removed afterward. |

Backend output included deprecation warnings from the installed pytest-asyncio/Starlette/httpx stack and deprecated FastAPI status constants; tests passed despite those warnings.

The tests cover server-owned accounts, categories, transactions/reversals, budgets, currency-scoped reports, sync ownership and conflict behavior, provider response parsing/error handling, AI retrieval consent and scoping, notification delivery preferences/device revocation, and M-Pesa idempotency/reconciliation. They do not establish PostgreSQL concurrency behavior or mobile-native runtime behavior.

## Financial scenario assessment

The server ledger enforces the expected invariant example:

| Operation | Expected consolidated cash effect |
|---|---:|
| Opening balance | +1,000 KES |
| Income | +300 KES |
| Expense | -100 KES |
| Transfer between two owned accounts | 0 KES |
| Expected resulting consolidated cash | 1,200 KES |

A transfer changes the two owned accounts by equal and opposite amounts, is excluded from income/expense, and is neutral to consolidated cash in its currency. Regression coverage is in `backend/tests/test_finance_ledger.py`.

## Not validated

- Production database connectivity, concurrent writes, or migration against real production data.
- API contract tests through web/mobile end-to-end flows.
- Android/iOS build, SQLCipher runtime, SecureStore failure/recovery, device persistence, or permissions.
- Browser accessibility, responsive behavior on real viewport/device, or full authenticated web/mobile end-to-end behavior.
- Redis failure/load behavior outside mocked AI tests; production Redis security/configuration.
- S3/object storage, TLS, backup/restore, deployment rollback, or production logs.
- Live Daraja payments/callbacks, SendGrid email, Twilio SMS, Expo push delivery, or OpenAI requests. Integrations are optional and have only mocked/test coverage; no provider credentials were supplied or used.
- Dependency vulnerability scanning. No Python scanner was run; the generated mobile lockfile is not intended as a committed artifact.
- Validity/revocation state of credential-like values in the root environment template.

During the original audit baseline, no existing local SQLite database file was opened and no persistent database rows were read or changed. Post-implementation migration verification used and removed a disposable SQLite database; it did not target the configured development database.

## Recommended validation additions

1. Add PostgreSQL migration smoke tests and transaction-isolation tests in disposable CI databases.
2. Expand ledger invariant/property tests: transfers net to zero, idempotent retries create one operation, reversals preserve history, and net worth equals assets minus liabilities by currency/date.
3. Add authorization tests for cross-user access to every new finance record and sync operation.
4. Add upload traversal, oversized body, invalid MIME/signature, replacement, and deletion tests.
5. Add refresh rotation, logout revocation, expired token, brute-force limiter, and secret-misconfiguration tests.
6. Add mobile native CI/device tests for SQLCipher key setup and offline repository access.
7. Commit lockfiles, run dependency advisory scanning, and pin reproducible container/package versions.
8. Add browser E2E and accessibility tests after core screens are connected to real APIs.
