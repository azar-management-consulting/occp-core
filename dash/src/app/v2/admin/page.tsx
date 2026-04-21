/**
 * Dashboard v2 — Admin overview.
 *
 * 3 KPI cards + 3 shortcut tiles. Admin guard lives in middleware / the
 * legacy tree; this page is read-only overview.
 */
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Shield,
  Users,
  Building2,
  Activity,
  BarChart3,
  Gauge,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type KPI = {
  label: string;
  value: string;
  delta: string;
  icon: LucideIcon;
};

type Shortcut = {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

/* Mock data — replace with SSE/fetch */
const KPIS: KPI[] = [
  { label: "Users", value: "37", delta: "+3 this week", icon: Users },
  { label: "Organizations", value: "5", delta: "+0 this week", icon: Building2 },
  { label: "Tasks (30d)", value: "8,412", delta: "+612 vs prev 30d", icon: Activity },
];

const SHORTCUTS: Shortcut[] = [
  {
    href: "/admin/users",
    title: "Users",
    description: "Invite, role, deactivate.",
    icon: Users,
  },
  {
    href: "/admin/stats",
    title: "Stats",
    description: "Pipeline + token usage charts.",
    icon: BarChart3,
  },
  {
    href: "/admin/usage",
    title: "Usage",
    description: "Per-org quota + billing state.",
    icon: Gauge,
  },
];

export default function AdminV2Page() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          <Shield className="inline-block mr-2 -mt-1" aria-hidden="true" /> Admin
        </h1>
        <p className="text-[var(--fg-muted,#a1a1aa)]">
          Platform-wide users, orgs and usage.
        </p>
      </div>

      {/* KPI grid */}
      <div className="grid gap-4 md:grid-cols-3">
        {KPIS.map((k) => {
          const Icon = k.icon;
          return (
            <Card key={k.label}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{k.label}</CardTitle>
                <Icon className="text-[var(--fg-muted,#a1a1aa)]" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{k.value}</div>
                <p className="mt-1 text-xs text-[var(--fg-muted,#a1a1aa)]">
                  {k.delta}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Shortcuts */}
      <div className="grid gap-4 md:grid-cols-3">
        {SHORTCUTS.map((s) => {
          const Icon = s.icon;
          return (
            <Link key={s.href} href={s.href} className="group block">
              <Card className="h-full group-hover:border-white/40">
                <CardHeader className="flex flex-row items-start gap-4 space-y-0">
                  <Icon className="mt-1 text-[var(--fg-muted,#a1a1aa)] group-hover:text-white" aria-hidden="true" />
                  <div>
                    <CardTitle className="text-base font-semibold">
                      {s.title}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {s.description}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <span className="text-xs font-mono text-[var(--fg-muted,#a1a1aa)]">
                    {s.href}
                  </span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
