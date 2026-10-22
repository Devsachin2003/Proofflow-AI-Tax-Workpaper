"use client";

import Link from "next/link";

export default function AdjustmentsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Adjustments</h1>
      <p className="text-sm text-slate-500">
        Overlay adjustments are modeled (original value, proposed value, estimated tax effect, approval, reversal) and persist in PostgreSQL. The proposal UI is Phase 4. Until then, inspect a line and its sources, then return here after validation findings exist.
      </p>
      <div className="rounded-xl border border-dashed border-[var(--pf-line)] bg-[var(--pf-surface)] p-6 text-sm">
        No workpaper adjustments yet. Start from <Link className="text-teal-800 hover:underline dark:text-teal-300" href="/calculations/SchB.1.2">SchB.1.2 Northlake Bank interest</Link> or <Link className="text-teal-800 hover:underline dark:text-teal-300" href="/calculations/SchB.1.6">SchB.1.6 Swedish interest (2024 FX rate)</Link>.
      </div>
    </div>
  );
}
