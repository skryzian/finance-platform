# Finance Platform Technical Audit

**Assessment date:** 2026-11-02  
**Scope:** Read-only review of the source, migrations, tests, client shells, environment/deployment configuration, and project documentation. No application code or data was changed.

> **Implementation update:** This is the pre-remediation baseline, not a current-state audit. Phases 1–6 have since added security hardening, an authoritative ledger, web workflows, offline sync, sourced daily valuation history, optional integrations/notifications, and consent-gated AI retrieval. The findings below describe the reviewed baseline unless stated otherwise. Previously exposed credential-like values were removed from templates, but active credentials still require owner-side rotation.

## Executive summary

The project is a Phase 1 foundation, not a functioning personal-finance management product. It has a FastAPI authentication/profile and international-settings API, market/watchlist/alert/opportunity scaffolding, an optional AI chat endpoint, a local-first mobile database/repository, and starter web/mobile screens. It does not have server-side accounts, transactions, budgets, balance calculation, transfers, assets/liabilities, recurring payments, investment holdings, or reporting APIs. The web and mobile dashboards currently render hard-coded financial figures.

**Production readiness: Not ready for real financial information.** The most urgent blockers are credential-like values in the root environment template, a profile-photo upload path that uses the submitted filename without constraining the resulting path, insecure fallback JWT secrets, and financial figures shown as though they are live. There is no server ledger against which balances, transfers, net worth, or reports could be verified.

The project is appropriately explicit that its Render configuration is demo-only in [README.md](./README.md). That warning should remain prominent; do not connect real user or financial data until the P0 roadmap items are completed.

### Maturity and architecture

| Area | Observed state |
|---|---|
| Web | Next.js 14/React/TypeScript starter dashboard and Copilot login/chat UI |
| Mobile | Expo/React Native shell; SQLCipher-configured local SQLite schema and repository |
| Backend | FastAPI, SQLAlchemy, Pydantic, JWT auth, profile, internationalization, market/intelligence, and AI routes |
| Server persistence | Three Alembic revisions for user/session, reference/intelligence, and AI data; no finance-ledger tables |
| Local persistence | Mobile schema includes accounts, transactions, budgets, assets, liabilities, investments, subscriptions, goals, and snapshots; no sync API |
| Integrations | OpenAI adapter exists but is disabled by default; market, FX, email, SMS, banking, and notification providers are not connected |
| Deployment | Compose is for local development; Render free-tier demo; no verified production operations or CI pipeline |

Runtime relationships are documented in [architecture.md](./docs/architecture.md), but that document describes several finance-domain capabilities that are not present in the backend code. The backend's registered models are in [models/__init__.py](./backend/app/models/__init__.py); the absence of the finance ledger is confirmed by the model inventory and migration chain.

### Strengths

- Password hashes are used rather than plaintext; bearer-protected routes use a shared current-user dependency.
- User-specific watchlists, alerts, opportunities, and AI conversations include ownership scoping.
- Monetary helper code rejects binary floating-point inputs, and the mobile repository stores money as decimal strings.
- OpenAI access is server-side, opt-in, bounded by prompt/token/timeout configuration, rate-limited through Redis, and disabled by default.
- SQLCipher is configured for mobile, with the database key held in SecureStore and initialization failing if SQLCipher is unavailable.
- Migrations are additive, and seeded country/currency data is inserted only when absent.
- Existing backend tests, web build, and web lint passed during this review.

### Confirmed critical concerns

1. The root [.env.example](./.env.example) contains credential-like values rather than placeholders. Their validity was not tested. Revoke/rotate every potentially real credential and secret; never copy values into reports or commit history.
2. Authenticated profile-photo upload uses the submitted filename in a path joined to local storage without resolving and constraining the target. This creates a path traversal/arbitrary-file-write risk.
3. Default JWT secrets remain usable when deployment variables are absent; startup does not reject these defaults in production.
4. Both dashboards display fixed financial numbers and trends with no sample/demo label or live-data connection.
5. The backend has no financial ledger or server APIs for accounts and transactions. Financial calculations and transaction consistency therefore cannot be certified.
6. Refresh-token renewal is a 501 stub; login records a refresh session with an expiry set to the current time. Logout deletes session rows, but access-token verification does not consult session state.

### Module-by-module assessment

