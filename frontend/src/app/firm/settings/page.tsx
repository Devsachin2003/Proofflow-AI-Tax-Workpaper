"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export default function FirmSettingsPage() {
  const q = useQuery({ queryKey: ["permissions"], queryFn: () => api<Record<string, string[]>>("/api/permissions") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Standards and permissions</h1>
      <p className="text-sm text-slate-500">Permission matrix is enforced on the API. Firm administrator edits to starter_standards persist in `firm_setting` (Phase 5 writer).</p>
      <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-slate-50 text-[11px] uppercase text-slate-500 dark:bg-white/5">
            <tr><th className="px-3 py-2">Action</th><th className="px-3 py-2">Roles</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--pf-line)]">
            {Object.entries(q.data ?? {}).map(([action, roles]) => (
              <tr key={action}>
                <td className="px-3 py-2 font-mono text-[12px]">{action}</td>
                <td className="px-3 py-2">{roles.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
