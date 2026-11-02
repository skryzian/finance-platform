'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

type Account = { id: number; name: string; currency_code: string };
type Category = { id: number; name: string; category_type: 'INCOME' | 'EXPENSE' };
type Requester = <T>(path: string, init?: RequestInit) => Promise<T>;
type Preferences = {
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  budget_alerts_enabled: boolean;
  mpesa_events_enabled: boolean;
  sync_events_enabled: boolean;
  security_events_enabled: boolean;
};
type Notification = { id: number; title: string; body: string; event_type: string; read_at: string | null; created_at: string };
type Delivery = { id: number; notification_id: number; channel: string; status: string; attempts: number; last_error: string | null };
type MpesaStatus = { enabled: boolean; environment: string; live_stk_enabled: boolean; destination_model: string };
type Mapping = { account_id: number; income_category_id: number; account_reference: string; active: boolean };
type StkRequest = { id: number; amount: string; phone_number: string; description: string; status: string; result_description: string | null; mpesa_receipt_number: string | null; transaction_id: number | null; created_at: string };
type UserProfile = { phone: string | null };

const eventFields: { key: keyof Preferences; label: string }[] = [
  { key: 'budget_alerts_enabled', label: 'Budget threshold alerts' },
  { key: 'mpesa_events_enabled', label: 'M-Pesa transaction status' },
  { key: 'sync_events_enabled', label: 'Sync conflicts and completion' },
  { key: 'security_events_enabled', label: 'Security and account events' },
];

