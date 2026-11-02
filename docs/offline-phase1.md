# Offline-First Mobile: Local Storage and Synchronization

## Existing architecture analysis

- Mobile is an Expo SDK 51 / React Native app with a static dashboard and the Financial Copilot UI.
- Before this phase, mobile had no persistent database, repository layer, or cached financial records.
- The backend now provides an authoritative account/category/transaction ledger and authenticated push/pull sync endpoints. The mobile repository remains usable offline and synchronizes explicitly when the user signs in.
- AI credentials remain server-only. This offline slice does not queue AI requests or include authentication tokens in SQLite.

## Architecture

```text
Expo screen / future feature hook
             |
             v
LocalFinanceRepository (scoped by local user ID)
             |
             v
Expo SQLite + SQLCipher
             |
             +-- users, accounts, transactions, budgets, goals, assets,
             |   liabilities, investments, subscriptions, watchlists, alerts
             +-- market_data_cache, sync_metadata
```

Repository writes go to local SQLite and return without making a network request. Account and transaction rows have UUID local IDs and local/server sync metadata. Monetary values are stored and passed as decimal strings, never JavaScript numbers. Transaction timestamps are normalized to UTC.

## Mobile database strategy

The app is configured to use Expo SQLite with SQLCipher enabled by its config plugin. A random 256-bit database key is generated once, stored in platform SecureStore, and applied before schema access. If SecureStore/key retrieval fails, initialization fails rather than opening an unencrypted database. Passwords and access tokens are not stored in this database. Device-level SQLCipher operation has not yet been verified; the UI must not claim encrypted storage is ready until a native build has completed this initialization.

The versioned schema is in `mobile/src/database/localDatabase.ts`. Schema version 2 includes the financial cache tables, sync metadata, transfer destinations, and persistent conflict snapshots. Local sync versions track server versions; local edits are tracked separately with `local_updated_at` and `sync_status`.

## Repository layer

`mobile/src/repositories/localFinanceRepository.ts` exposes a user-scoped repository. It currently supports:

- Create/update local profile mapping without credentials
- Create, list, edit, and tombstone local accounts
- Create and list local categories
- Create, list, edit, and tombstone transactions
- Read and increment the local update counter
- Clear one user's device data

Creating a manual transaction means the user explicitly pressed the local save action; it is marked `CONFIRMED` and `LOCAL_ONLY`. SMS confirmation is not implemented. Account deletion uses a tombstone and synchronizes as server-side archival. A synced ledger transaction is immutable; local edits/deletes produce a conflict, and corrections should use a reversal.

Use `useLocalFinanceRepository()` inside a component below the app's `SQLiteProvider`. Resolve the local user ID after authentication and pass that ID to every repository call. `remoteUserId` can be mapped through `upsertUserProfile`; for a device-only identity, keep and pass the generated/input local `id` on later calls. Do not use one global hard-coded user ID.

## Database and conflict notes

- Financial fields use `TEXT` decimal representations, avoiding SQLite/JavaScript binary float arithmetic.
- Foreign keys are enabled, and records are filtered/scoped by the local user ID.
- Rows include `sync_status`, `sync_version`, `local_updated_at`, `server_updated_at`, `last_synced_at`, and tombstone fields where they may later synchronize.
- `POST /api/finance/sync/push` upserts versioned accounts/categories and idempotently appends transactions. `GET /api/finance/sync/pull` returns a per-user monotonic cursor and ordered events.
- Account/category updates use optimistic server versions. Conflicts preserve local data and store the server snapshot for explicit “use server” or “keep local” resolution.
- Transaction operation IDs are stable idempotency keys. Server ledger entries cannot be edited or deleted; a conflicting local transaction must be replaced with a reversal workflow.
- Sync is user initiated; background scheduling, automatic connectivity detection, retry queues, budgets/assets sync, and transaction-level local reversal creation are not implemented.
- Historical market prices and FX rates can be refreshed through authenticated server APIs. This mobile sync phase does not yet cache or synchronize those observations to the device.

## Dependencies and configuration

`mobile/package.json` adds Expo SDK 51 compatible versions of `expo-sqlite`, `expo-secure-store`, and `expo-crypto`. `mobile/app.json` enables SQLCipher via the SQLite config plugin.

SQLCipher requires a custom native build; standard Expo Go does not contain the configured SQLCipher binary. From PowerShell:

```powershell
Set-Location "C:\Users\Administrator\Desktop\New folder\finance-platform\mobile"
npm install
npx expo prebuild
npx expo run:android
```

A physical device should set `EXPO_PUBLIC_API_URL` in `mobile/.env` to the development computer's LAN API URL. The default in app config is `http://10.0.2.2:8000` for an Android emulator. This API URL is not a secret.

## Validation plan

On an Android dev build:

1. Launch the app; SQLiteProvider runs the SecureStore key setup and schema migration before rendering the dashboard.
2. Create a user profile with `upsertUserProfile` and keep its local UUID.
3. Create an account with string balances, including `"0"`.
4. Create a transaction with a decimal string and an ISO timestamp including timezone.
5. Close and reopen the app; verify the same rows are readable from the repository.
6. Call `listTransactions` with a different user ID; it must not return the first user's rows.
7. Edit then delete a transaction; it remains a local tombstone with `LOCAL_ONLY` status and is absent from normal list results.

Mobile TypeScript validation passes after installing the declared dependencies. An Android/iOS native build and device-level SQLite/SQLCipher smoke test remain unverified; Expo Go does not include the configured SQLCipher binary.

## Remaining mobile sync work

The current sync covers accounts, categories, and immutable transactions. Add durable background scheduling, bounded retries, budgets/assets synchronization, and native SQLCipher device tests only with explicit product and operational requirements. External market/FX history remains fetched through the authenticated web/server APIs; it is not synchronized to the mobile cache yet.
