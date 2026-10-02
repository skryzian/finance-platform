import * as Crypto from 'expo-crypto';
import type { SQLiteDatabase } from 'expo-sqlite';

import type {
  LocalAccount,
  LocalAccountInput,
  LocalCategory,
  LocalSyncMetadata,
  LocalTransaction,
  LocalTransactionInput,
  LocalUserProfile,
  LocalUserProfileInput,
} from '../types/offline';

function nowUtc(): string {
  return new Date().toISOString();
}

function validateCurrencyCode(code: string): string {
  const normalized = code.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(normalized)) {
    throw new Error('Currency must be a three-letter ISO 4217 code.');
  }
  return normalized;
}

function validateAmount(amount: string): string {
  const normalized = amount.trim();
  if (!/^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/.test(normalized) || /^0(?:\.0+)?$/.test(normalized)) {
    throw new Error('Amount must be a positive decimal string with up to eight decimal places.');
  }
  return normalized;
}

function validateBalance(balance: string): string {
  const normalized = balance.trim();
  if (!/^-?(?:0|[1-9]\d*)(?:\.\d{1,8})?$/.test(normalized)) {
    throw new Error('Balance must be a decimal string with up to eight decimal places.');
  }
  return normalized;
}

function validateUtcTimestamp(value: string): string {
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) || !Number.isFinite(Date.parse(value))) {
    throw new Error('Transaction date must include a timezone offset.');
  }
  return new Date(value).toISOString();
}

function mapUser(row: Record<string, unknown>): LocalUserProfile {
  return {
    id: String(row.id),
    remoteUserId: row.remote_id == null ? null : String(row.remote_id),
    baseCurrency: String(row.base_currency),
    countryCode: String(row.country_code),
    timezone: String(row.timezone),
    locale: String(row.locale),
    createdAt: String(row.created_at),
    updatedAt: String(row.updated_at),
  };
}

function mapAccount(row: Record<string, unknown>): LocalAccount {
  return {
    id: String(row.id),
    userId: String(row.user_id),
    remoteId: row.remote_id == null ? null : String(row.remote_id),
    name: String(row.name),
    accountType: String(row.account_type),
    institution: row.institution == null ? null : String(row.institution),
    currencyCode: String(row.currency_code),
    openingBalance: String(row.opening_balance),
    currentBalance: String(row.current_balance),
    accountTimezone: row.account_timezone == null ? null : String(row.account_timezone),
    status: String(row.status),
    syncStatus: row.sync_status as LocalAccount['syncStatus'],
    syncVersion: Number(row.sync_version),
    localUpdatedAt: String(row.local_updated_at),
    serverUpdatedAt: row.server_updated_at == null ? null : String(row.server_updated_at),
    lastSyncedAt: row.last_synced_at == null ? null : String(row.last_synced_at),
  };
}

function mapCategory(row: Record<string, unknown>): LocalCategory {
  return {
    id: String(row.id),
    userId: String(row.user_id),
    name: String(row.name),
    categoryType: row.category_type as LocalCategory['categoryType'],
    parentId: row.parent_id == null ? null : String(row.parent_id),
    syncStatus: row.sync_status as LocalCategory['syncStatus'],
    localUpdatedAt: String(row.local_updated_at),
  };
}

function mapTransaction(row: Record<string, unknown>): LocalTransaction {
  return {
    id: String(row.id),
    operationId: String(row.operation_id),
    userId: String(row.user_id),
    remoteId: row.remote_id == null ? null : String(row.remote_id),
    accountId: row.account_id == null ? null : String(row.account_id),
    categoryId: row.category_id == null ? null : String(row.category_id),
    amount: String(row.amount),
    currencyCode: String(row.currency_code),
    transactionType: String(row.transaction_type),
    description: String(row.description),
    merchant: row.merchant == null ? null : String(row.merchant),
    reference: row.reference == null ? null : String(row.reference),
    transactionDate: String(row.transaction_date),
    notes: row.notes == null ? null : String(row.notes),
    source: String(row.source),
    status: String(row.status),
    syncStatus: row.sync_status as LocalTransaction['syncStatus'],
    syncVersion: Number(row.sync_version),
    localUpdatedAt: String(row.local_updated_at),
    serverUpdatedAt: row.server_updated_at == null ? null : String(row.server_updated_at),
    lastSyncedAt: row.last_synced_at == null ? null : String(row.last_synced_at),
  };
}

export class LocalFinanceRepository {
  constructor(private readonly database: SQLiteDatabase) {}

