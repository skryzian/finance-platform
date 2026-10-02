import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import type { SQLiteDatabase } from 'expo-sqlite';

const DATABASE_KEY_NAME = 'finance-platform.sqlite-key.v1';
const CURRENT_SCHEMA_VERSION = 1;

const MIGRATION_1 = `
CREATE TABLE users (
  id TEXT PRIMARY KEY NOT NULL,
  remote_id TEXT UNIQUE,
  base_currency TEXT NOT NULL,
  country_code TEXT NOT NULL,
  timezone TEXT NOT NULL,
  locale TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE accounts (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL,
  institution TEXT,
  currency_code TEXT NOT NULL,
  opening_balance TEXT NOT NULL,
  current_balance TEXT NOT NULL,
  account_timezone TEXT,
  status TEXT NOT NULL,
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);
CREATE INDEX accounts_user_updated_idx ON accounts(user_id, local_updated_at DESC);

CREATE TABLE categories (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  category_type TEXT NOT NULL,
  parent_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);
CREATE INDEX categories_user_name_idx ON categories(user_id, name);

CREATE TABLE transactions (
  id TEXT PRIMARY KEY NOT NULL,
  operation_id TEXT NOT NULL UNIQUE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  account_id TEXT REFERENCES accounts(id) ON DELETE RESTRICT,
  category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
  amount TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  transaction_type TEXT NOT NULL,
  description TEXT NOT NULL,
  merchant TEXT,
  reference TEXT,
  transaction_date TEXT NOT NULL,
  notes TEXT,
  source TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'CONFIRMED',
  sync_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);
CREATE INDEX transactions_user_date_idx ON transactions(user_id, transaction_date DESC);
CREATE INDEX transactions_user_sync_idx ON transactions(user_id, sync_status, local_updated_at);

CREATE TABLE budgets (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  period_type TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT,
  limit_amount TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);
CREATE INDEX budgets_user_period_idx ON budgets(user_id, start_date, end_date);

CREATE TABLE budget_items (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  budget_id TEXT NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
  category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
  limit_amount TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1))
);
CREATE INDEX budget_items_budget_idx ON budget_items(user_id, budget_id);

CREATE TABLE assets (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  current_value TEXT NOT NULL,
  valuation_date TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE liabilities (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  liability_type TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  outstanding_balance TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE investments (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  symbol TEXT,
  investment_type TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  quantity TEXT NOT NULL,
  current_value TEXT NOT NULL,
  valuation_timestamp TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE subscriptions (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  amount TEXT NOT NULL,
  frequency TEXT NOT NULL,
  next_payment_date TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE financial_goals (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  target_amount TEXT NOT NULL,
  current_amount TEXT NOT NULL,
  target_date TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE net_worth_snapshots (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  snapshot_date TEXT NOT NULL,
  currency_code TEXT NOT NULL,
  total_assets TEXT NOT NULL,
  total_liabilities TEXT NOT NULL,
  net_worth TEXT NOT NULL,
  data_timestamp TEXT,
  UNIQUE(user_id, snapshot_date, currency_code)
);

CREATE TABLE watchlists (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  name TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);
CREATE TABLE watchlist_items (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  watchlist_id TEXT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
  asset_key TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(watchlist_id, asset_key)
);

CREATE TABLE alerts (
  id TEXT PRIMARY KEY NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  remote_id TEXT,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL,
  data_timestamp TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  sync_status TEXT NOT NULL DEFAULT 'SYNCED' CHECK (sync_status IN ('LOCAL_ONLY', 'SYNCED', 'CONFLICT')),
  sync_version INTEGER NOT NULL DEFAULT 0,
  local_updated_at TEXT NOT NULL,
  server_updated_at TEXT,
  last_synced_at TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
  UNIQUE(user_id, remote_id)
);

CREATE TABLE market_data_cache (
  asset_key TEXT PRIMARY KEY NOT NULL,
  provider_key TEXT NOT NULL,
  data_state TEXT NOT NULL CHECK (data_state IN ('LIVE', 'DELAYED', 'HISTORICAL', 'ESTIMATED', 'USER_ENTERED', 'UNAVAILABLE')),
  data_timestamp TEXT,
  retrieved_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE sync_metadata (
  user_id TEXT PRIMARY KEY NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  last_pull_cursor TEXT,
  server_version INTEGER NOT NULL DEFAULT 0,
  last_sync_at TEXT,
  local_update_counter INTEGER NOT NULL DEFAULT 0
);
`;

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function getOrCreateDatabaseKey(): Promise<string> {
  const existingKey = await SecureStore.getItemAsync(DATABASE_KEY_NAME);
  if (existingKey) return existingKey;

  const key = bytesToHex(await Crypto.getRandomBytesAsync(32));
  await SecureStore.setItemAsync(DATABASE_KEY_NAME, key);
  return key;
}

export async function initializeLocalDatabase(database: SQLiteDatabase): Promise<void> {
  const key = await getOrCreateDatabaseKey();
  await database.execAsync(`PRAGMA key = "x'${key}'"; PRAGMA cipher_memory_security = ON; PRAGMA foreign_keys = ON;`);

  const cipher = await database.getFirstAsync<{ cipher_version: string }>('PRAGMA cipher_version');
  if (!cipher?.cipher_version) {
    throw new Error('SQLCipher is unavailable. Build the app with the configured native SQLite plugin; refusing to use plaintext storage.');
  }

  const currentVersion = await database.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  const version = currentVersion?.user_version ?? 0;
  if (version > CURRENT_SCHEMA_VERSION) {
    throw new Error('Local database schema is newer than this application version.');
  }

  if (version < 1) {
    await database.withTransactionAsync(async () => {
      await database.execAsync(MIGRATION_1);
      await database.execAsync('PRAGMA user_version = 1;');
    });
  }
}
