"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";

type Area = { id: string; title: string; status: string; preparer_id: string; reviewer_id: string; due_date: string | null };

export default function ReviewPage() {
  const areas = useQuery({ queryKey: ["areas"], queryFn: () => api<Area[]>("/api/areas") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Review workspace</h1>
      <p className="text-sm text-slate-500">Assignments come from the packet (Priya Raman preparer, Daniel Ortiz reviewer, Helen Strand partner). Notes, sign-offs and invalidation land in Phase 4.</p>
      <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-slate-50 text-[11px] uppercase text-slate-500 dark:bg-white/5">
            <tr><th className="px-3 py-2">Area</th><th className="px-3 py-2">Preparer</th><th className="px-3 py-2">Reviewer</th><th className="px-3 py-2">Due</th><th className="px-3 py-2">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--pf-line)]">
            {(areas.data ?? []).map((a) => (
              <tr key={a.id}>
                <td className="px-3 py-2"><Link className="hover:underline" href={`/workpaper/areas/${a.id}`}>{a.title}</Link></td>
                <td className="px-3 py-2">{a.preparer_id}</td>
                <td className="px-3 py-2">{a.reviewer_id}</td>
                <td className="px-3 py-2">{a.due_date}</td>
                <td className="px-3 py-2">{a.status.replaceAll("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
