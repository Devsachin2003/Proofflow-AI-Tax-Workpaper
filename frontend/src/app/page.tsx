"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { dueLabel, money, pct } from "@/lib/format";

type Overview = {
  household: { name: string; client_id: string; tax_year: number; filing_status: string; people: { name: string; role: string; ssn_masked: string }[]; residency: { state: string; from: string; to: string | null; status: string }[] };
  active_version: string;
  computed_at: string;
  trigger: string;
  federal: { agi: number; taxable_income: number; total_tax: number; payments: number; balance_due: number; penalty: number; yoy: { agi?: { amount: number; percent: number | null }; total_tax?: { amount: number; percent: number | null } } };
  california: { total_agi: number; ca_agi: number; total_tax: number; payments: number; balance_due: number; yoy: { total_tax?: { amount: number; percent: number | null } } };
  drilldowns: Record<string, string>;
  documents: { all: number; used: number; not_used: number; packet: number };
  findings: { open: number; blocking: number; engine_diagnostics: number };
  areas: { total: number; not_started: number };
  priority_queue: { id: string; kind: string; severity: string; title: string; href: string; blocks_filing: boolean }[];
  filing: { lifecycle: string; replay_now: string; note: string; required_signatures: string[] };
};

function Kpi({ label, value, href, sub }: { label: string; value: string; href?: string; sub?: string }) {
  const inner = (
    <>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      {sub ? <div className="mt-1 text-[12px] text-slate-500">{sub}</div> : null}
    </>
  );
  const cls = "rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 shadow-[0_1px_0_rgba(16,36,58,0.04)]";
  return href ? <Link href={href} className={`${cls} block hover:border-teal-700/40`}>{inner}</Link> : <div className={cls}>{inner}</div>;
}

export default function OverviewPage() {
  const q = useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/api/overview") });
  if (q.isLoading) return <LoadingState label="Loading household command center…" />;
  if (q.error) return <ErrorState error={q.error} />;
  const d = q.data!;
  const fedDue = dueLabel(d.federal.balance_due);
  const caDue = dueLabel(d.california.balance_due);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Okafor-Lindqvist household</h1>
        <p className="mt-1 text-sm text-slate-500">
          {d.household.client_id} · tax year {d.household.tax_year} · {d.household.filing_status.replaceAll("_", " ")} · engine {d.active_version}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Federal AGI" value={money(d.federal.agi)} href={`/calculations/${d.drilldowns.federal_agi}`} sub={d.federal.yoy.agi ? `vs 2024 ${pct(d.federal.yoy.agi.percent)}` : undefined} />
        <Kpi label="Federal taxable income" value={money(d.federal.taxable_income)} href={`/calculations/${d.drilldowns.federal_taxable_income}`} />
        <Kpi label="Federal total tax" value={money(d.federal.total_tax)} href={`/calculations/${d.drilldowns.federal_total_tax}`} sub={d.federal.yoy.total_tax ? `vs 2024 ${pct(d.federal.yoy.total_tax.percent)}` : undefined} />
        <Kpi label="Federal balance" value={fedDue.label} href={`/calculations/${d.drilldowns.federal_balance_due}`} />
        <Kpi label="California AGI" value={money(d.california.ca_agi)} href={`/calculations/${d.drilldowns.california_agi}`} sub={`Total AGI ${money(d.california.total_agi)}`} />
        <Kpi label="California total tax" value={money(d.california.total_tax)} href={`/calculations/${d.drilldowns.california_total_tax}`} />
        <Kpi label="California balance" value={caDue.label} />
        <Kpi label="Documents in v3 view" value={`${d.documents.used} used`} href="/evidence" sub={`${d.documents.packet} in packet · ${d.findings.engine_diagnostics} engine warnings`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
          <header className="flex items-center justify-between border-b border-[var(--pf-line)] px-4 py-3">
            <h2 className="text-sm font-semibold">Review priority queue</h2>
            <Link href="/findings" className="text-[12px] text-teal-800 hover:underline dark:text-teal-300">All findings</Link>
          </header>
          <ul className="divide-y divide-[var(--pf-line)]">
            {d.priority_queue.map((item) => (
              <li key={`${item.kind}-${item.id}`}>
                <Link href={item.href} className="flex gap-3 px-4 py-3 text-sm hover:bg-slate-50 dark:hover:bg-white/4">
                  <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${item.severity === "warning" || item.severity === "error" ? "bg-amber-500" : "bg-slate-400"}`} />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{item.title}</span>
                    <span className="text-[12px] text-slate-500">{item.kind.replaceAll("_", " ")}{item.blocks_filing ? " · may block filing" : ""}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <section className="space-y-4">
          <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
            <h2 className="text-sm font-semibold">Household</h2>
            <ul className="mt-3 space-y-1.5 text-slate-600 dark:text-slate-300">
              {d.household.people.map((p) => (
                <li key={p.name}><span className="font-medium text-[var(--pf-ink)]">{p.name}</span> · {p.role} · {p.ssn_masked}</li>
              ))}
            </ul>
            <div className="mt-3 text-[12px] text-slate-500">
              {d.household.residency.map((r) => (
                <div key={r.state + r.from}>{r.state} {r.status} {r.from} → {r.to ?? "open"}</div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
            <h2 className="text-sm font-semibold">Filing readiness</h2>
            <p className="mt-2 text-slate-600 dark:text-slate-300 capitalize">{d.filing.lifecycle.replaceAll("_", " ")}</p>
            <p className="mt-2 text-[12px] leading-relaxed text-slate-500">{d.filing.note}</p>
            <p className="mt-3 text-[12px] text-slate-500">Required: {d.filing.required_signatures.join(", ")}</p>
            <p className="mt-1 text-[12px] text-slate-500">{d.areas.not_started}/{d.areas.total} areas not started · {d.findings.open} open findings</p>
          </div>
        </section>
      </div>
    </div>
  );
}
