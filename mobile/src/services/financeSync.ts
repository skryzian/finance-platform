import type {
  LocalSyncEvent,
  LocalSyncPushResult,
  LocalUserProfileInput,
} from '../types/offline';
import { LocalFinanceRepository } from '../repositories/localFinanceRepository';

type TokenPair = {
  access_token: string;
  refresh_token: string;
};

type AuthenticatedUser = {
  id: number;
  currency: string;
  country: string;
  timezone: string;
  locale: string;
};

type SyncResponse = {
  results: LocalSyncPushResult[];
};

type PullResponse = {
  cursor: number;
  events: LocalSyncEvent[];
};

export type FinanceSyncLogin = {
  tokens: TokenPair;
  userId: string;
};

export type FinanceSyncSummary = {
  pushed: number;
  pulled: number;
  conflicts: number;
  rejected: number;
  cursor: number;
};

function normalizedBaseUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error('Enter a valid server URL, including http:// or https://.');
  }
  const isLocalDevelopmentHost = ['localhost', '127.0.0.1', '10.0.2.2'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && isLocalDevelopmentHost)) {
    throw new Error('Use HTTPS for remote servers. Plain HTTP is supported only for local development.');
  }
  return url.toString().replace(/\/+$/, '');
}

async function responseError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
  }
  return `Server request failed with HTTP ${response.status}.`;
}

export class FinanceSyncService {
  private readonly baseUrl: string;

  constructor(
    private readonly repository: LocalFinanceRepository,
    baseUrl: string,
  ) {
    this.baseUrl = normalizedBaseUrl(baseUrl);
  }

  async login(email: string, password: string): Promise<FinanceSyncLogin> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const tokens = await response.json() as TokenPair;
    const profileResponse = await fetch(`${this.baseUrl}/auth/me`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    if (!profileResponse.ok) throw new Error(await responseError(profileResponse));
    const profile = await profileResponse.json() as AuthenticatedUser;
    const profileInput: LocalUserProfileInput = {
      remoteUserId: String(profile.id),
      baseCurrency: profile.currency,
      countryCode: profile.country,
      timezone: profile.timezone,
      locale: profile.locale,
    };
    const localProfile = await this.repository.upsertUserProfile(profileInput);
    return { tokens, userId: localProfile.id };
  }

