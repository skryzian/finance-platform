'use client';

import { FormEvent, useCallback, useRef, useState } from 'react';
import { IntegrationNotificationsPanel } from './integration-notifications-panel';

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type Account = {
  id: number;
  name: string;
  account_type: string;
  currency_code: string;
  currency_source: 'PROVIDER' | 'USER_ENTERED';
  opening_balance: string;
  current_balance: string;
};

type Category = { id: number; name: string; category_type: 'INCOME' | 'EXPENSE' };
type Transaction = {
  id: number;
  transaction_type: 'INCOME' | 'EXPENSE' | 'TRANSFER';
  amount: string;
  currency_code: string;
  description: string;
  transaction_date: string;
};
type Budget = {
  id: number;
  name: string;
  amount: string;
  spent: string;
  currency_code: string;
  start_date: string;
  end_date: string;
};
type CurrencySummary = {
  currency_code: string;
  total_income: string;
  total_expenses: string;
  net_cash_flow: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
};
type MarketPrice = {
  id: number;
  symbol: string;
  asset_type: string;
  exchange: string | null;
  currency_code: string;
  currency_source: 'PROVIDER' | 'USER_ENTERED';
  price: string;
  effective_date: string;
  provider_key: string;
  data_state: string;
  retrieved_at: string;
};
type ExchangeRate = {
  id: number;
  base_currency: string;
  quote_currency: string;
  rate: string;
  effective_date: string;
  provider_key: string;
  data_state: string;
  retrieved_at: string;
};
type TokenResponse = { access_token: string; refresh_token: string };
type WorkspaceTab = 'accounts' | 'transactions' | 'budgets' | 'reports' | 'valuations' | 'integrations';

function currentMonthStart(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatAmount(amount: string, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(amount));
}