  async upsertUserProfile(input: LocalUserProfileInput): Promise<LocalUserProfile> {
    const remoteUserId = input.remoteUserId?.trim() || null;
    const baseCurrency = validateCurrencyCode(input.baseCurrency);
    const countryCode = input.countryCode.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(countryCode)) throw new Error('Country must be an ISO 3166-1 alpha-2 code.');
    if (!input.timezone.trim() || !input.locale.trim()) throw new Error('Timezone and locale are required.');

    const existing = remoteUserId
      ? await this.database.getFirstAsync<{ id: string }>('SELECT id FROM users WHERE remote_id = ?', remoteUserId)
      : input.id
        ? await this.database.getFirstAsync<{ id: string }>('SELECT id FROM users WHERE id = ?', input.id)
        : null;
    const userId = existing?.id ?? input.id ?? Crypto.randomUUID();
    const now = nowUtc();
    await this.database.withTransactionAsync(async () => {
      await this.database.runAsync(
        `INSERT INTO users (id, remote_id, base_currency, country_code, timezone, locale, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET
           remote_id = excluded.remote_id,
           base_currency = excluded.base_currency,
           country_code = excluded.country_code,
           timezone = excluded.timezone,
           locale = excluded.locale,
           updated_at = excluded.updated_at`,
        userId,
        remoteUserId,
        baseCurrency,
        countryCode,
        input.timezone.trim(),
        input.locale.trim(),
        now,
        now,
      );
      await this.database.runAsync('INSERT OR IGNORE INTO sync_metadata (user_id) VALUES (?)', userId);
    });
    const row = await this.database.getFirstAsync<Record<string, unknown>>('SELECT * FROM users WHERE id = ?', userId);
    if (!row) throw new Error('Unable to save the local user profile.');
    return mapUser(row);
  }

  async getUserByRemoteId(remoteUserId: string): Promise<LocalUserProfile | null> {
    const row = await this.database.getFirstAsync<Record<string, unknown>>(
      'SELECT * FROM users WHERE remote_id = ?',
      remoteUserId,
    );
    return row ? mapUser(row) : null;
  }

  async createAccount(userId: string, input: LocalAccountInput): Promise<LocalAccount> {
    await this.requireUser(userId);
    if (!input.name.trim() || !input.accountType.trim()) throw new Error('Account name and type are required.');
    const id = Crypto.randomUUID();
    const now = nowUtc();
    const currencyCode = validateCurrencyCode(input.currencyCode);
    const openingBalance = validateBalance(input.openingBalance);
    const currentBalance = validateBalance(input.currentBalance);
    await this.database.withTransactionAsync(async () => {
      await this.database.runAsync(
        `INSERT INTO accounts (
        id, user_id, name, account_type, institution, currency_code, opening_balance,
        current_balance, account_timezone, status, sync_status, local_updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOCAL_ONLY', ?)`,
        id,
        userId,
        input.name.trim(),
        input.accountType.trim(),
        input.institution?.trim() || null,
        currencyCode,
        openingBalance,
        currentBalance,
        input.accountTimezone?.trim() || null,
        input.status ?? 'ACTIVE',
        now,
      );
      await this.incrementLocalUpdateCounter(userId);
    });
    const row = await this.database.getFirstAsync<Record<string, unknown>>('SELECT * FROM accounts WHERE id = ?', id);
    if (!row) throw new Error('Unable to save the local account.');
    return mapAccount(row);
  }

  async listAccounts(userId: string): Promise<LocalAccount[]> {
    const rows = await this.database.getAllAsync<Record<string, unknown>>(
      'SELECT * FROM accounts WHERE user_id = ? AND is_deleted = 0 ORDER BY name COLLATE NOCASE',
      userId,
    );
    return rows.map(mapAccount);
  }

  async updateAccount(userId: string, accountId: string, input: LocalAccountInput): Promise<LocalAccount> {
    await this.requireOwnedRecord('accounts', userId, accountId);
    if (!input.name.trim() || !input.accountType.trim()) throw new Error('Account name and type are required.');
    const currencyCode = validateCurrencyCode(input.currencyCode);
    const openingBalance = validateBalance(input.openingBalance);
    const currentBalance = validateBalance(input.currentBalance);
    const now = nowUtc();
    await this.database.withTransactionAsync(async () => {
      await this.database.runAsync(
        `UPDATE accounts SET name = ?, account_type = ?, institution = ?, currency_code = ?,
         opening_balance = ?, current_balance = ?, account_timezone = ?, status = ?,
         sync_status = 'LOCAL_ONLY', sync_version = sync_version + 1, local_updated_at = ?, is_deleted = 0
         WHERE id = ? AND user_id = ?`,
        input.name.trim(),
        input.accountType.trim(),
        input.institution?.trim() || null,
        currencyCode,
        openingBalance,
        currentBalance,
        input.accountTimezone?.trim() || null,
        input.status ?? 'ACTIVE',
        now,
        accountId,
        userId,
      );
      await this.incrementLocalUpdateCounter(userId);
    });
    const row = await this.database.getFirstAsync<Record<string, unknown>>(
      'SELECT * FROM accounts WHERE id = ? AND user_id = ?',
      accountId,
      userId,
    );
    if (!row) throw new Error('Account not found for this user.');
    return mapAccount(row);
  }

  async deleteAccount(userId: string, accountId: string): Promise<void> {
    await this.database.withTransactionAsync(async () => {
      await this.requireOwnedRecord('accounts', userId, accountId);
      await this.database.runAsync(
        `UPDATE accounts SET is_deleted = 1, sync_status = 'LOCAL_ONLY',
         sync_version = sync_version + 1, local_updated_at = ? WHERE id = ? AND user_id = ?`,
        nowUtc(),
        accountId,
        userId,
      );
      await this.incrementLocalUpdateCounter(userId);
    });
  }

  async createCategory(userId: string, name: string, categoryType: 'INCOME' | 'EXPENSE', parentId?: string | null) {
    await this.requireUser(userId);
    const normalizedName = name.trim();
    if (!normalizedName) throw new Error('Category name is required.');
    const categoryId = Crypto.randomUUID();
    const now = nowUtc();
    await this.database.withTransactionAsync(async () => {
      if (parentId) await this.requireOwnedRecord('categories', userId, parentId);
      await this.database.runAsync(
        `INSERT INTO categories (
          id, user_id, name, category_type, parent_id, sync_status, local_updated_at
        ) VALUES (?, ?, ?, ?, ?, 'LOCAL_ONLY', ?)`,
        categoryId,
        userId,
        normalizedName,
        categoryType,
        parentId ?? null,
        now,
      );
      await this.incrementLocalUpdateCounter(userId);
    });
    return {
      id: categoryId,
      userId,
      name: normalizedName,
      categoryType,
      parentId: parentId ?? null,
      syncStatus: 'LOCAL_ONLY' as const,
      localUpdatedAt: now,
    };
  }

  async listCategories(userId: string): Promise<LocalCategory[]> {
    const rows = await this.database.getAllAsync<Record<string, unknown>>(
      'SELECT * FROM categories WHERE user_id = ? AND is_deleted = 0 ORDER BY name COLLATE NOCASE',
      userId,
    );
    return rows.map(mapCategory);
  }

  async createTransaction(userId: string, input: LocalTransactionInput): Promise<LocalTransaction> {
    await this.requireUser(userId);
    if (!input.description.trim()) throw new Error('Transaction description is required.');
    if (!input.transactionType.trim()) throw new Error('Transaction type is required.');
    const amount = validateAmount(input.amount);
    const currencyCode = validateCurrencyCode(input.currencyCode);
    const transactionDate = validateUtcTimestamp(input.transactionDate);
    const id = Crypto.randomUUID();
    const now = nowUtc();

    await this.database.withTransactionAsync(async () => {
      if (input.accountId) await this.requireOwnedRecord('accounts', userId, input.accountId);
      if (input.categoryId) await this.requireOwnedRecord('categories', userId, input.categoryId);
      await this.database.runAsync(
        `INSERT INTO transactions (
          id, operation_id, user_id, account_id, category_id, amount, currency_code,
          transaction_type, description, merchant, reference, transaction_date, notes,
          source, status, sync_status, local_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'MANUAL', 'CONFIRMED', 'LOCAL_ONLY', ?)`,
        id,
        id,
        userId,
        input.accountId ?? null,
        input.categoryId ?? null,
        amount,
        currencyCode,
        input.transactionType.trim(),
        input.description.trim(),
        input.merchant?.trim() || null,
        input.reference?.trim() || null,
        transactionDate,
        input.notes?.trim() || null,
        now,
      );
      await this.incrementLocalUpdateCounter(userId);
    });

    const row = await this.database.getFirstAsync<Record<string, unknown>>('SELECT * FROM transactions WHERE id = ?', id);
    if (!row) throw new Error('Unable to save the local transaction.');
    return mapTransaction(row);
  }

  async updateTransaction(userId: string, transactionId: string, input: LocalTransactionInput): Promise<LocalTransaction> {
    if (!input.description.trim()) throw new Error('Transaction description is required.');
    if (!input.transactionType.trim()) throw new Error('Transaction type is required.');
    const amount = validateAmount(input.amount);
    const currencyCode = validateCurrencyCode(input.currencyCode);
    const transactionDate = validateUtcTimestamp(input.transactionDate);
    const now = nowUtc();

    await this.database.withTransactionAsync(async () => {
      await this.requireOwnedRecord('transactions', userId, transactionId);
      if (input.accountId) await this.requireOwnedRecord('accounts', userId, input.accountId);
      if (input.categoryId) await this.requireOwnedRecord('categories', userId, input.categoryId);
      await this.database.runAsync(
        `UPDATE transactions SET
          account_id = ?, category_id = ?, amount = ?, currency_code = ?, transaction_type = ?,
          description = ?, merchant = ?, reference = ?, transaction_date = ?, notes = ?,
          sync_status = 'LOCAL_ONLY', sync_version = sync_version + 1,
          local_updated_at = ?, is_deleted = 0
         WHERE id = ? AND user_id = ?`,
        input.accountId ?? null,
        input.categoryId ?? null,
        amount,
        currencyCode,
        input.transactionType.trim(),
        input.description.trim(),
        input.merchant?.trim() || null,
        input.reference?.trim() || null,
        transactionDate,
        input.notes?.trim() || null,
        now,
        transactionId,
        userId,
      );
      await this.incrementLocalUpdateCounter(userId);
    });

    const row = await this.database.getFirstAsync<Record<string, unknown>>(
      'SELECT * FROM transactions WHERE id = ? AND user_id = ?',
      transactionId,
      userId,
    );
    if (!row) throw new Error('Transaction not found for this user.');
    return mapTransaction(row);
  }

  async deleteTransaction(userId: string, transactionId: string): Promise<void> {
    await this.database.withTransactionAsync(async () => {
      await this.requireOwnedRecord('transactions', userId, transactionId);
      await this.database.runAsync(
        `UPDATE transactions SET is_deleted = 1, sync_status = 'LOCAL_ONLY',
         sync_version = sync_version + 1, local_updated_at = ? WHERE id = ? AND user_id = ?`,
        nowUtc(),
        transactionId,
        userId,
      );
      await this.incrementLocalUpdateCounter(userId);
    });
  }

  async listTransactions(userId: string, limit = 100): Promise<LocalTransaction[]> {
    if (!Number.isInteger(limit) || limit < 1 || limit > 500) throw new Error('Limit must be between 1 and 500.');
    const rows = await this.database.getAllAsync<Record<string, unknown>>(
      `SELECT * FROM transactions WHERE user_id = ? AND is_deleted = 0
       ORDER BY transaction_date DESC, local_updated_at DESC LIMIT ?`,
      userId,
      limit,
    );
    return rows.map(mapTransaction);
  }

  async getSyncMetadata(userId: string): Promise<LocalSyncMetadata | null> {
    const row = await this.database.getFirstAsync<Record<string, unknown>>(
      'SELECT * FROM sync_metadata WHERE user_id = ?',
      userId,
    );
    if (!row) return null;
    return {
      userId: String(row.user_id),
      lastPullCursor: row.last_pull_cursor == null ? null : String(row.last_pull_cursor),
      serverVersion: Number(row.server_version),
      lastSyncAt: row.last_sync_at == null ? null : String(row.last_sync_at),
      localUpdateCounter: Number(row.local_update_counter),
    };
  }

  async clearUserData(userId: string): Promise<void> {
    await this.database.runAsync('DELETE FROM users WHERE id = ?', userId);
  }

  private async requireUser(userId: string): Promise<void> {
    const user = await this.database.getFirstAsync<{ id: string }>('SELECT id FROM users WHERE id = ?', userId);
    if (!user) throw new Error('Local user profile not found.');
  }

  private async incrementLocalUpdateCounter(userId: string): Promise<void> {
    await this.database.runAsync(
      'UPDATE sync_metadata SET local_update_counter = local_update_counter + 1 WHERE user_id = ?',
      userId,
    );
  }

  private async requireOwnedRecord(table: 'accounts' | 'categories' | 'transactions', userId: string, recordId: string): Promise<void> {
    const row = await this.database.getFirstAsync<{ id: string }>(
      `SELECT id FROM ${table} WHERE id = ? AND user_id = ? AND is_deleted = 0`,
      recordId,
      userId,
    );
    if (!row) throw new Error('Record not found for this user.');
  }
}
