export type LocalSyncStatus = 'LOCAL_ONLY' | 'SYNCED' | 'CONFLICT';

export type LocalUserProfileInput = {
  id?: string;
  remoteUserId?: string | null;
  baseCurrency: string;
  countryCode: string;
  timezone: string;
  locale: string;
};

export type LocalUserProfile = LocalUserProfileInput & {
  id: string;
  createdAt: string;
  updatedAt: string;
};

export type LocalAccountInput = {
  name: string;
  accountType: string;
  institution?: string | null;
  currencyCode: string;
  openingBalance: string;
  currentBalance: string;
  accountTimezone?: string | null;
  status?: string;
};

export type LocalAccount = LocalAccountInput & {
  id: string;
  userId: string;
  remoteId: string | null;
  syncStatus: LocalSyncStatus;
  syncVersion: number;
  localUpdatedAt: string;
  serverUpdatedAt: string | null;
  lastSyncedAt: string | null;
};

export type LocalCategory = {
  id: string;
  userId: string;
  remoteId: string | null;
  name: string;
  categoryType: 'INCOME' | 'EXPENSE';
  parentId: string | null;
  syncStatus: LocalSyncStatus;
  syncVersion: number;
  localUpdatedAt: string;
  serverUpdatedAt: string | null;
  lastSyncedAt: string | null;
};

export type LocalTransactionInput = {
  accountId?: string | null;
  transferAccountId?: string | null;
  categoryId?: string | null;
  amount: string;
  currencyCode: string;
  transactionType: 'INCOME' | 'EXPENSE' | 'TRANSFER';
  description: string;
  merchant?: string | null;
  reference?: string | null;
  transactionDate: string;
  notes?: string | null;
};

export type LocalTransaction = LocalTransactionInput & {
  id: string;
  operationId: string;
  userId: string;
  remoteId: string | null;
  source: string;
  status: string;
  syncStatus: LocalSyncStatus;
  syncVersion: number;
  localUpdatedAt: string;
  serverUpdatedAt: string | null;
  lastSyncedAt: string | null;
};

export type LocalSyncMetadata = {
  userId: string;
  lastPullCursor: string | null;
  serverVersion: number;
  lastSyncAt: string | null;
  localUpdateCounter: number;
};

export type LocalSyncPushResult = {
  entity_type: 'account' | 'category' | 'transaction';
  local_id: string;
  status: 'APPLIED' | 'CONFLICT' | 'REJECTED';
  remote_id?: number | null;
  server_version?: number | null;
  server_data?: Record<string, unknown> | null;
  message?: string | null;
};

export type LocalSyncEvent = {
  version: number;
  entity_type: 'account' | 'category' | 'transaction';
  entity_id: string;
  operation: 'UPSERT' | 'DELETE';
  payload: Record<string, unknown>;
  created_at: string;
};

export type LocalSyncChanges = {
  accounts: Array<LocalAccount & { isDeleted: boolean }>;
  categories: Array<LocalCategory & { isDeleted: boolean }>;
  transactions: Array<LocalTransaction & { isDeleted: boolean }>;
};

export type LocalSyncConflict = {
  id: string;
  entityType: 'account' | 'category' | 'transaction';
  entityId: string;
  serverVersion: number | null;
  serverPayload: Record<string, unknown>;
  createdAt: string;
};
