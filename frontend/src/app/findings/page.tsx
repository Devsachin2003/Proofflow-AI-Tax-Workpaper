"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Item = {
  id: string;
  rule_id: string;
  title: string;
  severity: string;
  status: string;
  category: string;
  affected_amount: number | null;
  line_keys: string[];
  blocks_filing: boolean;
};

export default function FindingsPage() {
  const qc = useQueryClient();
  const findings = useQuery({ queryKey: ["findings"], queryFn: () => api<{ total: number; items: Item[]; engine_pending: boolean }>("/api/findings") });
  const run = useMutation({
    mutationFn: () => api("/api/validation/run", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["findings"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
  if (findings.isLoading) return <LoadingState />;
  if (findings.error) return <ErrorState error={findings.error} />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Discrepancy queue</h1>
          <p className="mt-1 text-sm text-slate-500">Independent of the tax engine. Decisions are recorded; return lines are not changed here.</p>
        </div>
        <button type="button" onClick={() => run.mutate()} disabled={run.isPending} className="rounded-md bg-[var(--pf-navy)] px-3 py-2 text-[13px] text-white disabled:opacity-50">
          {run.isPending ? "Scanning…" : "Run validation"}
        </button>
      </div>
      {run.error ? <ErrorState error={run.error} /> : null}
      {findings.data!.total === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm text-slate-500">
          No findings stored. Run validation to scan the imported packet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500 dark:bg-white/5">
              <tr>
                <th className="px-3 py-2">Finding</th>
                <th className="px-3 py-2">Rule</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Lines</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--pf-line)]">
              {findings.data!.items.map((f) => (
                <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-white/4">
                  <td className="px-3 py-2">
                    <Link href={`/findings/${f.id}`} className="font-medium text-teal-800 hover:underline dark:text-teal-300">{f.title}</Link>
                    <div className="text-[12px] text-slate-500">{f.severity} · {f.category.replaceAll("_", " ")}{f.blocks_filing ? " · may block filing" : ""}</div>
                  </td>
                  <td className="px-3 py-2 font-mono text-[12px]">{f.rule_id}</td>
                  <td className="px-3 py-2">{f.status.replaceAll("_", " ")}</td>
                  <td className="px-3 py-2">{f.affected_amount == null ? "—" : money(f.affected_amount)}</td>
                  <td className="px-3 py-2 font-mono text-[11px]">{f.line_keys.slice(0, 3).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-[var(--pf-line)] px-3 py-2 text-[12px] text-slate-500">{findings.data!.total} findings</div>
        </div>
      )}
    </div>
  );
}
