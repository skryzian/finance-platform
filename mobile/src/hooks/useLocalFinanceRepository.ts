import { useSQLiteContext } from 'expo-sqlite';

import { LocalFinanceRepository } from '../repositories/localFinanceRepository';

export function useLocalFinanceRepository(): LocalFinanceRepository {
  return new LocalFinanceRepository(useSQLiteContext());
}
