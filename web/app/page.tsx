export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex items-center justify-between rounded-2xl bg-brand-900 p-6 text-white shadow-soft">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-brand-100">Finance Platform</p>
            <h1 className="mt-2 text-3xl font-semibold">Dashboard</h1>
          </div>
          <div className="rounded-full bg-white/10 px-4 py-2 text-sm">KES · Kenya</div>
        </header>

        <a href="/financial-copilot" className="flex items-center justify-between rounded-xl border border-brand-100 bg-white px-5 py-4 text-brand-900 shadow-soft hover:border-brand-500">
          <span><span className="block font-semibold">Financial Copilot</span><span className="mt-1 block text-sm text-slate-600">Personal financial records are not connected yet</span></span>
          <span aria-hidden="true" className="text-xl">→</span>
        </a>
        <a href="/finance" className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4 text-slate-900 shadow-soft hover:border-brand-500">
          <span><span className="block font-semibold">Accounts, transactions, budgets, and reports</span><span className="mt-1 block text-sm text-slate-600">Create an account or sign in to manage your own financial records</span></span>
          <span aria-hidden="true" className="text-xl">→</span>
        </a>

        <section className="card" aria-labelledby="dashboard-empty-state">
          <h2 id="dashboard-empty-state" className="text-lg font-semibold">Your financial dashboard is not connected yet</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Account balances, transactions, budgets, and reports are not available in this version. No sample figures are shown as personal financial data.
          </p>
        </section>
      </div>
    </main>
  );
}
