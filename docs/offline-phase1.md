# Offline-First Mobile: Phase 1

## Existing architecture analysis

- Mobile is an Expo SDK 51 / React Native app with a static dashboard and the Financial Copilot UI.
- Before this phase, mobile had no persistent database, repository layer, or cached financial records.
- The existing backend has authenticated REST foundations, but full accounts/transactions APIs are not yet implemented. This Phase 1 local repository is intentionally independent of network endpoints.
- AI credentials remain server-only. This offline slice does not queue AI requests or include authentication tokens in SQLite.

## Phase 1 architecture

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

The app uses Expo SQLite with SQLCipher enabled by its config plugin. A random 256-bit database key is generated once, stored in platform SecureStore, and applied before schema access. If SecureStore/key retrieval fails, initialization fails rather than opening an unencrypted database. Passwords and access tokens are not stored in this database.

The versioned schema is in `mobile/src/database/localDatabase.ts`. Schema version 1 includes the financial cache tables plus a sync metadata cursor table. A `pending_operations` queue is not created in this phase; queue processing belongs to Phase 2.

## Repository layer

`mobile/src/repositories/localFinanceRepository.ts` exposes a user-scoped repository. It currently supports:

- Create/update local profile mapping without credentials
- Create, list, edit, and tombstone local accounts
- Create and list local categories
- Create, list, edit, and tombstone transactions
- Read and increment the local update counter
- Clear one user's device data

Creating a manual transaction means the user explicitly pressed the local save action; it is marked `CONFIRMED` and `LOCAL_ONLY`. SMS confirmation is not implemented in this phase. Transaction deletion uses a tombstone so a future push sync can represent deletion rather than forgetting it.

Use `useLocalFinanceRepository()` inside a component below the app's `SQLiteProvider`. Resolve the local user ID after authentication and pass that ID to every repository call. `remoteUserId` can be mapped through `upsertUserProfile`; for a device-only identity, keep and pass the generated/input local `id` on later calls. Do not use one global hard-coded user ID.

## Database and conflict notes

- Financial fields use `TEXT` decimal representations, avoiding SQLite/JavaScript binary float arithmetic.
- Foreign keys are enabled, and records are filtered/scoped by the local user ID.
- Rows include `sync_status`, `sync_version`, `local_updated_at`, `server_updated_at`, `last_synced_at`, and tombstone fields where they may later synchronize.
- There is no push/pull API, idempotency handling on the server, conflict UI, queue, connectivity detection, or retries in Phase 1. Do not mark local-only changes as synchronized.
- Cache freshness is captured for market-data payloads, but no market data provider is connected.

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

The current environment does not have Node/npm or Android build tools available, so a native app build and device-level SQLite/SQLCipher smoke test could not be run here. Backend tests do not validate Expo native modules.

## Deferred phases

Phase 2 adds a durable operation queue and idempotent push API. Phase 3 adds incremental pull and conflict resolution. Phase 4 adds connectivity/background sync. Phase 5 adds SMS parsing/review against this repository. Phase 6 adds offline deterministic calculations and optional queued AI requests.
