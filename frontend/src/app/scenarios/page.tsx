"use client";

import { useQuery } from "@tanstack/react-query";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Scenario = { id: string; description: string; base_version: string; federal: { total_tax_change?: number }; california: { total_tax_change?: number }; changed_line_count: number; choices: unknown };

export default function ScenariosPage() {
  const q = useQuery({ queryKey: ["scenarios"], queryFn: () => api<Scenario[]>("/api/scenarios") });
  if (q.isLoading) return <LoadingState />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">What-if scenarios</h1>
      <p className="text-sm text-slate-500">Engine results from the packet. These are not local tax-effect estimates.</p>
      <div className="grid gap-3">
        {q.data!.map((s) => (
          <article key={s.id} className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
            <h2 className="font-semibold">{s.id}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{s.description}</p>
            <p className="mt-2 text-[13px]">Base {s.base_version} · federal tax change {money(s.federal.total_tax_change ?? 0)} · California {money(s.california.total_tax_change ?? 0)} · {s.changed_line_count} changed lines</p>
          </article>
        ))}
      </div>
    </div>
  );
}
