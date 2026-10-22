"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";

type User = { id: string; name: string; role: string; credential: string | null; sensitive_clearance: boolean; note: string | null };

export default function FirmPage() {
  const q = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/api/users") });
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Miraflores firm</h1>
        <Link href="/firm/settings" className="text-sm text-teal-800 hover:underline dark:text-teal-300">Standards</Link>
      </div>
      <div className="overflow-hidden rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)]">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-slate-50 text-[11px] uppercase text-slate-500 dark:bg-white/5">
            <tr><th className="px-3 py-2">Staff</th><th className="px-3 py-2">Role</th><th className="px-3 py-2">Clearance</th><th className="px-3 py-2">Note</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--pf-line)]">
            {(q.data ?? []).map((u) => (
              <tr key={u.id}>
                <td className="px-3 py-2">{u.name} <span className="font-mono text-[11px] text-slate-500">{u.id}</span></td>
                <td className="px-3 py-2">{u.role.replaceAll("_", " ")} {u.credential ? `· ${u.credential}` : ""}</td>
                <td className="px-3 py-2">{u.sensitive_clearance ? "yes" : "masked"}</td>
                <td className="px-3 py-2 text-slate-500">{u.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
