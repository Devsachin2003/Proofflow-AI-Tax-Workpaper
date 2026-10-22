"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

type HH = { people: { name: string; role: string }[]; related_returns: { who: string; return: string; prepared_by: string }[] };

export default function ClientPage() {
  const q = useQuery({ queryKey: ["household"], queryFn: () => api<HH>("/api/household") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Client workspace</h1>
      <p className="text-sm text-slate-500">Switch the demo role to Ngozi or Erik to see the client permission set. Approval and Form 8879 signing are Phase 5.</p>
      <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        <h2 className="font-semibold">Household</h2>
        <ul className="mt-2 list-disc pl-5">{(q.data?.people ?? []).map((p) => <li key={p.name}>{p.name} · {p.role}</li>)}</ul>
        <h2 className="mt-4 font-semibold">Related returns (outside this workpaper)</h2>
        <ul className="mt-2 space-y-2">
          {(q.data?.related_returns ?? []).map((r) => (
            <li key={r.who}><span className="font-medium">{r.who}</span>: {r.return} — {r.prepared_by}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
