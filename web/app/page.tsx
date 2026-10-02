const stats = [
  { label: 'Net worth', value: 'KES 1,245,000', change: '+12.4%' },
  { label: 'Monthly income', value: 'KES 120,000', change: '+7.1%' },
  { label: 'Monthly expenses', value: 'KES 85,000', change: '-2.4%' },
  { label: 'Savings rate', value: '29%', change: '+4.2%' },
];

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
          <span><span className="block font-semibold">Financial Copilot</span><span className="mt-1 block text-sm text-slate-600">Ask about your finances with verified application data</span></span>
          <span aria-hidden="true" className="text-xl">→</span>
        </a>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="card">
              <p className="text-sm text-slate-500">{stat.label}</p>
              <div className="mt-4 flex items-end justify-between">
                <h2 className="text-2xl font-bold">{stat.value}</h2>
                <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
                  {stat.change}
                </span>
              </div>
            </div>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[2fr_1fr]">
          <div className="card">
            <h3 className="text-lg font-semibold">Net worth trend</h3>
            <div className="mt-6 h-64 rounded-xl bg-gradient-to-br from-brand-50 to-white p-4">
              <div className="flex h-full items-end gap-3">
                {[42, 58, 68, 64, 79, 90, 100].map((height, index) => (
                  <div key={height} className="flex-1">
                    <div
                      className="w-full rounded-t-xl bg-gradient-to-t from-brand-600 to-brand-500"
                      style={{ height: `${height}%`, opacity: 0.5 + index * 0.08 }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold">Quick actions</h3>
            <ul className="mt-6 space-y-3 text-sm text-slate-700">
              <li className="rounded-xl bg-slate-50 p-3">Create account</li>
              <li className="rounded-xl bg-slate-50 p-3">Add transaction</li>
              <li className="rounded-xl bg-slate-50 p-3">Set budget</li>
              <li className="rounded-xl bg-slate-50 p-3">Review pending SMS</li>
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}
