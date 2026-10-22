"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";

type TL = { items: { id: string; event: string; detail: string; at: string; refs?: string[] }[] };

export default function NoticesPage() {
  const q = useQuery({ queryKey: ["timeline-future"], queryFn: () => api<TL>("/api/timeline?include_future=true") });
  const notices = (q.data?.items ?? []).filter((e) => e.event.includes("notice") || e.detail.toLowerCase().includes("notice"));
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Notices</h1>
      <p className="text-sm text-slate-500">Packet notices (CP2000 2023, Letter 566 2025 exam) are stored as agency records. The 2028 examination letter is scripted for replay.</p>
      {notices.map((n) => (
        <article key={n.id} className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
          <div className="text-[12px] text-slate-500">{n.id} · {n.event}</div>
          <p className="mt-1 text-sm">{n.detail}</p>
          {(n.refs ?? []).map((r) => r.startsWith("D") ? <Link key={r} href={`/evidence/${r}`} className="mr-2 text-[12px] text-teal-800 hover:underline">{r}</Link> : <span key={r} className="mr-2 text-[12px] font-mono">{r}</span>)}
        </article>
      ))}
    </div>
  );
}
