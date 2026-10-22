"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { when } from "@/lib/format";

type Overview = { filing: { lifecycle: string; replay_now: string; note: string; required_signatures: string[] }; findings: { open: number; blocking: number }; documents: { used: number; packet: number } };

export default function FilingPage() {
  const q = useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/api/overview") });
  const d = q.data;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Filing readiness</h1>
      <p className="text-sm text-slate-500">Simulated lifecycle only. There is no connection to IRS or FTB e-file services.</p>
      <div className="grid gap-3 md:grid-cols-3">
        <Card title="Lifecycle" body={d?.filing.lifecycle ?? "…"} />
        <Card title="Replay clock" body={d ? when(d.filing.replay_now) : "…"} />
        <Card title="Open findings" body={String(d?.findings.open ?? "…")} />
      </div>
      <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        <p>{d?.filing.note}</p>
        <p className="mt-2 text-slate-500">Required signatures: {d?.filing.required_signatures.join(", ")}</p>
        <p className="mt-2 text-slate-500">Documents used in the current view: {d?.documents.used} / {d?.documents.packet} packet records.</p>
        <p className="mt-2 text-amber-800 dark:text-amber-200">Filing is not ready: independent validation, sign-offs and client authorization are not complete.</p>
      </div>
    </div>
  );
}

function Card({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
      <div className="text-[11px] uppercase text-slate-500">{title}</div>
      <div className="mt-1 text-lg font-semibold capitalize">{body}</div>
    </div>
  );
}
