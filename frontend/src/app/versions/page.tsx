"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Compare = { left: { label: string; summary: { federal: { agi: number; total_tax: number; balance_due: number } } }; right: { label: string; summary: { federal: { agi: number; total_tax: number; balance_due: number } } }; rows: { key: string; label: string; left: unknown; right: unknown; diff: number | null; status: string }[] };

export default function VersionsPage() {
  const [a, setA] = useState("v2");
  const [b, setB] = useState("v3");
  const q = useQuery({ queryKey: ["compare", a, b], queryFn: () => api<Compare>(`/api/compare?a=${a}&b=${b}`) });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Version comparison</h1>
      <div className="flex gap-2">
        {["v1", "v2", "v3"].map((v) => (
          <button key={`a${v}`} type="button" onClick={() => setA(v)} className={`rounded-md border px-3 py-1 text-sm ${a === v ? "border-teal-700 bg-teal-50" : "border-[var(--pf-line)]"}`}>Left {v}</button>
        ))}
        {["v1", "v2", "v3"].map((v) => (
          <button key={`b${v}`} type="button" onClick={() => setB(v)} className={`rounded-md border px-3 py-1 text-sm ${b === v ? "border-teal-700 bg-teal-50" : "border-[var(--pf-line)]"}`}>Right {v}</button>
        ))}
      </div>
      {q.isLoading ? <LoadingState /> : q.error ? <ErrorState error={q.error} /> : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            <SummaryCard label={q.data!.left.label} s={q.data!.left.summary.federal} />
            <SummaryCard label={q.data!.right.label} s={q.data!.right.summary.federal} />
          </div>
          <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
            <table className="w-full text-left text-[13px]">
              <thead className="bg-slate-50 text-[11px] uppercase text-slate-500 dark:bg-white/5">
                <tr><th className="px-3 py-2">Key</th><th className="px-3 py-2">Label</th><th className="px-3 py-2">{a}</th><th className="px-3 py-2">{b}</th><th className="px-3 py-2">Diff</th></tr>
              </thead>
              <tbody className="divide-y divide-[var(--pf-line)]">
                {q.data!.rows.slice(0, 80).map((r) => (
                  <tr key={r.key}>
                    <td className="px-3 py-2 font-mono text-[12px]"><Link href={`/calculations/${encodeURIComponent(r.key)}`}>{r.key}</Link></td>
                    <td className="px-3 py-2">{r.label}</td>
                    <td className="px-3 py-2">{fmt(r.left)}</td>
                    <td className="px-3 py-2">{fmt(r.right)}</td>
                    <td className="px-3 py-2">{r.diff == null ? r.status : money(r.diff)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-[var(--pf-line)] px-3 py-2 text-[12px] text-slate-500">{q.data!.rows.length} changed lines (first 80 shown)</div>
          </div>
        </>
      )}
    </div>
  );
}

function fmt(v: unknown) {
  return typeof v === "number" ? money(v) : v == null ? "—" : String(v);
}

function SummaryCard({ label, s }: { label: string; s: { agi: number; total_tax: number; balance_due: number } }) {
  return (
    <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
      <div className="text-[11px] uppercase text-slate-500">{label} federal</div>
      <div className="mt-2">AGI {money(s.agi)}</div>
      <div>Tax {money(s.total_tax)}</div>
      <div>Balance {money(s.balance_due)}</div>
    </div>
  );
}
