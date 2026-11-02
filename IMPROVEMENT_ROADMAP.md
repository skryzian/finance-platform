# Prioritized Improvement Roadmap

This roadmap began as a baseline audit. Phases 1–6 have since been implemented, with the Phase 6 integrations optional and disabled until configured by the service owner. The original items below should be read with this current status:

| Phase | Current status |
|---|---|
| 1. Security/deployment and honest absent-data UI | Implemented; rotate any previously exposed active credentials and complete production operations review |
| 2. Authoritative ledger, invariants, migrations, tests | Implemented |
| 3. Account, transaction, category, budget, and report workflows | Implemented in web |
| 4. Offline sync with idempotency and conflicts | Implemented for accounts/categories/transactions; user-initiated only |
| 5. Sourced FX/market history | Implemented for daily Frankfurter/ECB rates and Alpha Vantage historical equities/ETFs/crypto; key and license requirements remain |
| 6. Integrations, notification delivery, and AI retrieval | Implemented: Daraja C2B/STK foundations, durable notification outbox/adapters, and per-user-consented scoped AI retrieval; provider credentials, live delivery, and production operations remain owner-configured/unverified |

## P0 - Critical: block real-data launch

| Problem | Proposed solution | Files/modules | Dependencies | Complexity | Expected outcome |
|---|---|---|---|---|---|
| Credential-like values are present in the root environment template | Revoke/rotate all potentially real credentials; sanitize template/history; add secret scanning | `.env.example`, deployment secret stores, CI | Provider account access; repository history review | S | No usable credentials remain in source control |
| Upload filename can escape the storage directory | Generate server-side names; enforce resolved-path containment; isolate storage; add malicious-path tests | `backend/app/api/routes/profile.py`, `backend/app/storage/storage.py` | Chosen storage backend | M | Authenticated uploads cannot write outside the photo namespace |
| Fixed demo financial figures appear live | Replace with explicit demo labels or empty states until APIs exist | `web/app/page.tsx`, `mobile/App.tsx` | Product copy/design decision | S | Users cannot mistake fabricated data for their own |
| Production configuration permits default JWT secrets | Require strong distinct secrets in production and fail startup on defaults | `backend/app/core/config.py`, deployment config | Secret manager configuration | S | Missing secret configuration fails closed |
| No authoritative server ledger exists | Design and implement accounts, immutable entries, transfers, currencies, idempotency, and ownership model | New backend models/schemas/services/routes and Alembic revisions; tests | Approved ledger semantics and migration/data plan | XL | One server source of truth for balances and future reports |
| No financial invariant verification | Add deterministic tests for income, expense, transfer, reversal, precision, FX, and net-worth calculations | Backend services/tests; mobile repository tests | Ledger service | L | Financial outputs are checked against explicit expected values |

## P1 - High priority: complete core workflows and auth

| Problem | Proposed solution | Files/modules | Dependencies | Complexity | Expected outcome |
|---|---|---|---|---|---|
| Refresh flow is unimplemented and session expiry is invalid; logout does not revoke JWTs | Implement refresh rotation/revocation, expiry checks, logout semantics, and lifecycle tests | `backend/app/api/routes/auth.py`, `backend/app/api/deps.py`, session model | Token/session design | L | Predictable, testable authentication lifecycle |
| Login/register are not visibly throttled | Add abuse-resistant rate limits, monitoring, and safe enumeration behavior | Auth routes, Redis/rate-limit service, deployment | Redis availability and policy | M | Reduced credential stuffing and account probing |
| Profile update APIs are duplicated and validation differs | Consolidate routes around typed schemas and shared validation | `backend/app/api/routes/auth.py`, `profile.py`, Pydantic schemas | API compatibility decision | M | Consistent profile validation and response behavior |
| Photo storage ignores configured provider and deletion leaves files | Implement configured object storage, bounded uploads, replacement cleanup, and private access policy | `backend/app/storage/`, profile route, configuration | Provider selection, lifecycle policy | M | Durable and privacy-preserving profile media |
| Mobile data has no server sync | Define push/pull cursors, idempotency, tombstones, conflict model, and per-user auth; then build sync | Mobile repository/hook; new backend API/services | Server ledger and auth completion | XL | Offline edits synchronize safely across devices |
| Copilot has no verified finance context | Keep finance-specific prompts disabled or explicitly unavailable; implement scoped retrieval only after ledger services and privacy review | `backend/app/api/routes/ai.py`, tool registry, tests, UI copy | Ledger APIs, AI threat/privacy review | L | AI answers cite actual dated data or refuse unsupported claims |
| Demo deployment lacks operational controls | Establish production-grade database, backups/restore tests, TLS, logging/monitoring, runbook, rollback, and deployment secrets | `render.yaml`, Dockerfiles, operations configuration | Target hosting decision | L | Recoverable, observable, securely configured deployment |