  async logout(accessToken: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) throw new Error(await responseError(response));
  }

  async synchronize(userId: string, accessToken: string): Promise<FinanceSyncSummary> {
    const initialChanges = await this.repository.getPendingSyncChanges(userId);
    const ordinaryAccounts = initialChanges.accounts.filter((account) => !account.isDeleted);
    const accountResults = await this.push({
      accounts: ordinaryAccounts.map((account) => ({
        client_id: account.id,
        ...(account.remoteId ? { remote_id: Number(account.remoteId) } : {}),
        base_version: account.syncVersion,
        is_deleted: false,
        name: account.name,
        account_type: account.accountType,
        institution: account.institution,
        currency_code: account.currencyCode,
        opening_balance: account.openingBalance,
      })),
      categories: initialChanges.categories.filter((category) => !category.isDeleted).map((category) => ({
        client_id: category.id,
        ...(category.remoteId ? { remote_id: Number(category.remoteId) } : {}),
        base_version: category.syncVersion,
        is_deleted: false,
        name: category.name,
        category_type: category.categoryType,
      })),
      transactions: [],
    }, accessToken, userId);

    const currentChanges = await this.repository.getPendingSyncChanges(userId);
    const accounts = new Map(
      [...await this.repository.listAccounts(userId), ...currentChanges.accounts]
        .map((account) => [account.id, account]),
    );
    const categories = new Map(
      [...await this.repository.listCategories(userId), ...currentChanges.categories]
        .map((category) => [category.id, category]),
    );
    const localTransactionResults: LocalSyncPushResult[] = [];
    const transactionInputs: Record<string, unknown>[] = [];
    for (const transaction of currentChanges.transactions) {
      if (transaction.isDeleted) {
        if (transaction.remoteId) {
          const sourceAccount = transaction.accountId ? accounts.get(transaction.accountId) : null;
          const transferAccount = transaction.transferAccountId
            ? accounts.get(transaction.transferAccountId)
            : null;
          const category = transaction.categoryId ? categories.get(transaction.categoryId) : null;
          const canResolveSnapshot = Boolean(
            sourceAccount?.remoteId
            && (!transaction.transferAccountId || transferAccount?.remoteId)
            && (!transaction.categoryId || category?.remoteId),
          );
          const serverData = canResolveSnapshot && sourceAccount?.remoteId
            ? {
              id: Number(transaction.remoteId),
              idempotency_key: transaction.operationId,
              account_id: Number(sourceAccount.remoteId),
              transfer_account_id: transferAccount?.remoteId ? Number(transferAccount.remoteId) : null,
              category_id: category?.remoteId ? Number(category.remoteId) : null,
              transaction_type: transaction.transactionType,
              amount: transaction.amount,
              currency_code: transaction.currencyCode,
              description: transaction.description,
              notes: transaction.notes,
              transaction_date: transaction.transactionDate,
            }
            : null;
          localTransactionResults.push({
            entity_type: 'transaction',
            local_id: transaction.id,
            status: 'CONFLICT',
            remote_id: Number(transaction.remoteId),
            server_data: serverData,
            message: 'A synced ledger transaction is immutable; record a reversal instead of deleting it.',
          });
        } else {
          localTransactionResults.push({
            entity_type: 'transaction',
            local_id: transaction.id,
            status: 'APPLIED',
            remote_id: null,
          });
        }
        continue;
      }
      const account = transaction.accountId ? accounts.get(transaction.accountId) : null;
      const category = transaction.categoryId ? categories.get(transaction.categoryId) : null;
      const transferAccount = transaction.transferAccountId
        ? accounts.get(transaction.transferAccountId)
        : null;
      if (!account || (transaction.transactionType !== 'TRANSFER' && !category)
        || (transaction.transactionType === 'TRANSFER' && !transferAccount)) {
        localTransactionResults.push({
          entity_type: 'transaction',
          local_id: transaction.id,
          status: 'REJECTED',
          message: 'The transaction references a missing local account or category.',
        });
        continue;
      }
      transactionInputs.push({
        local_id: transaction.id,
        idempotency_key: transaction.operationId,
        ...this.accountReference(account),
        ...(transferAccount ? { ...this.accountReference(transferAccount, 'transfer') } : {}),
        ...(category ? this.categoryReference(category) : {}),
        transaction_type: transaction.transactionType,
        amount: transaction.amount,
        currency_code: transaction.currencyCode,
        description: transaction.description,
        notes: transaction.notes,
        transaction_date: transaction.transactionDate,
      });
    }

    const transactionResults = await this.push({
      accounts: [],
      categories: [],
      transactions: transactionInputs,
    }, accessToken, userId);
    if (localTransactionResults.length > 0) {
      await this.repository.applySyncPushResults(userId, localTransactionResults);
    }

    const deletedAccounts = currentChanges.accounts.filter((account) => account.isDeleted);
    const deletionResults = await this.push({
      accounts: deletedAccounts.map((account) => ({
        client_id: account.id,
        ...(account.remoteId ? { remote_id: Number(account.remoteId) } : {}),
        base_version: account.syncVersion,
        is_deleted: true,
        name: account.name,
        account_type: account.accountType,
        institution: account.institution,
        currency_code: account.currencyCode,
        opening_balance: account.openingBalance,
      })),
      categories: [],
      transactions: [],
    }, accessToken, userId);

    let cursor = Number((await this.repository.getSyncMetadata(userId))?.lastPullCursor ?? 0);
    let pulled = 0;
    while (true) {
      const response = await fetch(
        `${this.baseUrl}/api/finance/sync/pull?cursor=${cursor}&limit=500`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) throw new Error(await responseError(response));
      const page = await response.json() as PullResponse;
      await this.repository.applySyncPull(userId, page.events, page.cursor, page.cursor);
      pulled += page.events.length;
      cursor = page.cursor;
      if (page.events.length < 500) break;
    }

    const allResults = [
      ...accountResults,
      ...transactionResults,
      ...deletionResults,
      ...localTransactionResults,
    ];
    return {
      pushed: allResults.filter((item) => item.status === 'APPLIED').length,
      pulled,
      conflicts: allResults.filter((item) => item.status === 'CONFLICT').length,
      rejected: allResults.filter((item) => item.status === 'REJECTED').length,
      cursor,
    };
  }

  private async push(
    payload: Record<string, unknown>,
    accessToken: string,
    userId: string,
  ): Promise<LocalSyncPushResult[]> {
    if (Object.values(payload).every((value) => Array.isArray(value) && value.length === 0)) return [];
    const response = await fetch(`${this.baseUrl}/api/finance/sync/push`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const result = await response.json() as SyncResponse;
    await this.repository.applySyncPushResults(userId, result.results);
    return result.results;
  }

  private accountReference(
    account: { id: string; remoteId: string | null },
    prefix: '' | 'transfer' = '',
  ): Record<string, unknown> {
    const field = prefix ? 'transfer_account' : 'account';
    return account.remoteId
      ? { [`${field}_remote_id`]: Number(account.remoteId) }
      : { [`${field}_client_id`]: account.id };
  }

  private categoryReference(category: { id: string; remoteId: string | null }): Record<string, unknown> {
    return category.remoteId
      ? { category_remote_id: Number(category.remoteId) }
      : { category_client_id: category.id };
  }
}
