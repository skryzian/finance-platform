import { FinanceWorkspace } from '@/components/finance-workspace';

export default function FinancePage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-7xl space-y-5">
        <a href="/" className="text-sm font-medium text-brand-700 hover:text-brand-900">← Dashboard</a>
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">Personal finance</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900">Accounts and activity</h1>
          <p className="mt-2 text-sm text-slate-600">Records are private to your account. Transactions are append-only and transfers are excluded from income and expense totals.</p>
        </header>
        <FinanceWorkspace />
      </div>
    </main>
  );
}
