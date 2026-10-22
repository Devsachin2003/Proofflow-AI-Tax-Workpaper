"use client";

export default function ActivityPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Audit history</h1>
      <p className="text-sm text-slate-500">
        Audit events are append-only in PostgreSQL (database trigger rejects UPDATE/DELETE). Attaching evidence writes an audit row. A dedicated activity feed API is next.
      </p>
      <div className="rounded-xl border border-[var(--pf-line)] bg-[var(--pf-surface)] p-4 text-sm">
        Switch to a preparer role on Evidence and attach a note to generate an audited event, then confirm it survived in the database.
      </div>
    </div>
  );
}
