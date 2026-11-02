'use client';

import { FormEvent, useState } from 'react';
import { Bot, Send, ShieldCheck } from 'lucide-react';

type ChatMessage = { role: 'user' | 'assistant'; content: string; sources?: { source: string; path: string }[] };
type ChatResponse = { answer: string; model: string; conversation_id: number | null; sources: { source: string; path: string }[] };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const suggestions = [
  'Summarize my recent spending by currency.',
  'How much have I spent against my budgets?',
  'What are my latest dated valuation observations?',
];

export function FinancialCopilot() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [historyEnabled, setHistoryEnabled] = useState(false);
  const [dataAccessEnabled, setDataAccessEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error('Sign-in failed. Check your credentials and try again.');
      const body = await response.json();
      setToken(body.access_token);
      setPassword('');
      const preference = await fetch(`${apiUrl}/api/ai/history`, {
        headers: { Authorization: `Bearer ${body.access_token}` },
      });
      if (preference.ok) setHistoryEnabled((await preference.json()).enabled);
      const dataAccess = await fetch(`${apiUrl}/api/ai/data-access`, {
        headers: { Authorization: `Bearer ${body.access_token}` },
      });
      if (!dataAccess.ok) throw new Error('Could not load AI data-access settings.');
      setDataAccessEnabled((await dataAccess.json()).enabled);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to sign in.');
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event?: FormEvent<HTMLFormElement>, suggested?: string) {
    event?.preventDefault();
    const text = (suggested ?? question).trim();
    if (!token || !text || busy) return;
    setMessages((current) => [...current, { role: 'user', content: text }]);
    setQuestion('');
    setError('');
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/api/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: text, ...(conversationId ? { conversation_id: conversationId } : {}) }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? 'Financial Copilot is unavailable.');
      const result = body as ChatResponse;
      setConversationId(result.conversation_id);
      setMessages((current) => [...current, { role: 'assistant', content: result.answer, sources: result.sources }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Financial Copilot is unavailable.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleDataAccess() {
    if (!token) return;
    const enabled = !dataAccessEnabled;
    if (enabled && !window.confirm(
      'Allow Financial Copilot to send your question and read-only summaries of your own accounts, transactions, budgets, balance sheet, and sourced dated valuations to the configured OpenAI provider? It cannot make changes or payments.',
    )) return;
    try {
      const response = await fetch(`${apiUrl}/api/ai/data-access`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) throw new Error('Could not update AI data-access settings.');
      setDataAccessEnabled(enabled);
      setConversationId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update AI data-access settings.');
    }
  }

  async function toggleHistory() {
    if (!token) return;
    const enabled = !historyEnabled;
    if (!enabled && !window.confirm('Turn off chat history and delete your saved Copilot conversations?')) return;
    const response = await fetch(`${apiUrl}/api/ai/history`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ enabled }),
    });
    if (!response.ok) {
      setError('Could not update chat history settings.');
      return;
    }
    setHistoryEnabled(enabled);
    setConversationId(null);
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft" aria-label="Financial Copilot">
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700"><Bot size={20} /></span>
          <div><h2 className="font-semibold">Financial Copilot</h2><p className="text-xs text-slate-500">Private by default. Financial facts require connected data.</p></div>
        </div>
        {token && <div className="flex items-center gap-3"><button type="button" onClick={() => { setMessages([]); setConversationId(null); }} className="text-sm text-slate-600 hover:text-slate-900">New chat</button><button type="button" onClick={() => { setToken(''); setPassword(''); setMessages([]); setConversationId(null); }} className="text-sm text-slate-600 hover:text-slate-900">Sign out</button></div>}
      </header>

      {!token ? (
        <form onSubmit={login} className="grid gap-3 p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="grid gap-1 text-sm text-slate-700">Email<input autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="grid gap-1 text-sm text-slate-700">Password<input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2" /></label>
          <button disabled={busy} className="rounded-lg bg-brand-700 px-4 py-2 font-medium text-white disabled:opacity-60">{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
      ) : (
        <>
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 text-xs text-slate-600">
            <span className="flex items-center gap-2"><ShieldCheck size={15} /> Your API key stays on the server</span>
            <div className="flex flex-wrap gap-4">
              <button type="button" onClick={toggleDataAccess} className="flex items-center gap-2">
                <input aria-label="Allow AI financial data access" type="checkbox" checked={dataAccessEnabled} readOnly className="accent-emerald-700" /> Share read-only finance data with AI
              </button>
              <button type="button" onClick={toggleHistory} className="flex items-center gap-2">
                <input aria-label="Save chat history" type="checkbox" checked={historyEnabled} readOnly className="accent-emerald-700" /> Save chat history
              </button>
            </div>
          </div>
          <div className="max-h-[380px] min-h-[180px] space-y-3 overflow-y-auto p-5" aria-live="polite">
            {messages.length === 0 && <div><p className="mb-3 text-sm text-slate-600">{dataAccessEnabled ? 'Copilot reads only your own finance records and sourced dated valuation observations. It does not execute transactions.' : 'Financial data is not shared with AI unless you explicitly enable read-only access above. Enabling sends your question and relevant financial context to the configured OpenAI provider.'}</p><div className="flex flex-wrap gap-2">{suggestions.map((item) => <button key={item} type="button" onClick={() => sendMessage(undefined, item)} disabled={busy || !dataAccessEnabled} className="rounded-full border border-slate-200 px-3 py-1.5 text-left text-xs text-slate-700 hover:border-brand-500 hover:text-brand-800 disabled:opacity-50">{item}</button>)}</div></div>}
            {messages.map((message, index) => <div key={`${index}-${message.role}`} className={`max-w-[90%] whitespace-pre-wrap rounded-xl px-4 py-3 text-sm ${message.role === 'user' ? 'ml-auto bg-brand-900 text-white' : 'bg-slate-100 text-slate-800'}`}>{message.content}{message.role === 'assistant' && message.sources && message.sources.length > 0 && <div className="mt-2 border-t border-slate-300 pt-2 text-xs text-slate-500">Sources: {message.sources.map((source) => source.source).join(' · ')}</div>}</div>)}
            {busy && <p className="text-sm text-slate-500">Preparing a response…</p>}
          </div>
          <form onSubmit={(event) => sendMessage(event)} className="flex gap-2 border-t border-slate-200 p-4">
            <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={4000} placeholder="Ask Financial Copilot" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none" />
            <button type="submit" disabled={busy || !question.trim() || !dataAccessEnabled} aria-label="Send question" title="Send question" className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-700 text-white disabled:opacity-50"><Send size={17} /></button>
          </form>
        </>
      )}
      {error && <p role="alert" className="border-t border-rose-100 bg-rose-50 px-5 py-3 text-sm text-rose-800">{error}</p>}
    </section>
  );
}
