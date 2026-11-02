import * as Crypto from 'expo-crypto';
import type { SQLiteDatabase } from 'expo-sqlite';

import type {
  LocalAccount,
  LocalAccountInput,
  LocalCategory,
  LocalSyncChanges,
  LocalSyncConflict,
  LocalSyncEvent,
  LocalSyncMetadata,
  LocalSyncPushResult,
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
    remoteId: row.remote_id == null ? null : String(row.remote_id),
    name: String(row.name),
    categoryType: row.category_type as LocalCategory['categoryType'],
    parentId: row.parent_id == null ? null : String(row.parent_id),
    syncStatus: row.sync_status as LocalCategory['syncStatus'],
    syncVersion: Number(row.sync_version),
    localUpdatedAt: String(row.local_updated_at),
    serverUpdatedAt: row.server_updated_at == null ? null : String(row.server_updated_at),
    lastSyncedAt: row.last_synced_at == null ? null : String(row.last_synced_at),
  };
}

function mapTransaction(row: Record<string, unknown>): LocalTransaction {
  return {
    id: String(row.id),
    operationId: String(row.operation_id),
    userId: String(row.user_id),
    remoteId: row.remote_id == null ? null : String(row.remote_id),
    accountId: row.account_id == null ? null : String(row.account_id),
    transferAccountId: row.transfer_account_id == null ? null : String(row.transfer_account_id),
    categoryId: row.category_id == null ? null : String(row.category_id),
    amount: String(row.amount),
    currencyCode: String(row.currency_code),
    transactionType: String(row.transaction_type) as LocalTransaction['transactionType'],
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
         sync_status = 'LOCAL_ONLY', local_updated_at = ?, is_deleted = 0
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
         local_updated_at = ? WHERE id = ? AND user_id = ?`,
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
    this.validateTransactionShape(input);
    const id = Crypto.randomUUID();
    const now = nowUtc();

    await this.database.withTransactionAsync(async () => {
      await this.validateTransactionReferences(userId, input);
      await this.database.runAsync(
        `INSERT INTO transactions (
          id, operation_id, user_id, account_id, transfer_account_id, category_id, amount, currency_code,
          transaction_type, description, merchant, reference, transaction_date, notes,
          source, status, sync_status, local_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'MANUAL', 'CONFIRMED', 'LOCAL_ONLY', ?)`,
        id,
        id,
        userId,
        input.accountId ?? null,
        input.transferAccountId ?? null,
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
    this.validateTransactionShape(input);
    const now = nowUtc();

    await this.database.withTransactionAsync(async () => {
      await this.requireOwnedRecord('transactions', userId, transactionId);
      await this.validateTransactionReferences(userId, input);
      await this.database.runAsync(
        `UPDATE transactions SET
          account_id = ?, transfer_account_id = ?, category_id = ?, amount = ?, currency_code = ?, transaction_type = ?,
          description = ?, merchant = ?, reference = ?, transaction_date = ?, notes = ?,
          sync_status = 'LOCAL_ONLY',
          local_updated_at = ?, is_deleted = 0
         WHERE id = ? AND user_id = ?`,
        input.accountId ?? null,
        input.transferAccountId ?? null,
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
         local_updated_at = ? WHERE id = ? AND user_id = ?`,
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

  async getPendingSyncChanges(userId: string): Promise<LocalSyncChanges> {
    await this.requireUser(userId);
    const [accountRows, categoryRows, transactionRows] = await Promise.all([
      this.database.getAllAsync<Record<string, unknown>>(
        "SELECT * FROM accounts WHERE user_id = ? AND sync_status = 'LOCAL_ONLY' ORDER BY local_updated_at, id",
        userId,
      ),
      this.database.getAllAsync<Record<string, unknown>>(
        "SELECT * FROM categories WHERE user_id = ? AND sync_status = 'LOCAL_ONLY' ORDER BY local_updated_at, id",
        userId,
      ),
      this.database.getAllAsync<Record<string, unknown>>(
        "SELECT * FROM transactions WHERE user_id = ? AND sync_status = 'LOCAL_ONLY' ORDER BY local_updated_at, id",
        userId,
      ),
    ]);
    return {
      accounts: accountRows.map((row) => ({ ...mapAccount(row), isDeleted: Number(row.is_deleted) === 1 })),
      categories: categoryRows.map((row) => ({ ...mapCategory(row), isDeleted: Number(row.is_deleted) === 1 })),
      transactions: transactionRows.map((row) => ({ ...mapTransaction(row), isDeleted: Number(row.is_deleted) === 1 })),
    };
  }

  async listSyncConflicts(userId: string): Promise<LocalSyncConflict[]> {
    const rows = await this.database.getAllAsync<Record<string, unknown>>(
      'SELECT * FROM sync_conflicts WHERE user_id = ? ORDER BY created_at DESC',
      userId,
    );
    return rows.map((row) => ({
      id: String(row.id),
      entityType: row.entity_type as LocalSyncConflict['entityType'],
      entityId: String(row.entity_id),
      serverVersion: row.server_version == null ? null : Number(row.server_version),
      serverPayload: JSON.parse(String(row.server_payload)) as Record<string, unknown>,
      createdAt: String(row.created_at),
    }));
  }

  async resolveSyncConflict(
    userId: string,
    conflictId: string,
    resolution: 'SERVER' | 'LOCAL',
  ): Promise<void> {
    await this.database.withTransactionAsync(async () => {
      const conflictRow = await this.database.getFirstAsync<Record<string, unknown>>(
        'SELECT * FROM sync_conflicts WHERE id = ? AND user_id = ?',
        conflictId,
        userId,
      );
      if (!conflictRow) throw new Error('Sync conflict not found for this user.');
      const entityType = String(conflictRow.entity_type) as LocalSyncConflict['entityType'];
      const entityId = String(conflictRow.entity_id);
      const serverVersion = conflictRow.server_version == null ? null : Number(conflictRow.server_version);
      const saved = JSON.parse(String(conflictRow.server_payload)) as Record<string, unknown>;
      const nested = saved.server_data;
      const serverData = nested && typeof nested === 'object'
        ? nested as Record<string, unknown>
        : saved;

      if (resolution === 'LOCAL') {
        if (entityType === 'transaction') {
          throw new Error('Synced ledger transactions are immutable. Use the server version and record a reversal if needed.');
        }
        if (serverVersion == null) throw new Error('The server version is unavailable; this conflict cannot be retried safely.');
        const table = entityType === 'account' ? 'accounts' : 'categories';
        await this.database.runAsync(
          `UPDATE ${table} SET sync_status = 'LOCAL_ONLY', sync_version = ?, local_updated_at = ?
           WHERE id = ? AND user_id = ?`,
          serverVersion,
          nowUtc(),
          entityId,
          userId,
        );
        await this.database.runAsync('DELETE FROM sync_conflicts WHERE id = ? AND user_id = ?', conflictId, userId);
        return;
      }

      if (entityType === 'account') {
        if (serverData.id == null || serverData.name == null || serverData.currency_code == null) {
          throw new Error('The server account snapshot is incomplete.');
        }
        const openingBalance = String(serverData.opening_balance);
        await this.database.runAsync(
          `UPDATE accounts SET remote_id = ?, name = ?, account_type = ?, institution = ?,
           currency_code = ?, opening_balance = ?, current_balance = ?, status = ?,
           sync_status = 'SYNCED', sync_version = ?, server_updated_at = ?, last_synced_at = ?
           WHERE id = ? AND user_id = ?`,
          String(serverData.id),
          String(serverData.name),
          String(serverData.account_type),
          serverData.institution == null ? null : String(serverData.institution),
          String(serverData.currency_code),
          openingBalance,
          serverData.current_balance == null ? openingBalance : String(serverData.current_balance),
          serverData.is_active === false ? 'ARCHIVED' : 'ACTIVE',
          Number(serverData.sync_version ?? serverVersion ?? 0),
          typeof serverData.updated_at === 'string' ? serverData.updated_at : nowUtc(),
          nowUtc(),
          entityId,
          userId,
        );
      } else if (entityType === 'category') {
        if (serverData.id == null || serverData.name == null || serverData.category_type == null) {
          throw new Error('The server category snapshot is incomplete.');
        }
        await this.database.runAsync(
          `UPDATE categories SET remote_id = ?, name = ?, category_type = ?,
           sync_status = 'SYNCED', sync_version = ?, server_updated_at = ?, last_synced_at = ?
           WHERE id = ? AND user_id = ?`,
          String(serverData.id),
          String(serverData.name),
          String(serverData.category_type),
          Number(serverData.sync_version ?? serverVersion ?? 0),
          typeof serverData.created_at === 'string' ? serverData.created_at : nowUtc(),
          nowUtc(),
          entityId,
          userId,
        );
      } else {
        await this.applyServerTransaction(userId, entityId, serverData, nowUtc());
      }
      await this.database.runAsync('DELETE FROM sync_conflicts WHERE id = ? AND user_id = ?', conflictId, userId);
    });
  }

  async applySyncPushResults(userId: string, results: LocalSyncPushResult[]): Promise<void> {
    const syncedAt = nowUtc();
    await this.database.withTransactionAsync(async () => {
      for (const result of results) {
        const table = result.entity_type === 'account'
          ? 'accounts'
          : result.entity_type === 'category'
            ? 'categories'
            : 'transactions';
        if (result.status === 'REJECTED') continue;
        if (result.status === 'APPLIED') {
          await this.database.runAsync(
            `UPDATE ${table} SET remote_id = ?, sync_status = 'SYNCED',
             sync_version = ?, server_updated_at = ?, last_synced_at = ?
             WHERE id = ? AND user_id = ?`,
            result.remote_id == null ? null : String(result.remote_id),
            result.server_version ?? 0,
            syncedAt,
            syncedAt,
            result.local_id,
            userId,
          );
          await this.database.runAsync(
            'DELETE FROM sync_conflicts WHERE user_id = ? AND entity_type = ? AND entity_id = ?',
            userId,
            result.entity_type,
            result.local_id,
          );
          continue;
        }
        await this.database.runAsync(
          `UPDATE ${table} SET sync_status = 'CONFLICT' WHERE id = ? AND user_id = ?`,
          result.local_id,
          userId,
        );
        await this.saveConflict(
          userId,
          result.entity_type,
          result.local_id,
          result.server_version ?? null,
          {
            server_data: result.server_data ?? null,
            message: result.message ?? 'The server reported a sync conflict.',
          },
        );
      }
    });
  }

  async applySyncPull(
    userId: string,
    events: LocalSyncEvent[],
    cursor: number,
    serverVersion: number,
  ): Promise<void> {
    const syncedAt = nowUtc();
    await this.database.withTransactionAsync(async () => {
      for (const event of events) {
        const data = event.payload;
        if (event.entity_type === 'account') {
          const remoteId = String(data.id);
          const clientId = typeof data.client_id === 'string' ? data.client_id : null;
          let row = await this.database.getFirstAsync<Record<string, unknown>>(
            clientId
              ? 'SELECT * FROM accounts WHERE user_id = ? AND (remote_id = ? OR id = ?) LIMIT 1'
              : 'SELECT * FROM accounts WHERE user_id = ? AND remote_id = ? LIMIT 1',
            ...(clientId ? [userId, remoteId, clientId] : [userId, remoteId]),
          );
          if (row && (row.sync_status === 'LOCAL_ONLY' || row.sync_status === 'CONFLICT')) {
            await this.database.runAsync(
              "UPDATE accounts SET sync_status = 'CONFLICT' WHERE id = ? AND user_id = ?",
              String(row.id),
              userId,
            );
            await this.saveConflict(userId, 'account', String(row.id), Number(data.sync_version), data);
            continue;
          }
          const localId = row ? String(row.id) : clientId ?? Crypto.randomUUID();
          const openingBalance = String(data.opening_balance);
          const serverUpdatedAt = typeof data.updated_at === 'string' ? data.updated_at : syncedAt;
          const accountStatus = data.is_active === false ? 'ARCHIVED' : 'ACTIVE';
          await this.database.runAsync(
            `INSERT INTO accounts (
              id, user_id, remote_id, name, account_type, institution, currency_code,
              opening_balance, current_balance, status, sync_status, sync_version,
              local_updated_at, server_updated_at, last_synced_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
              remote_id = excluded.remote_id, name = excluded.name,
              account_type = excluded.account_type, institution = excluded.institution,
              currency_code = excluded.currency_code, opening_balance = excluded.opening_balance,
              current_balance = excluded.current_balance, status = excluded.status,
              sync_status = 'SYNCED', sync_version = excluded.sync_version,
              local_updated_at = excluded.local_updated_at,
              server_updated_at = excluded.server_updated_at, last_synced_at = excluded.last_synced_at`,
            localId,
            userId,
            remoteId,
            String(data.name),
            String(data.account_type),
            data.institution == null ? null : String(data.institution),
            String(data.currency_code),
            openingBalance,
            data.current_balance == null ? openingBalance : String(data.current_balance),
            accountStatus,
            Number(data.sync_version ?? 0),
            syncedAt,
            serverUpdatedAt,
            syncedAt,
          );
          await this.database.runAsync(
            'DELETE FROM sync_conflicts WHERE user_id = ? AND entity_type = ? AND entity_id = ?',
            userId,
            'account',
            localId,
          );
          continue;
        }

        if (event.entity_type === 'category') {
          const remoteId = String(data.id);
          const clientId = typeof data.client_id === 'string' ? data.client_id : null;
          const row = await this.database.getFirstAsync<Record<string, unknown>>(
            clientId
              ? 'SELECT * FROM categories WHERE user_id = ? AND (remote_id = ? OR id = ?) LIMIT 1'
              : 'SELECT * FROM categories WHERE user_id = ? AND remote_id = ? LIMIT 1',
            ...(clientId ? [userId, remoteId, clientId] : [userId, remoteId]),
          );
          if (row && (row.sync_status === 'LOCAL_ONLY' || row.sync_status === 'CONFLICT')) {
            await this.database.runAsync(
              "UPDATE categories SET sync_status = 'CONFLICT' WHERE id = ? AND user_id = ?",
              String(row.id),
              userId,
            );
            await this.saveConflict(userId, 'category', String(row.id), Number(data.sync_version), data);
            continue;
          }
          const localId = row ? String(row.id) : clientId ?? Crypto.randomUUID();
          const serverUpdatedAt = typeof data.created_at === 'string' ? data.created_at : syncedAt;
          await this.database.runAsync(
            `INSERT INTO categories (
              id, user_id, remote_id, name, category_type, sync_status, sync_version,
              local_updated_at, server_updated_at, last_synced_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, 'SYNCED', ?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
              remote_id = excluded.remote_id, name = excluded.name,
              category_type = excluded.category_type, sync_status = 'SYNCED',
              sync_version = excluded.sync_version, local_updated_at = excluded.local_updated_at,
              server_updated_at = excluded.server_updated_at, last_synced_at = excluded.last_synced_at`,
            localId,
            userId,
            remoteId,
            String(data.name),
            String(data.category_type),
            Number(data.sync_version ?? 0),
            syncedAt,
            serverUpdatedAt,
            syncedAt,
          );
          await this.database.runAsync(
            'DELETE FROM sync_conflicts WHERE user_id = ? AND entity_type = ? AND entity_id = ?',
            userId,
            'category',
            localId,
          );
          continue;
        }

        const remoteId = String(data.id);
        const operationId = String(data.idempotency_key);
        const row = await this.database.getFirstAsync<Record<string, unknown>>(
          'SELECT * FROM transactions WHERE user_id = ? AND (remote_id = ? OR operation_id = ?) LIMIT 1',
          userId,
          remoteId,
          operationId,
        );
        if (row && (
          row.sync_status === 'LOCAL_ONLY'
          || row.sync_status === 'CONFLICT'
          || Number(row.is_deleted) === 1
        )) {
          await this.database.runAsync(
            "UPDATE transactions SET sync_status = 'CONFLICT' WHERE id = ? AND user_id = ?",
            String(row.id),
            userId,
          );
          await this.saveConflict(userId, 'transaction', String(row.id), null, data);
          continue;
        }
        const account = await this.database.getFirstAsync<{ id: string }>(
          'SELECT id FROM accounts WHERE user_id = ? AND remote_id = ?',
          userId,
          String(data.account_id),
        );
        const transferAccount = data.transfer_account_id == null
          ? null
          : await this.database.getFirstAsync<{ id: string }>(
            'SELECT id FROM accounts WHERE user_id = ? AND remote_id = ?',
            userId,
            String(data.transfer_account_id),
          );
        const category = data.category_id == null
          ? null
          : await this.database.getFirstAsync<{ id: string }>(
            'SELECT id FROM categories WHERE user_id = ? AND remote_id = ?',
            userId,
            String(data.category_id),
          );
        if (!account || (data.transfer_account_id != null && !transferAccount) || (data.category_id != null && !category)) {
          throw new Error(`Cannot apply pulled transaction ${remoteId}: a referenced finance record is missing.`);
        }
        const localId = row ? String(row.id) : operationId;
        await this.database.runAsync(
          `INSERT INTO transactions (
            id, operation_id, user_id, remote_id, account_id, transfer_account_id, category_id,
            amount, currency_code, transaction_type, description, notes, transaction_date,
            source, status, sync_status, sync_version, local_updated_at, server_updated_at,
            last_synced_at, is_deleted
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYNC', 'CONFIRMED', 'SYNCED', 0, ?, ?, ?, 0)
          ON CONFLICT(id) DO UPDATE SET
            remote_id = excluded.remote_id, account_id = excluded.account_id,
            transfer_account_id = excluded.transfer_account_id, category_id = excluded.category_id,
            amount = excluded.amount, currency_code = excluded.currency_code,
            transaction_type = excluded.transaction_type, description = excluded.description,
            notes = excluded.notes, transaction_date = excluded.transaction_date,
            sync_status = 'SYNCED', local_updated_at = excluded.local_updated_at,
            server_updated_at = excluded.server_updated_at, last_synced_at = excluded.last_synced_at`,
          localId,
          operationId,
          userId,
          remoteId,
          account.id,
          transferAccount?.id ?? null,
          category?.id ?? null,
          String(data.amount),
          String(data.currency_code),
          String(data.transaction_type),
          String(data.description),
          data.notes == null ? null : String(data.notes),
          String(data.transaction_date),
          syncedAt,
          event.created_at,
          syncedAt,
        );
        const accountBalances = data.account_balances;
        if (accountBalances && typeof accountBalances === 'object') {
          for (const [serverAccountId, balance] of Object.entries(accountBalances)) {
            await this.database.runAsync(
              'UPDATE accounts SET current_balance = ? WHERE user_id = ? AND remote_id = ?',
              String(balance),
              userId,
              serverAccountId,
            );
          }
        }
        await this.database.runAsync(
          'DELETE FROM sync_conflicts WHERE user_id = ? AND entity_type = ? AND entity_id = ?',
          userId,
          'transaction',
          localId,
        );
      }
      await this.database.runAsync(
        `UPDATE sync_metadata SET last_pull_cursor = ?, server_version = ?, last_sync_at = ?
         WHERE user_id = ?`,
        String(cursor),
        serverVersion,
        syncedAt,
        userId,
      );
    });
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

  private async saveConflict(
    userId: string,
    entityType: string,
    entityId: string,
    serverVersion: number | null,
    serverPayload: Record<string, unknown>,
  ): Promise<void> {
    await this.database.runAsync(
      `INSERT INTO sync_conflicts (id, user_id, entity_type, entity_id, server_version, server_payload, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(user_id, entity_type, entity_id) DO UPDATE SET
         server_version = excluded.server_version,
         server_payload = excluded.server_payload,
         created_at = excluded.created_at`,
      Crypto.randomUUID(),
      userId,
      entityType,
      entityId,
      serverVersion,
      JSON.stringify(serverPayload),
      nowUtc(),
    );
  }

  private async applyServerTransaction(
    userId: string,
    localId: string,
    data: Record<string, unknown>,
    syncedAt: string,
  ): Promise<void> {
    if (data.id == null || data.idempotency_key == null || data.account_id == null) {
      throw new Error('The server transaction snapshot is incomplete.');
    }
    const account = await this.database.getFirstAsync<{ id: string }>(
      'SELECT id FROM accounts WHERE user_id = ? AND remote_id = ?',
      userId,
      String(data.account_id),
    );
    const transferAccount = data.transfer_account_id == null
      ? null
      : await this.database.getFirstAsync<{ id: string }>(
        'SELECT id FROM accounts WHERE user_id = ? AND remote_id = ?',
        userId,
        String(data.transfer_account_id),
      );
    const category = data.category_id == null
      ? null
      : await this.database.getFirstAsync<{ id: string }>(
        'SELECT id FROM categories WHERE user_id = ? AND remote_id = ?',
        userId,
        String(data.category_id),
      );
    if (!account || (data.transfer_account_id != null && !transferAccount) || (data.category_id != null && !category)) {
      throw new Error('The server transaction references finance records that are not on this device.');
    }
    await this.database.runAsync(
      `UPDATE transactions SET remote_id = ?, account_id = ?, transfer_account_id = ?, category_id = ?,
       amount = ?, currency_code = ?, transaction_type = ?, description = ?, notes = ?,
       transaction_date = ?, source = 'SYNC', sync_status = 'SYNCED', server_updated_at = ?,
       last_synced_at = ?, is_deleted = 0
       WHERE id = ? AND user_id = ?`,
      String(data.id),
      account.id,
      transferAccount?.id ?? null,
      category?.id ?? null,
      String(data.amount),
      String(data.currency_code),
      String(data.transaction_type),
      String(data.description),
      data.notes == null ? null : String(data.notes),
      String(data.transaction_date),
      syncedAt,
      syncedAt,
      localId,
      userId,
    );
    const accountBalances = data.account_balances;
    if (accountBalances && typeof accountBalances === 'object') {
      for (const [serverAccountId, balance] of Object.entries(accountBalances)) {
        await this.database.runAsync(
          'UPDATE accounts SET current_balance = ? WHERE user_id = ? AND remote_id = ?',
          String(balance),
          userId,
          serverAccountId,
        );
      }
    }
  }

  private validateTransactionShape(input: LocalTransactionInput): void {
    if (!input.accountId) throw new Error('Transactions must reference a local account.');
    if (input.transactionType === 'TRANSFER') {
      if (!input.transferAccountId || input.categoryId) {
        throw new Error('Transfers require a destination account and cannot have a category.');
      }
      if (input.accountId && input.accountId === input.transferAccountId) {
        throw new Error('Transfer source and destination must differ.');
      }
      return;
    }
    if (input.transactionType !== 'INCOME' && input.transactionType !== 'EXPENSE') {
      throw new Error('Transaction type must be income, expense, or transfer.');
    }
    if (!input.categoryId || input.transferAccountId) {
      throw new Error('Income and expenses require a category and cannot have a transfer destination.');
    }
  }

  private async validateTransactionReferences(
    userId: string,
    input: LocalTransactionInput,
  ): Promise<void> {
    this.validateTransactionShape(input);
    const accountId = input.accountId;
    if (!accountId) throw new Error('Transactions must reference a local account.');
    const source = await this.database.getFirstAsync<{ currency_code: string; status: string }>(
      'SELECT currency_code, status FROM accounts WHERE id = ? AND user_id = ? AND is_deleted = 0',
      accountId,
      userId,
    );
    if (!source || source.status !== 'ACTIVE') throw new Error('Source account is not active for this user.');
    if (source.currency_code !== validateCurrencyCode(input.currencyCode)) {
      throw new Error('Transaction currency must match its account.');
    }

    if (input.transactionType === 'TRANSFER') {
      const transferAccountId = input.transferAccountId;
      if (!transferAccountId) throw new Error('Transfers require a destination account.');
      const destination = await this.database.getFirstAsync<{ currency_code: string; status: string }>(
        'SELECT currency_code, status FROM accounts WHERE id = ? AND user_id = ? AND is_deleted = 0',
        transferAccountId,
        userId,
      );
      if (!destination || destination.status !== 'ACTIVE') {
        throw new Error('Destination account is not active for this user.');
      }
      if (destination.currency_code !== source.currency_code) {
        throw new Error('Transfers between different currencies are not supported.');
      }
    } else {
      const categoryId = input.categoryId;
      if (!categoryId) throw new Error('Income and expenses require a category.');
      const category = await this.database.getFirstAsync<{ category_type: string }>(
        'SELECT category_type FROM categories WHERE id = ? AND user_id = ? AND is_deleted = 0',
        categoryId,
        userId,
      );
      if (!category || category.category_type !== input.transactionType) {
        throw new Error('Select a category matching the transaction type.');
      }
    }
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
