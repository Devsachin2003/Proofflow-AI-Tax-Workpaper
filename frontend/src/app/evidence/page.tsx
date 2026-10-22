"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

type Doc = {
  id: string;
  title: string;
  document_type: string;
  issuer: string;
  belongs_to: string;
  tax_year: number;
  received_at: string;
  marked_corrected: boolean;
  extraction_status: string;
  values: number;
  usage: string;
  usage_reason: string | null;
  review_status: string;
  origin: string;
};

type List = { total: number; items: Doc[]; facets: { document_type: string[]; belongs_to: string[]; usage: string[]; extraction_status: string[] } };

export default function EvidencePage() {
  const [q, setQ] = useState("");
  const [usage, setUsage] = useState("");
  const [type, setType] = useState("");
  const list = useQuery({
    queryKey: ["documents", q, usage, type],
    queryFn: () => {
      const p = new URLSearchParams();
      if (q) p.set("q", q);
      if (usage) p.set("usage", usage);
      if (type) p.set("document_type", type);
      const qs = p.toString();
      return api<List>(`/api/documents${qs ? `?${qs}` : ""}`);
    },
  });

  const types = useMemo(() => list.data?.facets.document_type ?? [], [list.data]);
  const usages = useMemo(() => list.data?.facets.usage ?? [], [list.data]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Evidence explorer</h1>
        <p className="mt-1 text-sm text-slate-500">Simulated document previews from printed_content. Packet documents are immutable.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title, issuer, id" className="h-9 w-64 rounded-md border border-[var(--pf-line)] bg-[var(--pf-surface)] px-3 text-sm" />
        <select value={usage} onChange={(e) => setUsage(e.target.value)} className="h-9 rounded-md border border-[var(--pf-line)] bg-[var(--pf-surface)] px-2 text-sm">
          <option value="">All usage</option>
          {usages.map((u) => <option key={u} value={u}>{u}</option>)}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="h-9 rounded-md border border-[var(--pf-line)] bg-[var(--pf-surface)] px-2 text-sm">
          <option value="">All types</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {list.isLoading ? <LoadingState /> : list.error ? <ErrorState error={list.error} /> : (
        <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500 dark:bg-white/5">
              <tr>
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2">Issuer</th>
                <th className="px-3 py-2">Usage</th>
                <th className="px-3 py-2">Extract</th>
                <th className="px-3 py-2">Values</th>
                <th className="px-3 py-2">Received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--pf-line)]">
              {list.data!.items.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50 dark:hover:bg-white/4">
                  <td className="px-3 py-2 font-mono text-[12px]"><Link className="text-teal-800 hover:underline dark:text-teal-300" href={`/evidence/${d.id}`}>{d.id}</Link></td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{d.title}</div>
                    <div className="text-[12px] text-slate-500">{d.document_type} · {d.belongs_to}{d.marked_corrected ? " · corrected" : ""}</div>
                  </td>
                  <td className="px-3 py-2 text-slate-600">{d.issuer}</td>
                  <td className="px-3 py-2">
                    <div>{d.usage}</div>
                    {d.marked_corrected ? <div className="text-[11px] text-amber-800">corrected source</div> : null}
                    {d.usage_reason ? <div className="max-w-xs text-[11px] text-slate-500">{d.usage_reason}</div> : null}
                  </td>
                  <td className="px-3 py-2">{d.extraction_status}</td>
                  <td className="px-3 py-2">{d.values}</td>
                  <td className="px-3 py-2 text-slate-500">{when(d.received_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-[var(--pf-line)] px-3 py-2 text-[12px] text-slate-500">{list.data!.total} documents in this view</div>
        </div>
      )}
    </div>
  );
}
