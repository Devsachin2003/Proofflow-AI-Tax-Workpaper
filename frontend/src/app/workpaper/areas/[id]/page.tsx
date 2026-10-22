"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Area = { id: string; title: string; description: string; group: string; status: string };
type Lines = { total: number; items: { key: string; label: string; value: unknown; sources: number }[] };

export default function AreaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const areas = useQuery({ queryKey: ["areas"], queryFn: () => api<Area[]>("/api/areas") });
  const lines = useQuery({ queryKey: ["area-lines", id], queryFn: () => api<Lines>(`/api/lines?area=${id}&limit=400`) });
  if (areas.isLoading || lines.isLoading) return <LoadingState />;
  if (areas.error) return <ErrorState error={areas.error} />;
  const area = areas.data!.find((a) => a.id === id);
  if (!area) return <ErrorState error={new Error("Unknown area")} />;
  return (
    <div className="space-y-4">
      <Link href="/workpaper/areas" className="text-[12px] text-teal-800 hover:underline dark:text-teal-300">← Areas</Link>
      <h1 className="text-2xl font-semibold tracking-tight">{area.title}</h1>
      <p className="text-sm text-slate-500">{area.description}</p>
      {lines.error ? <ErrorState error={lines.error} /> : (
        <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-slate-50 text-[11px] uppercase text-slate-500 dark:bg-white/5">
              <tr><th className="px-3 py-2">Key</th><th className="px-3 py-2">Label</th><th className="px-3 py-2">Value</th><th className="px-3 py-2">Sources</th></tr>
            </thead>
            <tbody className="divide-y divide-[var(--pf-line)]">
              {(lines.data?.items ?? []).map((ln) => (
                <tr key={ln.key}>
                  <td className="px-3 py-2 font-mono text-[12px]"><Link className="text-teal-800 hover:underline dark:text-teal-300" href={`/calculations/${encodeURIComponent(ln.key)}`}>{ln.key}</Link></td>
                  <td className="px-3 py-2">{ln.label}</td>
                  <td className="px-3 py-2">{typeof ln.value === "number" ? money(ln.value) : String(ln.value)}</td>
                  <td className="px-3 py-2">{ln.sources}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
