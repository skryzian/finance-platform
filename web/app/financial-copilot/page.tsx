import { FinancialCopilot } from '@/components/financial-copilot';

export default function FinancialCopilotPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-4xl space-y-5">
        <a href="/" className="text-sm font-medium text-brand-700 hover:text-brand-900">← Dashboard</a>
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-700">Personal Financial Intelligence</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900">Financial Copilot</h1>
        </header>
        <FinancialCopilot />
      </div>
    </main>
  );
}
