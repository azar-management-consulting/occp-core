/**
 * Dashboard v2 — Mission Control home.
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
import { SpendSparkline } from "@/components/spend-sparkline";
import { PageHeader } from "@/components/page-header";
import { LiveBadge } from "@/components/live-badge";

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
      <PageHeader
        title="Mission Control"
        description="All autonomous activity in one pane."
        badge={<LiveBadge variant="live" />}
        actions={
          <>
            <Button asChild>
              <Link href="/v2/pipeline">
                <Plus aria-hidden="true" /> New task
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/admin/users">
                <UserPlus aria-hidden="true" /> Invite user
              </Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/v2/audit">
                <FileText aria-hidden="true" /> Audit
              </Link>
            </Button>
          </>
        }
      />

      {/* KPI grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {KPIs.map((k) => {
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
                {k.label === "Token Spend" && <SpendSparkline />}
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
            {/* TODO: swap mock check when API wires */}
            <ul className="space-y-2 font-mono text-sm">
              {RECENT_EVENTS.map((e, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between border-b border-[var(--border-subtle,#52525b)] pb-2 last:border-0"
                >
                  <span className="text-[var(--fg-muted,#a1a1aa)]">{e.ts}</span>
                  <span className="flex-1 px-4">{e.type}</span>
                  <span className="mr-3 text-[var(--fg-muted,#a1a1aa)]">
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
              <Keyboard aria-hidden="true" /> Shortcuts
            </CardTitle>
            <CardDescription>Keyboard first.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm" aria-label="Keyboard shortcuts">
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
                  <kbd className="rounded border border-[var(--border-subtle,#52525b)] px-2 py-0.5 text-xs font-mono">
                    {k}
                  </kbd>
                  <span className="text-[var(--fg-muted,#a1a1aa)]">{v}</span>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
