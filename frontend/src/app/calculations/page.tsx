"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Line = { key: string; form: string; label: string; jurisdiction: string; value: unknown; rule: string; sources: number; inputs: number };
type List = { total: number; items: Line[] };

export default function CalculationsPage() {
  const [q, setQ] = useState("");
  const [form, setForm] = useState("");
  const list = useQuery({
    queryKey: ["lines", q, form],
    queryFn: () => {
      const p = new URLSearchParams({ limit: "400" });
      if (q) p.set("q", q);
      if (form) p.set("form", form);
      return api<List>(`/api/lines?${p}`);
    },
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Calculation explorer</h1>
        <p className="mt-1 text-sm text-slate-500">Click a line to inspect inputs, sources, and version history. Form 8949 lots are hidden until you search or filter to F8949.</p>
      </div>
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search key or label" className="h-9 w-72 rounded-md border border-[var(--pf-line)] bg-[var(--pf-surface)] px-3 text-sm" />
        <input value={form} onChange={(e) => setForm(e.target.value)} placeholder="Form e.g. SchB" className="h-9 w-40 rounded-md border border-[var(--pf-line)] bg-[var(--pf-surface)] px-3 text-sm" />
      </div>
      {list.isLoading ? <LoadingState /> : list.error ? <ErrorState error={list.error} /> : (
        <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500 dark:bg-white/5">
              <tr>
                <th className="px-3 py-2">Key</th>
                <th className="px-3 py-2">Label</th>
                <th className="px-3 py-2">Value</th>
                <th className="px-3 py-2">Rule</th>
                <th className="px-3 py-2">Src</th>
                <th className="px-3 py-2">In</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--pf-line)]">
              {list.data!.items.map((ln) => (
                <tr key={ln.key} className="hover:bg-slate-50 dark:hover:bg-white/4">
                  <td className="px-3 py-2 font-mono text-[12px]"><Link className="text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(ln.key)}`}>{ln.key}</Link></td>
                  <td className="px-3 py-2">{ln.label}</td>
                  <td className="px-3 py-2">{typeof ln.value === "number" ? money(ln.value) : String(ln.value)}</td>
                  <td className="px-3 py-2 text-slate-500">{ln.rule}</td>
                  <td className="px-3 py-2">{ln.sources}</td>
                  <td className="px-3 py-2">{ln.inputs}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-[var(--pf-line)] px-3 py-2 text-[12px] text-slate-500">{list.data!.total} lines</div>
        </div>
      )}
    </div>
  );
}
