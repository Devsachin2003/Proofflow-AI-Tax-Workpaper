"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { use, useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { displayValue, money, when } from "@/lib/format";

type Finding = {
  id: string;
  rule_id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  category: string;
  confidence: string;
  blocks_filing: boolean;
  affected_amount: number | null;
  fed_effect: number | null;
  ca_effect: number | null;
  effect_basis: string | null;
  evidence: string[];
  line_keys: string[];
  recommended_action: string;
  details: Record<string, unknown>;
  resolution_note: string | null;
  row_version: number;
  notes: { id: number; author_id: string; body: string; created_at: string }[];
  audit: { id: number; at: string; actor_id: string | null; action: string; summary: string }[];
};

function hrefFor(ref: string): string | null {
  if (/^D\d{2}$/.test(ref) || /^W-\d{4}$/.test(ref)) return `/evidence/${ref}`;
  if (ref.startsWith("ev-")) return `/evidence/value/${ref}`;
  return null;
}

export default function FindingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const q = useQuery({ queryKey: ["finding", id], queryFn: () => api<Finding>(`/api/findings/${id}`) });
  const decide = useMutation({
    mutationFn: (status: string) => api<Finding>(`/api/findings/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, note, expected_version: q.data?.row_version }),
    }),
    onSuccess: (body) => {
      setNote("");
      qc.setQueryData(["finding", id], body);
      qc.invalidateQueries({ queryKey: ["findings"] });
    },
  });
  if (q.isLoading) return <LoadingState />;
  if (q.error) return <ErrorState error={q.error} />;
  const f = q.data!;
  const pairs = Array.isArray(f.details.pairs) ? f.details.pairs as { line: string; document_id: string; ev: string; page: number; label: string; value: unknown }[] : [];

  return (
    <div className="space-y-4">
      <Link href="/findings" className="text-[12px] text-teal-800 hover:underline dark:text-teal-300">← Findings</Link>
      <div>
        <div className="text-[12px] font-mono text-slate-500">{f.id} · {f.rule_id}</div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{f.title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-700 dark:text-slate-200">{f.description}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <Stat label="Severity" value={f.severity} />
        <Stat label="Status" value={f.status.replaceAll("_", " ")} />
        <Stat label="Confidence" value={f.confidence} />
        <Stat label="Amount" value={f.affected_amount == null ? "—" : money(f.affected_amount)} />
      </div>
      <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        <h2 className="font-semibold">Source records</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {f.evidence.map((ref) => {
            const href = hrefFor(ref);
            return href ? <Link key={ref} href={href} className="rounded bg-slate-100 px-2 py-1 font-mono text-[12px] dark:bg-white/10">{ref}</Link> : <span key={ref} className="rounded bg-slate-100 px-2 py-1 font-mono text-[12px] dark:bg-white/10">{ref}</span>;
          })}
        </div>
        {pairs.length ? (
          <ul className="mt-3 space-y-2">
            {pairs.map((p) => (
              <li key={p.ev}>
                <Link className="font-mono text-teal-800 hover:underline dark:text-teal-300" href={`/evidence/${p.document_id}?ev=${p.ev}&page=${p.page}`}>{p.document_id} {p.ev}</Link>
                {" · "}{p.label} = {displayValue(p.value)} {" · "}
                <Link className="font-mono text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(p.line)}`}>{p.line}</Link>
              </li>
            ))}
          </ul>
        ) : null}
        <h2 className="mt-4 font-semibold">Affected lines</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {f.line_keys.map((k) => <Link key={k} href={`/calculations/${encodeURIComponent(k)}`} className="rounded bg-slate-100 px-2 py-1 font-mono text-[12px] dark:bg-white/10">{k}</Link>)}
          {f.line_keys.length === 0 ? <span className="text-slate-500">None</span> : null}
        </div>
        {f.effect_basis ? <p className="mt-3 text-[13px] text-slate-500">{f.effect_basis} Federal estimate {money(f.fed_effect)}. California estimate {money(f.ca_effect)}.</p> : null}
        <p className="mt-3"><span className="font-medium">Next action. </span>{f.recommended_action}</p>
      </section>
      <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        <h2 className="font-semibold">Review decision</h2>
        <p className="mt-1 text-[12px] text-slate-500">Recording a decision does not change Schedule B or any other return line.</p>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Required when verifying or marking a false positive" className="mt-2 min-h-20 w-full rounded-md border border-[var(--pf-line)] bg-[var(--pf-bg)] px-3 py-2" />
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={() => decide.mutate("open")} className="rounded-md border border-[var(--pf-line)] px-3 py-2">Mark unresolved</button>
          <button type="button" onClick={() => decide.mutate("resolved")} className="rounded-md bg-teal-800 px-3 py-2 text-white">Mark verified</button>
          <button type="button" onClick={() => decide.mutate("false_positive")} className="rounded-md border border-amber-700 px-3 py-2 text-amber-900">False positive</button>
        </div>
        {decide.error ? <p className="mt-2 text-rose-700">{decide.error.message}</p> : null}
        {f.resolution_note ? <p className="mt-3">Latest note: {f.resolution_note}</p> : null}
        <ul className="mt-3 space-y-2">
          {f.notes.map((n) => <li key={n.id} className="text-[13px]"><span className="font-mono">{n.author_id}</span> · {when(n.created_at)} · {n.body}</li>)}
        </ul>
      </section>
      <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        <h2 className="font-semibold">Audit history</h2>
        <ul className="mt-2 space-y-2">
          {f.audit.length === 0 ? <li className="text-slate-500">No decision events yet. A validation scan is logged separately from this finding.</li> : f.audit.map((e) => (
            <li key={e.id}>{when(e.at)} · {e.actor_id ?? "system"} · {e.action} · {e.summary}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-3">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="mt-1 font-semibold capitalize">{value}</div>
    </div>
  );
}
