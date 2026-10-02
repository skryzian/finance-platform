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
  name: string;
  categoryType: 'INCOME' | 'EXPENSE';
  parentId: string | null;
  syncStatus: LocalSyncStatus;
  localUpdatedAt: string;
};

export type LocalTransactionInput = {
  accountId?: string | null;
  categoryId?: string | null;
  amount: string;
  currencyCode: string;
  transactionType: string;
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
