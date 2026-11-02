# UI/UX Recommendations

> **Implementation update:** This was written against the pre-workflow UI. The web now has authenticated account, transaction, category, budget, report, historical market/FX, integration, and notification settings; the main dashboard no longer presents fabricated personal balances. Mobile now has explicit sign-in/sync, conflict-resolution, and push-registration controls. AI finance retrieval is read-only and requires per-user consent. Native-device accessibility and SQLCipher behavior remain unverified.

## Current experience

The web application has a single dashboard and a Financial Copilot page. The mobile app renders a static dashboard and Copilot component. Both are visually consistent enough for a prototype, use responsive layout primitives, and have a basic error/loading pattern in the Copilot UI. Neither client is yet a usable account-management product.

## Specific pages and components

### Web dashboard - [page.tsx](./web/app/page.tsx#L2)

- **Problem:** Net worth, income, expenses, savings rate, changes, and trend bars are hard-coded. No sample/demo warning is shown. The dashboard can be read as a user's actual data.
- **Recommendation:** Until live data exists, replace the figures with an explicit "Demo data - not connected to an account" state or an empty onboarding view. Once implemented, fetch authenticated summaries, show data freshness/source, selected reporting period, and distinguish zero from unavailable.
- **Problem:** "Create account", "Add transaction", "Set budget", and "Review pending SMS" are plain list text rather than actionable controls.
- **Recommendation:** Make only implemented actions into accessible links/buttons. Remove deferred actions or label them as unavailable; do not imply SMS detection is available.
- **Problem:** "Net worth trend" uses decorative bars with no labels, scale, dates, source, or accessible text alternative.
- **Recommendation:** Use a real chart with axis/period/hover or keyboard-accessible detail, currency, and an accompanying tabular summary.
- **Problem:** There is no clear authentication/onboarding shell around financial information.
- **Recommendation:** Add account creation/sign-in, protected navigation, explicit account setup, currency selection, and a first-run empty state before exposing any personalized dashboard.

### Web Financial Copilot - [financial-copilot.tsx](./web/components/financial-copilot.tsx)

- **Problem:** The assistant suggests questions about spending, net worth, portfolio, and market events, while the backend sends empty verified finance context.
- **Recommendation:** Disable finance-data suggestions until the relevant verified-data tools exist. Otherwise state plainly that connected financial data is unavailable and avoid implying the assistant knows personal records.
- **Problem:** The inline sign-in form is specific to this one component; no app-wide authenticated state or token-refresh/logout flow exists.
- **Recommendation:** Integrate a shared auth/session layer once token lifecycle is implemented. Keep tokens out of persistent browser storage unless a reviewed session design explicitly requires it.
- **Problem:** History setting updates have no visible busy state; the response body handling is mostly generic.
- **Recommendation:** Add pending/disabled states, keyboard focus, retry affordance, and explicit confirmation/result text for destructive history deletion.
- **Positive:** User/assistant messages use `aria-live`, send has an accessible label, and errors use `role="alert"`.

### Mobile dashboard - [App.tsx](./mobile/App.tsx#L23)

- **Problem:** It displays a fixed net-worth amount and an "Encrypted local storage ready" claim. SQLCipher setup is designed to fail closed, but native/device operation was not verified.
- **Recommendation:** Render real repository-derived data only after authenticated local-profile selection. Show a trustworthy storage state based on completed initialization, and do not show fabricated balances.
- **Problem:** The local finance repository is not used by the current dashboard.
- **Recommendation:** Build the core offline account and transaction flows against the repository with currency-aware input, validation, confirmation, and clear sync status.
- **Problem:** Android declares SMS and other sensitive permissions without an implemented feature.
- **Recommendation:** Remove permissions not needed by the current product. Request any future sensitive permission only at the point of use with contextual consent.

## Cross-cutting improvements

1. Establish a consistent navigation model across dashboard, accounts, transactions, budgets, reports, settings, and help.
2. Add semantic labels, visible keyboard focus, contrast checks, screen-reader announcements, and touch targets; verify with accessibility tooling.
3. Use explicit loading, empty, stale-data, offline, and error states. Never substitute demo balances for failed API results.
4. Show reporting currency, transaction/account currency, date range, data timestamp, and FX source wherever values are converted.
5. Use consistent date/number formatting from the user's locale and timezone; do not infer locale solely from country.
6. Provide chart summaries and accessible tables; color should not be the only indicator of gain/loss.
7. Use confirmation for irreversible operations and explain whether delete means archive, tombstone, or permanent removal.

## Priority

- **P0:** Remove or clearly mark mock financial values; fix misleading Copilot and encrypted-storage claims.
- **P1:** Build authenticated account/transaction flows and consistent account-level navigation after the ledger/API is ready.
- **P2:** Add accessibility, real charts, international formatting, and consistent loading/empty/error patterns.
- **P3:** Personalized insights, advanced dashboards, and household/family experiences after data and permission models are established.

No interactive browser session or device UI test was available during this review; these recommendations are based on the inspected source.
