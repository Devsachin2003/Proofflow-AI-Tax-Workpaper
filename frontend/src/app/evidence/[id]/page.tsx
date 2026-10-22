"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { displayValue } from "@/lib/format";

type Value = {
  id: string;
  page: number;
  field: string;
  label: string;
  value: unknown;
  confidence: number;
  position: { x0: number; y0: number; x1: number; y1: number };
  used_by: Record<string, string[]>;
};

type Detail = {
  id: string;
  title: string;
  issuer: string;
  marked_corrected: boolean;
  simulated: boolean;
  origin: string;
  pages: { page: number; printed_content: string }[];
  values: Value[];
  usage: { status: string; reason: string | null; lines: string[] };
  direct_lines: string[];
  downstream_lines: { key: string; label: string; value: unknown }[];
  findings: { id: string; title: string; status: string; severity: string }[];
};

export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [kind, setKind] = useState("note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const q = useQuery({ queryKey: ["document", id], queryFn: () => api<Detail>(`/api/documents/${id}`) });
  const attach = useMutation({
    mutationFn: () => api<{ id: string }>("/api/evidence", {
      method: "POST",
      body: JSON.stringify({ kind, title, content, attached_to: id }),
    }),
    onSuccess: (created) => {
      setTitle("");
      setContent("");
      qc.invalidateQueries({ queryKey: ["documents"] });
      window.location.href = `/evidence/${created.id}`;
    },
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ev = params.get("ev");
    const pageNo = Number(params.get("page") || "");
    if (ev) setSelected(ev);
    if (pageNo) setPage(pageNo);
  }, [id]);

  useEffect(() => {
    const hit = q.data?.values.find((v) => v.id === selected);
    if (hit) setPage(hit.page);
  }, [q.data, selected]);

  if (q.isLoading) return <LoadingState label="Opening simulated document…" />;
  if (q.error) return <ErrorState error={q.error} />;
  const d = q.data!;
  const current = d.pages.find((p) => p.page === page) ?? d.pages[0];
  const highlights = d.values.filter((v) => v.page === current?.page);
  const sel = d.values.find((v) => v.id === selected) ?? null;

  return (
    <div className="space-y-4">
      <div>
        <Link href="/evidence" className="text-[12px] text-teal-800 hover:underline dark:text-teal-300">← Evidence</Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{d.id} · {d.title}</h1>
        <p className="mt-1 text-sm text-slate-500">{d.issuer}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-[12px]">
          <span className="rounded-full bg-slate-100 px-2 py-1 dark:bg-white/10">usage: {d.usage.status}</span>
          {d.marked_corrected ? <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">corrected</span> : null}
          <span className="rounded-full bg-slate-100 px-2 py-1 dark:bg-white/10">{d.origin}</span>
        </div>
        {d.usage.reason ? <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{d.usage.reason}</p> : null}
        {d.simulated ? (
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            Simulated preview generated from printed_content. This is not an original scan.
          </div>
        ) : null}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {d.pages.map((p) => (
              <button key={p.page} type="button" onClick={() => setPage(p.page)} className={`rounded-md border px-2 py-1 text-[12px] ${p.page === current?.page ? "border-teal-700 bg-teal-50 dark:bg-teal-950/40" : "border-[var(--pf-line)]"}`}>
                Page {p.page}
              </button>
            ))}
          </div>
          <div className="relative aspect-[8.5/11] overflow-hidden rounded-md border border-[var(--pf-line)] bg-[#fbfaf6] text-[#1b1b18]">
            <pre className="h-full overflow-hidden whitespace-pre-wrap p-6 font-mono text-[11px] leading-5">{current?.printed_content}</pre>
            {highlights.map((h) => (
              <button
                key={h.id}
                type="button"
                aria-label={h.label}
                onClick={() => setSelected(h.id)}
                className={`absolute z-10 border-2 ${selected === h.id ? "border-teal-700 bg-teal-400/35" : "border-amber-500/90 bg-amber-300/25"}`}
                style={{ left: `${h.position.x0 * 100}%`, top: `${h.position.y0 * 100}%`, width: `${Math.max((h.position.x1 - h.position.x0) * 100, 1.5)}%`, height: `${Math.max((h.position.y1 - h.position.y0) * 100, 1.2)}%` }}
              />
            ))}
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4">
            <h2 className="text-sm font-semibold">Extracted fields</h2>
            <div className="mt-3 max-h-[50vh] space-y-2 overflow-auto">
              {d.values.map((v) => (
                <button key={v.id} type="button" onClick={() => { setSelected(v.id); setPage(v.page); }} className={`block w-full rounded-md border px-3 py-2 text-left text-[13px] ${selected === v.id ? "border-teal-700 bg-teal-50 dark:bg-teal-950/30" : "border-[var(--pf-line)]"}`}>
                  <div className="font-medium">{v.label}</div>
                  <div className="text-slate-600 dark:text-slate-300">{displayValue(v.value)} · {v.id} · field {v.field} · conf {(v.confidence * 100).toFixed(0)}%</div>
                  {Object.entries(v.used_by).map(([ver, keys]) => (
                    <div key={ver} className="mt-1 text-[12px] text-slate-500">{ver}: {keys.map((k) => <Link key={k} href={`/calculations/${encodeURIComponent(k)}`} className="mr-2 text-teal-800 hover:underline dark:text-teal-300">{k}</Link>)}</div>
                  ))}
                </button>
              ))}
              {d.values.length === 0 ? <p className="text-sm text-slate-500">No extracted fields. {d.usage.reason}</p> : null}
            </div>
            {sel ? (
              <div className="mt-4 rounded-md bg-slate-50 p-3 text-[13px] dark:bg-white/5">
                <div className="font-medium">{sel.id} · {sel.field}</div>
                <div>Value {displayValue(sel.value)}. Page {sel.page}. Box highlighted on the simulated page.</div>
                <div className="mt-1">Feeds: {Object.values(sel.used_by).flat().join(", ") || "not cited by a return line"}.</div>
              </div>
            ) : null}
          </div>
          <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-[13px]">
            <h2 className="text-sm font-semibold">Where this document landed</h2>
            {d.direct_lines.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {d.direct_lines.map((k) => <Link key={k} href={`/calculations/${encodeURIComponent(k)}`} className="rounded bg-slate-100 px-2 py-1 font-mono text-[12px] dark:bg-white/10">{k}</Link>)}
              </div>
            ) : <p className="mt-2 text-slate-500">No direct return lines in the active version.</p>}
            {d.downstream_lines.length ? (
              <div className="mt-3">
                <div className="font-medium">Downstream calculations</div>
                <ul className="mt-1 space-y-1">
                  {d.downstream_lines.slice(0, 12).map((ln) => (
                    <li key={ln.key}><Link className="font-mono text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(ln.key)}`}>{ln.key}</Link> · {ln.label} · {displayValue(ln.value)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
          {d.findings?.length ? (
            <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-[13px]">
              <h2 className="text-sm font-semibold">Findings that cite this document</h2>
              <ul className="mt-2 space-y-1">
                {d.findings.map((f) => (
                  <li key={f.id}><Link className="text-teal-800 hover:underline dark:text-teal-300" href={`/findings/${f.id}`}>{f.title}</Link> · {f.status}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <form className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm" onSubmit={(e) => { e.preventDefault(); attach.mutate(); }}>
            <h2 className="text-sm font-semibold">Attach evidence</h2>
            <p className="mt-1 text-[12px] text-slate-500">Saved as a new workpaper document. The packet file is not modified.</p>
            <div className="mt-3 flex gap-2">
              {["note", "message", "file"].map((k) => (
                <button key={k} type="button" onClick={() => setKind(k)} className={`rounded-md border px-2 py-1 text-[12px] ${kind === k ? "border-teal-700 bg-teal-50" : "border-[var(--pf-line)]"}`}>{k}</button>
              ))}
            </div>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className="mt-2 h-9 w-full rounded-md border border-[var(--pf-line)] bg-[var(--pf-bg)] px-3 text-sm" />
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Note, message, or file description" className="mt-2 min-h-20 w-full rounded-md border border-[var(--pf-line)] bg-[var(--pf-bg)] px-3 py-2 text-sm" />
            <button type="submit" disabled={title.trim().length < 3 || !content.trim() || attach.isPending} className="mt-2 rounded-md bg-[var(--pf-navy)] px-3 py-2 text-[13px] text-white disabled:opacity-40">Save attachment</button>
            {attach.error ? <p className="mt-2 text-rose-700">{attach.error.message}</p> : null}
          </form>
        </div>
      </div>
    </div>
  );
}
