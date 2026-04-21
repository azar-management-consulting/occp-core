/**
 * Dashboard v2 — parallel route behind flag NEXT_PUBLIC_DASH_V2=true.
 *
 * Opt-in redesign per .planning/OCCP_DASHBOARD_10_2026.md §4 Home view:
 * - 4 KPI cards (Active Agents, Tasks 24h, Token Spend $, SLO Burn)
 * - Area chart 7d (recharts, Tremor-free — Tremor blocks on React 19)
 * - Live activity feed (last 20 events) — stub for SSE wire
 * - Quick actions row
 *
 * The legacy /(default) /page.tsx stays the primary until this is proven.
 */
import Link from "next/link";
import {
  Activity,
  Cpu,
  Coins,
  Flame,
  Plus,
  UserPlus,
  FileText,
  Keyboard,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// Mock data placeholders — replace with SSE subscriptions in follow-up.
const KPIs = [
  {
    label: "Active Agents",
    value: "8",
    delta: "+0 today",
    icon: Cpu,
  },
  {
    label: "Tasks (24h)",
    value: "307",
    delta: "+42 vs yesterday",
    icon: Activity,
  },
  {
    label: "Token Spend",
    value: "$4.68",
    delta: "60% cache hit rate",
    icon: Coins,
  },
  {
    label: "SLO Burn",
    value: "0.3×",
    delta: "healthy",
    icon: Flame,
  },
];

const RECENT_EVENTS = [
  { ts: "08:42:11", type: "pipeline.pass", task: "task-042", agent: "eng-core" },
  { ts: "08:41:55", type: "audit.append", task: "task-041", agent: "wp-web" },
  { ts: "08:41:30", type: "pipeline.pass", task: "task-040", agent: "content-forge" },
  { ts: "08:40:12", type: "approval.pending", task: "task-039", agent: "infra-ops" },
  { ts: "08:39:44", type: "pipeline.pass", task: "task-038", agent: "eng-core" },
];

export default function DashboardV2Home() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Mission Control
          </h1>
          <p className="text-[var(--fg-muted,#999)]">
            All autonomous activity in one pane. Press{" "}
            <kbd className="rounded border border-[var(--border-subtle,#333)] px-1.5 py-0.5 text-xs">
              ⌘K
            </kbd>{" "}
            for the command palette.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/pipeline">
              <Plus /> New task
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/admin/users">
              <UserPlus /> Invite user
            </Link>
          </Button>
          <Button asChild variant="ghost">
            <Link href="/audit">
              <FileText /> Audit
            </Link>
          </Button>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {KPIs.map((k) => {
          const Icon = k.icon;
          return (
            <Card key={k.label}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{k.label}</CardTitle>
                <Icon className="text-[var(--fg-muted,#999)]" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{k.value}</div>
                <p className="mt-1 text-xs text-[var(--fg-muted,#999)]">
                  {k.delta}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Recent activity + shortcuts */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>
              Last {RECENT_EVENTS.length} pipeline events — live stream wires
              in follow-up SSE commit.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 font-mono text-sm">
              {RECENT_EVENTS.map((e, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between border-b border-[var(--border-subtle,#333)] pb-2 last:border-0"
                >
                  <span className="text-[var(--fg-muted,#999)]">{e.ts}</span>
                  <span className="flex-1 px-4">{e.type}</span>
                  <span className="mr-3 text-[var(--fg-muted,#999)]">
                    {e.agent}
                  </span>
                  <span>{e.task}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Keyboard /> Shortcuts
            </CardTitle>
            <CardDescription>Keyboard first.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              {[
                ["⌘K", "Command palette"],
                ["⌘J", "Ask Brian"],
                ["G H", "Home"],
                ["G P", "Pipeline"],
                ["G A", "Agents"],
                ["G U", "Audit"],
                ["N", "New task"],
                ["⌘⇧K", "KILL SWITCH"],
              ].map(([k, v]) => (
                <div key={k} className="flex items-center justify-between">
                  <kbd className="rounded border border-[var(--border-subtle,#333)] px-2 py-0.5 text-xs font-mono">
                    {k}
                  </kbd>
                  <span className="text-[var(--fg-muted,#999)]">{v}</span>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
