"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { displayValue } from "@/lib/format";

type Source = { ref: string; type: string; resolved: boolean; note?: string | null; document_id?: string | null; page?: number | null; label?: string | null; value?: unknown };
type Line = {
  key: string; version: string; label: string; value: unknown; rule: string; rule_text: string; note: string | null; form: string;
  inputs: { key: string; label: string | null; value: unknown; resolved: boolean; inputs?: number }[];
  consumers: { key: string; label: string; value: unknown }[];
  sources: Source[];
  history: { version: string; value: unknown; present: boolean }[];
};

function val(v: unknown) {
  return displayValue(v);
}

export default function LinePage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params);
  const decoded = decodeURIComponent(key);
  const q = useQuery({ queryKey: ["line", decoded], queryFn: () => api<Line>(`/api/lines/${encodeURIComponent(decoded)}`) });
  if (q.isLoading) return <LoadingState label="Tracing calculation…" />;
  if (q.error) return <ErrorState error={q.error} />;
  const ln = q.data!;

  return (
    <div className="space-y-4">
      <Link href="/calculations" className="text-[12px] text-teal-800 hover:underline dark:text-teal-300">← Calculations</Link>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{ln.key}</h1>
        <p className="mt-1 text-sm text-slate-500">{ln.label} · {ln.form} · {ln.version}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Amount</div>
          <div className="mt-1 text-2xl font-semibold">{val(ln.value)}</div>
        </div>
        <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 md:col-span-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Rule {ln.rule}</div>
          <p className="mt-1 text-sm leading-relaxed">{ln.rule_text}</p>
          {ln.note ? <p className="mt-2 text-[13px] text-slate-500">{ln.note}</p> : null}
        </div>
      </div>
      <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
        <h2 className="text-sm font-semibold">Sources</h2>
        <ul className="mt-3 space-y-2 text-[13px]">
          {ln.sources.length === 0 ? <li className="text-slate-500">No direct source refs — this line is computed from inputs.</li> : ln.sources.map((s) => (
            <li key={s.ref} className="rounded-md border border-[var(--pf-line)] px-3 py-2">
              <div className="font-mono text-[12px]">{s.ref} {s.resolved ? "" : "· unresolved"}</div>
              <div>{s.label} {s.value != null ? `= ${val(s.value)}` : ""}</div>
              {s.document_id ? <Link className="text-teal-800 hover:underline dark:text-teal-300" href={`/evidence/${s.document_id}?ev=${encodeURIComponent(s.ref)}&page=${s.page ?? 1}`}>Open {s.document_id}{s.page ? ` p.${s.page}` : ""} · {s.ref}</Link> : null}
              {!s.resolved && s.note ? <div className="text-amber-700">{s.note}</div> : null}
            </li>
          ))}
        </ul>
      </section>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
          <h2 className="text-sm font-semibold">Inputs</h2>
          <ul className="mt-3 space-y-1 text-[13px]">
            {ln.inputs.map((i) => (
              <li key={i.key}><Link className="font-mono text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(i.key)}`}>{i.key}</Link> · {i.label} · {val(i.value)}</li>
            ))}
            {ln.inputs.length === 0 ? <li className="text-slate-500">None</li> : null}
          </ul>
        </section>
        <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
          <h2 className="text-sm font-semibold">Feeds</h2>
          <ul className="mt-3 space-y-1 text-[13px]">
            {ln.consumers.map((c) => (
              <li key={c.key}><Link className="font-mono text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(c.key)}`}>{c.key}</Link> · {c.label} · {val(c.value)}</li>
            ))}
            {ln.consumers.length === 0 ? <li className="text-slate-500">Terminal line</li> : null}
          </ul>
        </section>
      </div>
      <section className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
        <h2 className="text-sm font-semibold">Across versions</h2>
        <div className="mt-3 flex gap-4 text-[13px]">
          {ln.history.map((h) => (
            <div key={h.version} className="rounded-md border border-[var(--pf-line)] px-3 py-2">
              <div className="text-[11px] uppercase text-slate-500">{h.version}</div>
              <div className="font-medium">{h.present ? val(h.value) : "not present"}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