| Module | Current implementation / what works | Missing, defective, or unverified | Priority |
|---|---|---|---|
| Authentication | Registration, login, bcrypt hashing, signed access JWTs, active-user check | No registration/login rate limits, email verification, password recovery, or completed refresh flow; access tokens remain usable after logout until expiry; defaults are unsafe if deployed | P0/P1 |
| Profile | Read/update profile, photo upload/delete endpoints | Profile update is duplicated and one route accepts an untyped dictionary; file path and upload-boundary issues; storage configuration is ignored; deletion does not remove stored bytes | P0/P1 |
| Accounts/transactions | Mobile schema/repository supports local account and transaction records | No server models, APIs, synchronization, double-entry/transfer semantics, or authoritative balance service; mobile UI does not use the repository | P0 |
| Income/expenses/budgets | Mobile schema has categories/budgets; category and transaction methods exist locally | No backend implementation or screens; no recurrence, reporting, categorization workflow, or calculations | P1 |
| Net worth/assets/liabilities | Mobile schema has asset, liability, investment, and snapshot tables | No backend calculations, valuation pipeline, history API, or validation; dashboard value is fixed | P0 |
| Investments/market | Backend has asset catalog, watchlists, market contracts, and user alert rules | No quote/history ingestion, prices, holdings, trade records, FX conversion, dividends, or provider adapters; catalog data is not a portfolio | P1 |
| Recurring payments | Mobile schema includes subscriptions | No recurring payment processor, reminder scheduler, history, or UI | P2 |
| Intelligence/alerts | Authenticated read/create/review endpoints and data models | No ingestion, evaluation worker, alert dispatch, or real data source; arbitrary alert conditions are stored, not evaluated | P1 |
| AI Copilot | Authenticated provider endpoint, quota, opt-in saved history, usage records, web/mobile UI | Endpoint always supplies empty verified context; it cannot answer from actual finance records. Web text implies verified data despite the absence of that data path | P1 |
| Internationalization | Country/currency reference records, settings APIs, IANA timezone validation, decimal helper | Small seeded country list, no rates/provider or locale-formatting UI; exchange-rate model has no freshness policy or integration | P2 |
| Mobile/offline | SQLCipher schema, secure key setup, local repository primitives | No local account/transaction screens in the app, no push/pull sync, conflict handling, queue, or native/device validation; sensitive SMS permission is declared without a feature | P1/P2 |
| Web UI | Static dashboard and Copilot route; responsive utility classes | Dashboard is unauthenticated and mock-only; quick actions are text, not controls; no finance forms, navigation, empty/error states, or meaningful data visualizations | P0/P2 |
| Deployment/operations | Dockerfiles, local Compose, Render demo configuration, migration command in backend container | Demo credentials in Compose; no production-grade secrets validation, backup/restore proof, monitoring, CI/CD evidence, rollback procedure, or production topology | P0/P1 |

## Professional verdict

1. **Architecturally sound?** Reasonable foundation and separation for a prototype, but not yet an implemented finance architecture. Runtime schema creation and migration ownership also need consolidation.
2. **Financially accurate?** Cannot be certified. No backend financial ledger or calculation endpoints exist; the displayed balances are constants.
3. **Secure enough for real financial information?** No. Address the exposed credential-like values, upload path handling, production secret defaults, auth lifecycle, and data-protection/operations gaps first.
4. **Scalable?** Not demonstrated. There is no server-side transaction workload, paging strategy for finance history, or production performance test.
5. **Production-ready?** No. The published Render setup is explicitly demo-only and several core finance functions are absent.
6. **Ten most important improvements:** revoke exposed credentials; constrain uploads; reject unsafe secret defaults; replace mock figures with honest empty/demo states; design and implement a server ledger; make transfers and idempotent writes transactional; implement tested balance/net-worth calculations; complete refresh/revocation and auth throttling; establish a privacy-safe sync contract for mobile; add backups/monitoring/release controls.
7. **Fix first:** rotate credentials, close the upload path issue, reject insecure production configuration, and remove/label fake balances.
8. **Next phase:** build the authoritative server financial domain and its invariant-driven tests before adding new analytics, integrations, or AI retrieval.

See [SECURITY_AUDIT.md](./SECURITY_AUDIT.md), [DATABASE_ARCHITECTURE_REVIEW.md](./DATABASE_ARCHITECTURE_REVIEW.md), [UI_UX_RECOMMENDATIONS.md](./UI_UX_RECOMMENDATIONS.md), [MISSING_FEATURES.md](./MISSING_FEATURES.md), [IMPROVEMENT_ROADMAP.md](./IMPROVEMENT_ROADMAP.md), and [TESTING_AND_VALIDATION_REPORT.md](./TESTING_AND_VALIDATION_REPORT.md) for supporting evidence and next steps.

## Scope limitations

No live PostgreSQL/Redis/Render/Vercel environment, external provider credentials, production telemetry, or native Android/iOS device was inspected. No database rows were read. Findings distinguish observed code/configuration from behavior that requires deployment or device verification. Dependency vulnerability scanning could not run because the web project has no lockfile.