export function IntegrationNotificationsPanel({
  request,
  accounts,
  categories,
}: {
  request: Requester;
  accounts: Account[];
  categories: Category[];
}) {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [mpesaStatus, setMpesaStatus] = useState<MpesaStatus | null>(null);
  const [mapping, setMapping] = useState<Mapping | null>(null);
  const [accountReference, setAccountReference] = useState('');
  const [stkRequests, setStkRequests] = useState<StkRequest[]>([]);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [stkIdempotencyKey, setStkIdempotencyKey] = useState<string | null>(null);
  const loadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setError('');
    try {
      const [prefs, feed, deliveryRows, mpesa, stk, profile] = await Promise.all([
        request<Preferences>('/api/notifications/preferences'),
        request<Notification[]>('/api/notifications?limit=30'),
        request<Delivery[]>('/api/notifications/deliveries?limit=30'),
        request<MpesaStatus>('/api/integrations/mpesa/status'),
        request<StkRequest[]>('/api/integrations/mpesa/stk-push?limit=20'),
        request<UserProfile>('/auth/me'),
      ]);
      setPreferences(prefs);
      setNotifications(feed);
      setDeliveries(deliveryRows);
      setMpesaStatus(mpesa);
      setStkRequests(stk);
      setPhone(profile.phone ?? '');
      try {
        const savedMapping = await request<Mapping>('/api/integrations/mpesa/account-mapping');
        setMapping(savedMapping);
        setAccountReference(savedMapping.account_reference);
      } catch (caught) {
        if (caught instanceof Error && caught.message === 'M-Pesa C2B account mapping is not configured') {
          setMapping(null);
          setAccountReference('');
        } else {
          throw caught;
        }
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load integrations and notifications.');
    } finally {
      loadingRef.current = false;
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  async function updatePreference(field: keyof Preferences, value: boolean) {
    if (!preferences) return;
    const updated = { ...preferences, [field]: value };
    setError('');
    try {
      const saved = await request<Preferences>('/api/notifications/preferences', {
        method: 'PUT',
        body: JSON.stringify(updated),
      });
      setPreferences(saved);
      setNotice('Notification preference saved.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save notification preference.');
    }
  }

  async function savePhone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    try {
      await request('/auth/profile', {
        method: 'PUT',
        body: JSON.stringify({ phone }),
      });
      setNotice('Phone number saved. Use E.164 format (+254…).');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save phone number.');
    }
  }

  async function markRead(id: number) {
    try {
      await request(`/api/notifications/${id}/read`, { method: 'POST' });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not mark notification as read.');
    }
  }

  async function retryDelivery(id: number) {
    setError('');
    try {
      await request(`/api/notifications/deliveries/${id}/retry`, { method: 'POST' });
      setNotice('Delivery retry queued.');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not retry delivery.');
    }
  }

  async function saveMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError('');
    setNotice('');
    try {
      const saved = await request<Mapping>('/api/integrations/mpesa/account-mapping', {
        method: 'PUT',
        body: JSON.stringify({
          account_id: Number(form.get('account_id')),
          income_category_id: Number(form.get('income_category_id')),
          account_reference: form.get('account_reference'),
        }),
      });
      setMapping(saved);
      setAccountReference(saved.account_reference);
      setNotice('M-Pesa C2B mapping saved. Share this reference with payers.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save M-Pesa account mapping.');
    }
  }

  async function initiateStkPush(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mpesaStatus) return;
    const form = new FormData(event.currentTarget);
    const accountName = accounts.find((item) => item.id === Number(form.get('account_id')))?.name ?? 'selected account';
    const amount = String(form.get('amount') ?? '');
    const phone = String(form.get('phone_number') ?? '');
    const mode = mpesaStatus.environment === 'production' ? 'LIVE' : 'SANDBOX';
    if (!window.confirm(
      `${mode} M-Pesa payment: request ${amount} KES from ${phone}, collected by the platform-managed shortcode, and record it as an expense in ${accountName}?`,
    )) return;
    setBusy(true);
    setError('');
    setNotice('');
    const idempotencyKey = stkIdempotencyKey ?? crypto.randomUUID();
    setStkIdempotencyKey(idempotencyKey);
    try {
      const created = await request<StkRequest>('/api/integrations/mpesa/stk-push', {
        method: 'POST',
        body: JSON.stringify({
          idempotency_key: idempotencyKey,
          account_id: Number(form.get('account_id')),
          category_id: Number(form.get('category_id')),
          amount,
          phone_number: phone,
          description: String(form.get('description') ?? ''),
        }),
      });
      setStkRequests((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setStkIdempotencyKey(null);
      setNotice(`Payment request ${created.status.toLowerCase().replaceAll('_', ' ')}. Check the phone prompt and review its status below.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not initiate M-Pesa payment.');
    } finally {
      setBusy(false);
    }
  }

  const incomeCategories = categories.filter((item) => item.category_type === 'INCOME');
  const expenseCategories = categories.filter((item) => item.category_type === 'EXPENSE');
  const kesAccounts = accounts.filter((item) => item.currency_code === 'KES');

  return (
    <div className="grid gap-5">
      <section className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold">Notification preferences</h3>
            <p className="mt-1 text-sm text-slate-600">Email, SMS, and push are off until you opt in. External messages contain no financial amounts; details stay in-app.</p>
          </div>
          <button type="button" onClick={() => void load()} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Refresh</button>
        </div>
        {preferences && (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <fieldset className="grid gap-2">
              <legend className="mb-1 text-sm font-medium">Delivery channels</legend>
              {([
                ['email_enabled', 'Email (SendGrid)'],
                ['sms_enabled', 'SMS (Twilio)'],
                ['push_enabled', 'Mobile push (Expo)'],
              ] as [keyof Preferences, string][]).map(([field, label]) => (
                <label key={field} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={preferences[field]} onChange={(event) => void updatePreference(field, event.target.checked)} />
                  {label}
                </label>
              ))}
              <p className="text-xs text-slate-500">SMS requires an E.164 profile phone number. Push requires a registered mobile device. Delivery is visible in the attempts list below.</p>
            </fieldset>
            <fieldset className="grid gap-2">
              <legend className="mb-1 text-sm font-medium">Events</legend>
              {eventFields.map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={preferences[key]} onChange={(event) => void updatePreference(key, event.target.checked)} />
                  {label}
                </label>
              ))}
            </fieldset>
          </div>
        )}
        <form onSubmit={savePhone} className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-4">
          <label className="grid gap-1 text-sm">SMS phone number (E.164)<input value={phone} onChange={(event) => setPhone(event.target.value)} type="tel" placeholder="+2547XXXXXXXX" pattern="\+[1-9][0-9]{7,14}" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <button className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Save phone</button>
        </form>
      </section>

      <section className="card">
        <h3 className="font-semibold">In-app notifications</h3>
        {notifications.length === 0 ? <p className="mt-3 text-sm text-slate-600">No notifications yet.</p> : (
          <ul className="mt-3 divide-y">
            {notifications.map((item) => (
              <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div><p className="font-medium">{item.title}</p><p className="text-sm text-slate-600">{item.body}</p><p className="text-xs text-slate-500">{item.event_type} · {new Date(item.created_at).toLocaleString()}</p></div>
                {!item.read_at && <button type="button" onClick={() => void markRead(item.id)} className="text-sm font-medium text-brand-700">Mark read</button>}
              </li>
            ))}
          </ul>
        )}
        {deliveries.length > 0 && (
          <div className="mt-5 border-t pt-4">
            <h4 className="text-sm font-medium">External delivery attempts</h4>
            <ul className="mt-2 grid gap-2">
              {deliveries.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2 text-sm">
                  <span>{item.channel} · {item.status.toLowerCase()} · attempt {item.attempts}{item.last_error ? ` · ${item.last_error}` : ''}</span>
                  {item.status === 'FAILED' && <button type="button" onClick={() => void retryDelivery(item.id)} className="text-brand-700">Retry</button>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="card grid gap-5">
        <div>
          <h3 className="font-semibold">M-Pesa Daraja</h3>
          <p className="mt-1 text-sm text-slate-600">Environment: {mpesaStatus?.environment ?? 'loading'} · destination: platform-managed shortcode. Credentials and callback tokens are server-only. Configure live payments explicitly on the server after Daraja onboarding.</p>
          {mpesaStatus && !mpesaStatus.enabled && <p className="mt-2 text-sm text-amber-800">Integration is not configured by the service owner.</p>}
        </div>
        <form onSubmit={saveMapping} className="grid gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-3">
          <div className="md:col-span-3"><h4 className="font-medium">Incoming C2B mapping</h4><p className="text-xs text-slate-500">Confirmed incoming payments with this reference are recorded as KES income. The service owner must register the callback URLs with Daraja.</p></div>
          <label className="grid gap-1 text-sm">KES account<select name="account_id" required className="rounded-lg border border-slate-300 px-3 py-2">{kesAccounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Income category<select name="income_category_id" required className="rounded-lg border border-slate-300 px-3 py-2">{incomeCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Account reference<input name="account_reference" minLength={4} maxLength={20} required value={accountReference} onChange={(event) => setAccountReference(event.target.value)} pattern="[A-Za-z0-9_-]+" className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <div className="md:col-span-3 flex items-center justify-between gap-3">
            {mapping && <span className="text-sm text-slate-600">Current reference: <strong>{mapping.account_reference}</strong></span>}
            <button disabled={kesAccounts.length === 0 || incomeCategories.length === 0} className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Save C2B mapping</button>
          </div>
        </form>

        <form onSubmit={initiateStkPush} className="grid gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-2">
          <div className="md:col-span-2"><h4 className="font-medium">Request an STK Push payment</h4><p className="text-xs text-slate-500">This asks the phone owner to approve a payment to the platform-managed shortcode. A ledger expense is posted only after a matching successful provider callback. Never enter payment credentials here.</p></div>
          <label className="grid gap-1 text-sm">KES account<select name="account_id" required className="rounded-lg border border-slate-300 px-3 py-2">{kesAccounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Expense category<select name="category_id" required className="rounded-lg border border-slate-300 px-3 py-2">{expenseCategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm">Amount (whole KES)<input name="amount" type="number" min="1" step="1" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="grid gap-1 text-sm">Safaricom phone (254…)<input name="phone_number" pattern="\+?254[17][0-9]{8}" placeholder="2547XXXXXXXX" required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="grid gap-1 text-sm md:col-span-2">Description<input name="description" maxLength={120} required className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <button disabled={busy || !mpesaStatus?.enabled || (mpesaStatus.environment === 'production' && !mpesaStatus.live_stk_enabled) || kesAccounts.length === 0 || expenseCategories.length === 0} className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 md:col-span-2">{busy ? 'Requesting…' : 'Request phone approval'}</button>
        </form>

        {stkRequests.length > 0 && (
          <div className="overflow-x-auto">
            <h4 className="font-medium">Payment requests</h4>
            <table className="mt-2 w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="py-2">Date</th><th>Amount</th><th>Phone</th><th>Status / receipt</th></tr></thead><tbody>
              {stkRequests.map((item) => <tr key={item.id} className="border-b border-slate-100"><td className="py-2">{new Date(item.created_at).toLocaleString()}</td><td>{item.amount} KES</td><td>{item.phone_number}</td><td>{item.status}{item.mpesa_receipt_number ? ` · ${item.mpesa_receipt_number}` : ''}{item.result_description ? ` · ${item.result_description}` : ''}</td></tr>)}
            </tbody></table>
          </div>
        )}
      </section>

      {notice && <p role="status" className="text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    </div>
  );
}
