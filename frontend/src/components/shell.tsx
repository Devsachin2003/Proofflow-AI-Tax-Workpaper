"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  Calculator,
  CalendarClock,
  FileSearch,
  Files,
  Gavel,
  GitCompare,
  Landmark,
  LayoutDashboard,
  ListChecks,
  Moon,
  Scale,
  Search,
  ShieldAlert,
  Sun,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";

import { api, getDemoUser, setDemoUser } from "@/lib/api";
import { cn } from "@/lib/utils";

type User = {
  id: string;
  name: string;
  role: string;
  kind: string;
  credential: string | null;
  sensitive_clearance: boolean;
};

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/workpaper", label: "Workpaper", icon: ListChecks },
  { href: "/workpaper/areas", label: "Area reviews", icon: Files },
  { href: "/evidence", label: "Evidence", icon: FileSearch },
  { href: "/calculations", label: "Calculations", icon: Calculator },
  { href: "/findings", label: "Findings", icon: ShieldAlert },
  { href: "/review", label: "Review", icon: Scale },
  { href: "/adjustments", label: "Adjustments", icon: Gavel },
  { href: "/versions", label: "Versions", icon: GitCompare },
  { href: "/scenarios", label: "What-if", icon: GitCompare },
  { href: "/timeline", label: "Timeline", icon: CalendarClock },
  { href: "/filing", label: "Filing", icon: Landmark },
  { href: "/notices", label: "Notices", icon: Activity },
  { href: "/client", label: "Client", icon: UserRound },
  { href: "/firm", label: "Firm", icon: Building2 },
  { href: "/activity", label: "Activity", icon: Activity },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [userId, setUserId] = useState(DEFAULT_SAFE);
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/api/users") });
  const me = useQuery({
    queryKey: ["me", userId],
    queryFn: () => api<{ name: string; role: string; sensitive_clearance: boolean; permissions: string[] }>("/api/me"),
  });
  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: () => api<{ packet: { name: string }; active_version: string; replay_now: string }>("/api/meta"),
  });

  useEffect(() => {
    setUserId(getDemoUser());
    const onChange = () => setUserId(getDemoUser());
    window.addEventListener("proofflow-user", onChange);
    return () => window.removeEventListener("proofflow-user", onChange);
  }, []);

  const current = users.data?.find((u) => u.id === userId);

  const crumbs = useMemo(() => {
    const hit = NAV.find((n) => n.href !== "/" && pathname.startsWith(n.href));
    return hit?.label ?? "Overview";
  }, [pathname]);

  return (
    <div className="min-h-screen bg-[var(--pf-bg)] text-[var(--pf-ink)]">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-[var(--pf-line)] bg-[var(--pf-navy)] text-slate-100">
        <div className="px-5 py-5">
          <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-teal-300/90">ProofFlow AI</div>
          <div className="mt-1 text-[15px] font-semibold leading-tight">Tax Review Workspace</div>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-6">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "mb-0.5 flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition",
                  active ? "bg-white/12 text-white" : "text-slate-300 hover:bg-white/6 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4 shrink-0 opacity-80" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-white/10 px-4 py-3 text-[11px] text-slate-400">
          Demo identity via <code className="text-slate-200">X-Demo-User</code>
        </div>
      </aside>

      <div className="pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-[var(--pf-line)] bg-[var(--pf-surface)]/90 px-5 backdrop-blur">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="relative w-full max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                placeholder="Search lines, documents, findings…"
                className="h-9 w-full rounded-md border border-[var(--pf-line)] bg-[var(--pf-bg)] pl-9 pr-3 text-[13px] outline-none ring-teal-700/30 focus:ring-2"
              />
            </div>
            <div className="hidden truncate text-[12px] text-slate-500 lg:block">
              {meta.data?.packet?.name ?? "Okafor-Lindqvist · 2025"} · {meta.data?.active_version ?? "v3"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-medium text-teal-800 dark:bg-teal-900/40 dark:text-teal-200">
              {crumbs}
            </span>
            <select
              value={userId}
              onChange={(e) => {
                setDemoUser(e.target.value);
                window.location.reload();
              }}
              className="h-9 max-w-[220px] rounded-md border border-[var(--pf-line)] bg-[var(--pf-bg)] px-2 text-[12px]"
              aria-label="Switch demo role"
            >
              {(users.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} · {u.role.replaceAll("_", " ")}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--pf-line)]"
              aria-label="Toggle theme"
            >
              <Sun className="h-4 w-4 dark:hidden" />
              <Moon className="hidden h-4 w-4 dark:block" />
            </button>
          </div>
        </header>
        <div className="border-b border-[var(--pf-line)] bg-[var(--pf-surface)] px-5 py-2 text-[12px] text-slate-500">
          Signed in as {me.data?.name ?? current?.name ?? "…"} ({me.data?.role ?? current?.role})
          {me.data?.sensitive_clearance === false ? " · sensitive values masked" : ""}
          {" · "}Not production tax software
        </div>
        <main className="px-5 py-6">{children}</main>
      </div>
    </div>
  );
}

const DEFAULT_SAFE = "st-01";