## P2 - Medium priority: reliability and user experience

| Problem | Proposed solution | Files/modules | Dependencies | Complexity | Expected outcome |
|---|---|---|---|---|---|
| Static dashboard and nonfunctional quick actions | Build authenticated account/transaction/budget workflows with loading, empty, offline, and error states | `web/app`, `web/components`, mobile screens | Ledger APIs and UX design | L | Usable core product rather than a static prototype |
| Accessibility and localized financial presentation are unverified | Add keyboard/screen-reader/contrast tests and locale/timezone-aware amounts/dates | Web/mobile presentation components | Shared formatting policy | M | Inclusive, internationally consistent experience |
| Runtime `create_all` competes with migration workflow | Make Alembic the sole schema owner and test upgrade/downgrade on disposable PostgreSQL | `backend/app/main.py`, migrations, Docker startup | Migration validation plan | M | Reproducible deploy-time schema changes |
| No pagination/query-budget policy exists for future ledger APIs | Design cursor pagination and indexes alongside transaction endpoints; profile representative datasets | New finance API/query modules | Ledger schema | M | Predictable latency as transaction history grows |
| Mobile SQLCipher/native configuration was not built or tested | Add Android dev-build smoke tests for key setup, persistence, wrong-key failure, and clear-user operation | `mobile/app.json`, local database, CI/device workflow | Native build infrastructure | M | Verified encrypted local persistence |
| Sensitive SMS permission is declared without an active feature | Remove until approved use; document consent and data lifecycle before reintroducing | `mobile/app.json` and any future SMS module | Product/privacy review | S | Least-privilege app permissions |

## P3 - Future enhancements

| Problem/opportunity | Proposed solution | Files/modules | Dependencies | Complexity | Expected outcome |
|---|---|---|---|---|---|
| No transaction import or bank/M-Pesa connectivity | Select providers based on Kenyan availability, contracts, consent, and reconciliation support | Provider adapters, import pipeline, finance APIs | Ledger/idempotency and provider due diligence | XL | Lower manual entry with traceable imported records |
| No sourced portfolio valuation or market history | Add licensed providers, freshness metadata, currency conversion, and stale-data UI | Market provider contracts/adapters, valuation services | Holdings model and licensing | XL | Explainable investment values, not just symbol watchlists |
| No notification worker or delivery provider | Add transactional outbox, retry policy, provider receipts, and user channel preferences | Alert delivery model, worker, provider adapters | Real alert sources and operations | L | Reliable, auditable reminders |
| No savings goals/export/shared finance | Add only after demand and privacy/authorization requirements are established | Goals, exports, household modules | Stable user/ledger authorization model | M-XL | Product expansion without weakening ownership boundaries |

## Release gates

Do not treat a release as suitable for real financial information until P0 is complete, the backend ledger invariants pass against PostgreSQL, authorization/isolation tests cover new endpoints, restore is proven, and security findings are re-reviewed. Detailed validation limitations are in [TESTING_AND_VALIDATION_REPORT.md](./TESTING_AND_VALIDATION_REPORT.md).
