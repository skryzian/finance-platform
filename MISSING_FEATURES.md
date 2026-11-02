# Missing Features and Product Value

This list has been updated after implementation of phases 1–6. The remaining gaps below distinguish implemented foundations from features still requiring product, provider, or licensing work.

| Feature | Observed gap | Value | Complexity |
|---|---|---|---|
| Server accounts and ledger transactions | Implemented: account/category/immutable transaction APIs, idempotency, derived balances, and ownership checks | Authoritative source of truth for balances and history | XL |
| Transfers and reconciliation | Transfers are balance-neutral and reversals are append-only; statement matching/reconciliation is still absent | Prevents incorrect cash totals and supports auditability | L |
| Income/expense categorization and reports | Implemented: categories, currency-scoped totals, budgets, reports, and web forms | Makes spending history useful and supports downstream budgets | L |
| Budgets and recurring transactions | Budgets and current spend reporting are implemented; recurring-payment scheduling is not | Spending controls and predictable cash-flow views | L |
| Assets, liabilities, net worth | Current asset/liability values and currency-scoped net worth are implemented; historical balance-sheet snapshots are not | Trustworthy net-worth statement and historical trend | L |
| Investments and investment activity | Dated provider price observations exist; user holdings, trades, cost basis, and realized P/L do not | Portfolio valuation and cost-basis/P&L tracking | XL |
| Multi-currency valuation | Dated Frankfurter/ECB reference rates are stored; reports remain grouped by currency and never auto-convert | Comparable reports without silently mixing currencies | L |
| Mobile-to-server synchronization | Authenticated account/category/transaction push-pull, idempotency, per-user cursors, and explicit conflict resolution are implemented; sync is user initiated | Multi-device continuity and recoverability | XL |
| Profile image object storage | Upload path/content/size handling is hardened; a configured remote object-storage adapter remains unimplemented | Durable, bounded, secure media handling in deployment | M |
| Account recovery and verification | No password reset/email verification workflow | Recoverable accounts and reduced account abuse | M |
| Notification delivery | Implemented: in-app feed, preferences, durable outbox, retry worker, and optional SendGrid/Twilio/Expo adapters; credentials and live end-to-end delivery remain unverified | Timely user-noticed alerts | M |
| Market/FX/news ingestion | Manual daily Alpha Vantage price and Frankfurter/ECB rate refreshes are implemented; no scheduler, news feed, or alert evaluation worker | Fresh sourced data for investments and alerts | L-XL |
| M-Pesa/bank connection/import | Optional Daraja C2B callbacks and STK Push against an owner-managed platform shortcode are implemented; live payments are disabled by default. Personal-wallet/bank connections and general transaction imports remain absent. | Reduce manual entry for Kenya and international use | XL per provider |
| Goals and emergency-fund tracking | Mobile schema only; no UI/API/calculation | Actionable savings targets and progress tracking | M |
| Export and data portability | No CSV/Excel/PDF export or account deletion/recovery workflow | User control, reporting, and regulatory readiness | M |
| Transaction search/pagination | List pagination and account filtering exist; free-text search and cursor pagination do not | Usable large histories and scalable client queries | M |
| Shared/family access and roles | No authorization roles or household ownership model | Controlled shared finances if product scope requires it | XL |

## Avoid premature implementation

- The M-Pesa integration is not a personal-wallet connection. Keep live payments disabled until shortcode ownership, provider contracts, callback/logging controls, reconciliation, and production tests are verified.
- AI retrieval is read-only, scoped to the user's own ledger and sourced valuations, and requires explicit per-user consent. Do not broaden its data access or make consequential actions available without a separate privacy/security review.
- Do not implement transaction SMS reading as a background permission-driven feature without a clear consent, review, privacy, and platform-policy design.
- Do not use market feeds as a substitute for user-reported holdings, reconciled transaction history, or dated valuations.

## Recommended next work

The six roadmap phases are implemented. Remaining work is operational and product-specific: configure and verify provider accounts, perform production deployment/privacy review, add bank connections and transaction imports if approved, schedule market refreshes, and build remaining investment, export, recovery, and reconciliation workflows.
