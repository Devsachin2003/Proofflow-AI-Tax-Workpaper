export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="rounded-lg border border-[var(--pf-line)] bg-[var(--pf-surface)] px-4 py-10 text-center text-sm text-slate-500">
      {label}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong";
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
      {message}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--pf-line)] bg-[var(--pf-surface)] px-4 py-10 text-center">
      <div className="text-sm font-medium">{title}</div>
      <p className="mt-1 text-sm text-slate-500">{body}</p>
    </div>
  );
}
