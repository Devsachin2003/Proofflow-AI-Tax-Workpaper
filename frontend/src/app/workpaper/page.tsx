"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { ErrorState, LoadingState } from "@/components/state";
import { api } from "@/lib/api";

type Area = { id: string; title: string; group: string; status: string; description: string; open_findings: number };

export default function WorkpaperPage() {
  const areas = useQuery({ queryKey: ["areas"], queryFn: () => api<Area[]>("/api/areas") });
  if (areas.isLoading) return <LoadingState />;
  if (areas.error) return <ErrorState error={areas.error} />;
  const groups = [...new Set(areas.data!.map((a) => a.group))];
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tax workpaper</h1>
        <p className="mt-1 text-sm text-slate-500">Nineteen review areas seeded from the packet. Status is workpaper overlay; baseline numbers stay immutable.</p>
      </div>
      {groups.map((g) => (
        <section key={g}>
          <h2 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">{g}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {areas.data!.filter((a) => a.group === g).map((a) => (
              <Link key={a.id} href={`/workpaper/areas/${a.id}`} className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 hover:border-teal-700/40">
                <div className="flex items-start justify-between gap-3">
                  <div className="font-medium">{a.title}</div>
                  <span className="text-[11px] uppercase text-slate-500">{a.status.replaceAll("_", " ")}</span>
                </div>
                <p className="mt-1 text-[13px] text-slate-500">{a.description}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