export function FinanceWorkspace() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [registerMode, setRegisterMode] = useState(false);
  const [accessToken, setAccessToken] = useState('');
  const [refreshToken, setRefreshToken] = useState('');
  const [tab, setTab] = useState<WorkspaceTab>('accounts');
  const [transactionType, setTransactionType] = useState<Transaction['transaction_type']>('EXPENSE');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [summary, setSummary] = useState<CurrencySummary[]>([]);
  const [marketPrices, setMarketPrices] = useState<MarketPrice[]>([]);
  const [exchangeRates, setExchangeRates] = useState<ExchangeRate[]>([]);
  const [startDate, setStartDate] = useState(currentMonthStart);
  const [endDate, setEndDate] = useState(today);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const refreshInFlight = useRef<Promise<TokenResponse> | null>(null);

  const apiRequest = useCallback(async function apiRequest<T>(
    path: string,
    init: RequestInit = {},
    tokenOverride = accessToken,
  ): Promise<T> {
    const send = (token: string) =>
      fetch(`${apiUrl}${path}`, {
        ...init,
        headers: {
          ...(init.body ? { 'Content-Type': 'application/json' } : {}),
          ...init.headers,
          Authorization: `Bearer ${token}`,
        },
      });

    let response = await send(tokenOverride);
    if (response.status === 401 && refreshToken) {
      if (!refreshInFlight.current) {
        refreshInFlight.current = (async () => {
          const refreshResponse = await fetch(`${apiUrl}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (!refreshResponse.ok) throw new Error('Your session expired. Sign in again.');
          return (await refreshResponse.json()) as TokenResponse;
        })();
      }
      try {
        const rotated = await refreshInFlight.current;
        setAccessToken(rotated.access_token);
        setRefreshToken(rotated.refresh_token);
        response = await send(rotated.access_token);
      } catch (caught) {
        setAccessToken('');
        setRefreshToken('');
        throw caught;
      } finally {
        refreshInFlight.current = null;
      }
    }

    const body = response.status === 204 ? undefined : await response.json();
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? String(body.detail) : 'Request failed.';
      throw new Error(detail);
    }
    return body as T;
  }, [accessToken, refreshToken]);

  async function loadWorkspace(token: string) {
    setLoading(true);
    setError('');
    try {
      const [accountRows, categoryRows, transactionRows, budgetRows] = await Promise.all([
        apiRequest<Account[]>('/api/finance/accounts', {}, token),
        apiRequest<Category[]>('/api/finance/categories', {}, token),
        apiRequest<Transaction[]>('/api/finance/transactions?limit=100', {}, token),
        apiRequest<Budget[]>('/api/finance/budgets', {}, token),
      ]);
      setAccounts(accountRows);
      setCategories(categoryRows);
      setTransactions(transactionRows);
      setBudgets(budgetRows);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load financial records.');
    } finally {
      setLoading(false);
    }
  }

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setNotice('');
    try {
      if (registerMode) {
        const registration = await fetch(`${apiUrl}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            first_name: firstName,
            last_name: lastName,
            email,
            password,
            country: 'KE',
          }),
        });
        if (!registration.ok) {
          const body = await registration.json();
          throw new Error(body.detail ?? 'Could not create your account.');
        }
      }
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const body = (await response.json()) as TokenResponse & { detail?: string };
      if (!response.ok) throw new Error(body.detail ?? 'Sign-in failed.');
      setAccessToken(body.access_token);
      setRefreshToken(body.refresh_token);
      setPassword('');
      setNotice(registerMode ? 'Account created.' : '');
      await loadWorkspace(body.access_token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to authenticate.');
    } finally {
      setLoading(false);
    }
  }

  async function submitJson<T>(path: string, payload: object): Promise<T> {
    return apiRequest<T>(path, { method: 'POST', body: JSON.stringify(payload) });
  }

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setNotice('');
    try {
      await submitJson('/api/finance/accounts', {
        name: form.get('name'),
        account_type: form.get('account_type'),
        currency_code: form.get('currency_code'),
        opening_balance: form.get('opening_balance') || '0',
      });
      formElement.reset();
      setNotice('Account created.');
      await loadWorkspace(accessToken);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create account.');
    }
  }

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await submitJson('/api/finance/categories', {
        name: form.get('name'),
        category_type: form.get('category_type'),
      });
      formElement.reset();
      setNotice('Category created.');
      await loadWorkspace(accessToken);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create category.');
    }
  }

  async function createTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const transactionType = String(form.get('transaction_type'));
    const accountId = Number(form.get('account_id'));
    const account = accounts.find((item) => item.id === accountId);
    if (!account) {
      setError('Select an account.');
      return;
    }
    const transactionDate = form.get('transaction_date');
    try {
      await submitJson('/api/finance/transactions', {
        idempotency_key: crypto.randomUUID(),
        account_id: accountId,
        ...(transactionType === 'TRANSFER' ? { transfer_account_id: Number(form.get('transfer_account_id')) } : {}),
        ...(transactionType !== 'TRANSFER' ? { category_id: Number(form.get('category_id')) } : {}),
        transaction_type: transactionType,
        amount: form.get('amount'),
        currency_code: account.currency_code,
        description: form.get('description'),
        transaction_date: new Date(String(transactionDate)).toISOString(),
      });
      formElement.reset();
      setNotice('Transaction recorded.');
      setTransactionType('EXPENSE');
      await loadWorkspace(accessToken);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not record transaction.');
    }
  }

  async function createBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await submitJson('/api/finance/budgets', {
        name: form.get('name'),
        category_id: Number(form.get('category_id')),
        amount: form.get('amount'),
        currency_code: form.get('currency_code'),
        start_date: form.get('start_date'),
        end_date: form.get('end_date'),
      });
      formElement.reset();
      setNotice('Budget created.');
      await loadWorkspace(accessToken);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create budget.');
    }
  }

  async function runReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
      const report = await apiRequest<{ by_currency: CurrencySummary[] }>(
        `/api/finance/reports/summary?${query.toString()}`,
      );
      setSummary(report.by_currency);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load report.');
    } finally {
      setLoading(false);
    }
  }

  async function refreshMarketPrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    setError('');
    setNotice('');
    try {
      await apiRequest<MarketPrice>('/api/markets/prices/refresh', {
        method: 'POST',
        body: JSON.stringify({
          symbol: form.get('symbol'),
          asset_type: form.get('asset_type'),
          currency_code: form.get('currency_code'),
          exchange: form.get('exchange') || null,
        }),
      });
      const symbol = String(form.get('symbol')).trim().toUpperCase();
      const query = new URLSearchParams({ symbol, limit: '100' });
      setMarketPrices(await apiRequest<MarketPrice[]>(`/api/markets/prices?${query}`));
      setNotice(`Stored the sourced daily close history for ${symbol}. This is historical data, not a live quote.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not refresh market history.');
    } finally {
      setLoading(false);
    }
  }

  async function refreshExchangeRates(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const baseCurrency = String(form.get('base_currency')).trim().toUpperCase();
      const quoteCurrency = String(form.get('quote_currency')).trim().toUpperCase();
      await apiRequest<ExchangeRate[]>('/api/markets/exchange-rates/refresh', {
        method: 'POST',
        body: JSON.stringify({
          base_currency: baseCurrency,
          quote_currency: quoteCurrency,
          start_date: form.get('start_date'),
          end_date: form.get('end_date'),
        }),
      });
      const query = new URLSearchParams({
        base_currency: baseCurrency,
        quote_currency: quoteCurrency,
        start_date: String(form.get('start_date')),
        end_date: String(form.get('end_date')),
        limit: '500',
      });
      setExchangeRates(await apiRequest<ExchangeRate[]>(`/api/markets/exchange-rates?${query}`));
      setNotice(`Stored dated ECB reference rates for ${baseCurrency}/${quoteCurrency}. No FX conversion is applied automatically.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not refresh exchange-rate history.');
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } catch {
      setError('The session could not be revoked; local sign-in state was cleared.');
    } finally {
      setAccessToken('');
      setRefreshToken('');
      setAccounts([]);
      setCategories([]);
      setTransactions([]);
      setBudgets([]);
      setSummary([]);
      setMarketPrices([]);
      setExchangeRates([]);
    }
  }

  if (!accessToken) {
    return (
      <section className="card mx-auto max-w-xl">
        <h2 className="text-xl font-semibold">{registerMode ? 'Create your account' : 'Sign in to your finances'}</h2>
        <p className="mt-2 text-sm text-slate-600">Financial records are private and require authentication.</p>
        <form onSubmit={authenticate} className="mt-5 grid gap-3">
          {registerMode && (
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1 text-sm">First name<input name="first_name" required value={firstName} onChange={(event) => setFirstName(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <label className="grid gap-1 text-sm">Last name<input name="last_name" required value={lastName} onChange={(event) => setLastName(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            </div>
          )}
          <label className="grid gap-1 text-sm">Email<input autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="grid gap-1 text-sm">Password<input autoComplete={registerMode ? 'new-password' : 'current-password'} type="password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <button disabled={loading} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white disabled:opacity-60">{loading ? 'Please wait…' : registerMode ? 'Create account' : 'Sign in'}</button>
        </form>
        <button type="button" onClick={() => setRegisterMode(!registerMode)} className="mt-4 text-sm font-medium text-brand-700">
          {registerMode ? 'Already registered? Sign in' : 'New here? Create an account'}
        </button>
        {error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
      </section>
    );
  }

  const tabs: { id: WorkspaceTab; label: string }[] = [
    { id: 'accounts', label: 'Accounts' },
    { id: 'transactions', label: 'Transactions' },
    { id: 'budgets', label: 'Budgets' },
    { id: 'reports', label: 'Reports' },
    { id: 'valuations', label: 'Market data' },
    { id: 'integrations', label: 'Integrations & alerts' },
  ];
  const expenseCategories = categories.filter((category) => category.category_type === 'EXPENSE');
  const canRecordTransaction = accounts.length > 0;

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Your financial records</h2>
          <p className="mt-1 text-sm text-slate-600">Amounts are shown in their original currency; transfers are not income or expenses.</p>
        </div>
        <button type="button" onClick={signOut} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Sign out</button>
      </div>

      <nav className="flex flex-wrap gap-2" aria-label="Finance sections">
        {tabs.map((item) => (
          <button key={item.id} type="button" onClick={() => setTab(item.id)} aria-current={tab === item.id ? 'page' : undefined} className={`rounded-full px-4 py-2 text-sm ${tab === item.id ? 'bg-brand-800 text-white' : 'border border-slate-300 bg-white text-slate-700'}`}>
            {item.label}
          </button>
        ))}
      </nav>

      {tab === 'accounts' && (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <form onSubmit={createAccount} className="card grid content-start gap-3">
            <h3 className="font-semibold">Add account</h3>
            <label className="grid gap-1 text-sm">Name<input name="name" required maxLength={120} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Type<select name="account_type" className="rounded-lg border border-slate-300 px-3 py-2"><option value="BANK">Bank</option><option value="CASH">Cash</option><option value="MOBILE_MONEY">Mobile money</option><option value="SAVINGS">Savings</option><option value="CREDIT">Credit</option></select></label>
            <label className="grid gap-1 text-sm">Currency<input name="currency_code" defaultValue="KES" pattern="[A-Za-z]{3}" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Opening balance<input name="opening_balance" type="number" step="0.00000001" defaultValue="0" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <button className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white">Save account</button>
          </form>
          <div className="card">
            <h3 className="font-semibold">Accounts</h3>
            {accounts.length === 0 ? <p className="mt-3 text-sm text-slate-600">No accounts yet. Add an account to begin recording transactions.</p> : (
              <ul className="mt-3 divide-y divide-slate-100">
                {accounts.map((account) => <li key={account.id} className="flex justify-between gap-4 py-3"><span><span className="block font-medium">{account.name}</span><span className="text-xs text-slate-500">{account.account_type}</span></span><span className="font-semibold">{formatAmount(account.current_balance, account.currency_code)}</span></li>)}
              </ul>
            )}
          </div>
          <form onSubmit={createCategory} className="card grid content-start gap-3">
            <h3 className="font-semibold">Add category</h3>
            <label className="grid gap-1 text-sm">Name<input name="name" required maxLength={80} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Type<select name="category_type" className="rounded-lg border border-slate-300 px-3 py-2"><option value="EXPENSE">Expense</option><option value="INCOME">Income</option></select></label>
            <button className="rounded-lg border border-brand-700 px-4 py-2 font-medium text-brand-800">Save category</button>
            <p className="text-xs text-slate-500">Categories: {categories.map((category) => category.name).join(', ') || 'none yet'}</p>
          </form>
        </div>
      )}

      {tab === 'transactions' && (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <form onSubmit={createTransaction} className="card grid content-start gap-3">
            <h3 className="font-semibold">Record transaction</h3>
            {!canRecordTransaction && <p className="text-sm text-amber-800">Create an account first.</p>}
            <label className="grid gap-1 text-sm">Type<select name="transaction_type" value={transactionType} onChange={(event) => setTransactionType(event.target.value as Transaction['transaction_type'])} className="rounded-lg border border-slate-300 px-3 py-2"><option value="EXPENSE">Expense</option><option value="INCOME">Income</option><option value="TRANSFER">Transfer</option></select></label>
            <label className="grid gap-1 text-sm">From account<select name="account_id" required disabled={!canRecordTransaction} className="rounded-lg border border-slate-300 px-3 py-2">{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency_code}</option>)}</select></label>
            {transactionType === 'TRANSFER' ? (
              <label className="grid gap-1 text-sm">To account for transfer<select name="transfer_account_id" required className="rounded-lg border border-slate-300 px-3 py-2"><option value="">Select destination</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency_code}</option>)}</select></label>
            ) : (
              <label className="grid gap-1 text-sm">Category<select name="category_id" required className="rounded-lg border border-slate-300 px-3 py-2"><option value="">Select category</option>{categories.filter((category) => category.category_type === transactionType).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            )}
            <label className="grid gap-1 text-sm">Amount<input name="amount" type="number" min="0.00000001" step="0.00000001" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Description<input name="description" required maxLength={240} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Date and time<input name="transaction_date" type="datetime-local" required defaultValue={new Date().toISOString().slice(0, 16)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <button disabled={!canRecordTransaction} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white disabled:opacity-50">Record transaction</button>
          </form>
          <div className="card overflow-x-auto">
            <h3 className="font-semibold">Recent transactions</h3>
            {transactions.length === 0 ? <p className="mt-3 text-sm text-slate-600">No transactions recorded.</p> : (
              <table className="mt-3 w-full text-left text-sm">
                <thead><tr className="border-b text-xs text-slate-500"><th className="py-2">Date</th><th>Description</th><th>Type</th><th className="text-right">Amount</th></tr></thead>
                <tbody>{transactions.map((transaction) => <tr key={transaction.id} className="border-b border-slate-100"><td className="py-2 pr-3">{new Date(transaction.transaction_date).toLocaleDateString()}</td><td className="pr-3">{transaction.description}</td><td className="pr-3">{transaction.transaction_type}</td><td className="text-right">{formatAmount(transaction.amount, transaction.currency_code)}</td></tr>)}</tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {tab === 'budgets' && (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <form onSubmit={createBudget} className="card grid content-start gap-3">
            <h3 className="font-semibold">Create budget</h3>
            <label className="grid gap-1 text-sm">Name<input name="name" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Expense category<select name="category_id" required className="rounded-lg border border-slate-300 px-3 py-2"><option value="">Select category</option>{expenseCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            <label className="grid gap-1 text-sm">Amount<input name="amount" type="number" min="0.00000001" step="0.00000001" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Currency<input name="currency_code" defaultValue="KES" pattern="[A-Za-z]{3}" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">Start<input name="start_date" type="date" required defaultValue={currentMonthStart()} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">End<input name="end_date" type="date" required defaultValue={today()} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <button className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white">Save budget</button>
          </form>
          <div className="card">
            <h3 className="font-semibold">Budgets</h3>
            {budgets.length === 0 ? <p className="mt-3 text-sm text-slate-600">No budgets created.</p> : <ul className="mt-3 divide-y divide-slate-100">{budgets.map((budget) => <li key={budget.id} className="py-3"><div className="flex justify-between gap-4"><span className="font-medium">{budget.name}</span><span>{formatAmount(budget.spent, budget.currency_code)} / {formatAmount(budget.amount, budget.currency_code)}</span></div><p className="mt-1 text-xs text-slate-500">{budget.start_date} – {budget.end_date}</p></li>)}</ul>}
          </div>
        </div>
      )}

      {tab === 'reports' && (
        <div className="space-y-4">
          <form onSubmit={runReport} className="card flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-sm">From<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <label className="grid gap-1 text-sm">To<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
            <button disabled={loading} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white">Run report</button>
          </form>
          {summary.length === 0 ? <p className="card text-sm text-slate-600">Choose a date range and run a report. Values remain grouped by currency; no exchange-rate conversion is applied.</p> : summary.map((item) => (
            <div className="card" key={item.currency_code}>
              <h3 className="font-semibold">{item.currency_code} · {startDate} to {endDate}</h3>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <ReportValue label="Income in period" value={item.total_income} currency={item.currency_code} />
                <ReportValue label="Expenses in period" value={item.total_expenses} currency={item.currency_code} />
                <ReportValue label="Net cash flow" value={item.net_cash_flow} currency={item.currency_code} />
                <ReportValue label="Current assets" value={item.total_assets} currency={item.currency_code} />
                <ReportValue label="Current liabilities" value={item.total_liabilities} currency={item.currency_code} />
                <ReportValue label="Current net worth" value={item.net_worth} currency={item.currency_code} />
              </dl>
              <p className="mt-3 text-xs text-slate-500">Assets, liabilities, and net worth are current recorded values, not historical balances for the selected period.</p>
            </div>
          ))}
        </div>
      )}

      {tab === 'valuations' && (
        <div className="space-y-5">
          <p className="card text-sm text-slate-600">
            Prices are historical daily observations from Alpha Vantage; FX rates are daily ECB reference data via Frankfurter.
            Provider coverage, date, and source are shown for every observation. No real-time prices or automatic currency conversion are claimed.
          </p>
          <div className="grid gap-5 lg:grid-cols-2">
            <form onSubmit={refreshMarketPrice} className="card grid content-start gap-3">
              <h3 className="font-semibold">Fetch a daily market price</h3>
              <label className="grid gap-1 text-sm">Provider symbol<input name="symbol" required maxLength={32} pattern="[A-Za-z0-9._-]+" placeholder="IBM or BTC" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <label className="grid gap-1 text-sm">Asset type<select name="asset_type" className="rounded-lg border border-slate-300 px-3 py-2"><option value="EQUITY">Equity</option><option value="ETF">ETF</option><option value="CRYPTO">Crypto</option></select></label>
              <label className="grid gap-1 text-sm">Quote currency<input name="currency_code" defaultValue="USD" required pattern="[A-Za-z]{3}" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <label className="grid gap-1 text-sm">Exchange label (optional)<input name="exchange" maxLength={50} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <button disabled={loading} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white">Fetch and store daily close</button>
              <p className="text-xs text-slate-500">The server requires ALPHA_VANTAGE_API_KEY. Never enter provider credentials in this form.</p>
            </form>
            <form onSubmit={refreshExchangeRates} className="card grid content-start gap-3">
              <h3 className="font-semibold">Fetch dated ECB rates</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1 text-sm">Base currency<input name="base_currency" defaultValue="EUR" required pattern="[A-Za-z]{3}" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
                <label className="grid gap-1 text-sm">Quote currency<input name="quote_currency" defaultValue="USD" required pattern="[A-Za-z]{3}" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              </div>
              <label className="grid gap-1 text-sm">From<input name="start_date" type="date" defaultValue={startDate} required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <label className="grid gap-1 text-sm">To<input name="end_date" type="date" defaultValue={endDate} required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
              <button disabled={loading} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white">Fetch and store daily rates</button>
            </form>
          </div>
          {marketPrices.length > 0 && (
            <div className="card overflow-x-auto">
              <h3 className="font-semibold">Daily price history</h3>
              <table className="mt-3 w-full text-left text-sm">
                <thead><tr className="border-b text-slate-500"><th className="py-2">Date</th><th>Symbol</th><th>Close</th><th>Currency source</th><th>Source / state</th></tr></thead>
                <tbody>{marketPrices.map((item) => <tr key={item.id} className="border-b border-slate-100"><td className="py-2">{item.effective_date}</td><td>{item.symbol}{item.exchange ? ` · ${item.exchange}` : ''}</td><td>{item.price} {item.currency_code}</td><td>{item.currency_source === 'PROVIDER' ? 'Provider-reported' : 'User-entered'}</td><td>{item.provider_key} · {item.data_state}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {exchangeRates.length > 0 && (
            <div className="card overflow-x-auto">
              <h3 className="font-semibold">Dated exchange-rate history</h3>
              <table className="mt-3 w-full text-left text-sm">
                <thead><tr className="border-b text-slate-500"><th className="py-2">Date</th><th>Pair</th><th>Rate</th><th>Source / state</th></tr></thead>
                <tbody>{exchangeRates.map((item) => <tr key={item.id} className="border-b border-slate-100"><td className="py-2">{item.effective_date}</td><td>{item.base_currency}/{item.quote_currency}</td><td>{item.rate}</td><td>{item.provider_key} · {item.data_state}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'integrations' && (
        <IntegrationNotificationsPanel request={apiRequest} accounts={accounts} categories={categories} />
      )}

      {loading && <p role="status" className="text-sm text-slate-600">Loading financial records…</p>}
      {notice && <p role="status" className="text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    </section>
  );
}

function ReportValue({ label, value, currency }: { label: string; value: string; currency: string }) {
  return <div><dt className="text-sm text-slate-500">{label}</dt><dd className="mt-1 font-semibold">{formatAmount(value, currency)}</dd></div>;
}
