"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

type TL = { now: string; visible: number; total: number; scripted_remaining: number; items: { id: string; at: string; event: string; actor: string | null; detail: string; status: string }[] };

export default function TimelinePage() {
  const [future, setFuture] = useState(false);
  const q = useQuery({ queryKey: ["timeline", future], queryFn: () => api<TL>(`/api/timeline?include_future=${future}`) });
  if (q.isLoading) return <LoadingState />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Case timeline</h1>
          <p className="mt-1 text-sm text-slate-500">Replay clock is {when(q.data!.now)}. Events after v3 are scripted until the clock advances.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={future} onChange={(e) => setFuture(e.target.checked)} />
          Show scripted future
        </label>
      </div>
      <ol className="space-y-3">
        {q.data!.items.map((e) => (
          <li key={e.id} className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
            <div className="text-[12px] text-slate-500">{e.id} · {when(e.at)} · {e.status}</div>
            <div className="font-medium">{e.event.replaceAll("_", " ")}</div>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{e.detail}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
