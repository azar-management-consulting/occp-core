/**
 * Dashboard v2 — Agent grid.
 *
 * 8 cards for the core OCCP agent roster. Server component; real agent
 * registry + last-run metrics wire in follow-up.
 */
import Link from "next/link";
import { Cpu, Plus } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { LiveBadge } from "@/components/live-badge";
import { EmptyState } from "@/components/empty-state";

type AgentStatus = "active" | "idle";

type Agent = {
  type: string;
  displayName: string;
  description: string;
  lastRun: string;
  successRate: number;
  status: AgentStatus;
};

/* Mock data — replace with SSE/fetch */
const AGENTS: Agent[] = [
  { type: "eng-core", displayName: "Eng Core", description: "Codegen, refactor, tests", lastRun: "2m ago", successRate: 0.97, status: "active" },
  { type: "wp-web", displayName: "WP Web", description: "WordPress / Elementor ops", lastRun: "5m ago", successRate: 0.94, status: "active" },
  { type: "content-forge", displayName: "Content Forge", description: "Copy, SEO, translations", lastRun: "11m ago", successRate: 0.91, status: "idle" },
  { type: "infra-ops", displayName: "Infra Ops", description: "Deploy, monitor, SRE", lastRun: "23m ago", successRate: 0.88, status: "idle" },
  { type: "brain-research", displayName: "Brain Research", description: "Deep research, citations", lastRun: "4m ago", successRate: 0.93, status: "active" },
  { type: "mcp-bridge", displayName: "MCP Bridge", description: "Tool fan-out across servers", lastRun: "1m ago", successRate: 0.99, status: "active" },
  { type: "autodev", displayName: "AutoDev", description: "Autonomous feature runner", lastRun: "38m ago", successRate: 0.85, status: "idle" },
  { type: "hitl", displayName: "HITL", description: "Human-in-the-loop approvals", lastRun: "1h ago", successRate: 1.0, status: "idle" },
];

export default function AgentsV2Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Agents"
        description={`${AGENTS.length} agents registered.`}
        badge={<LiveBadge variant="live" />}
        actions={
          <Button asChild>
            <Link href="/agents?new=1">
              <Plus aria-hidden="true" /> Register agent
            </Link>
          </Button>
        }
      />

      {/* Agent grid */}
      {/* TODO: swap mock check when API wires */}
      {AGENTS.length === 0 ? (
        <EmptyState
          icon={Cpu}
          title="No agents registered"
          description="Register your first agent to start running autonomous tasks."
          action={
            <Button asChild>
              <Link href="/agents?new=1">
                <Plus aria-hidden="true" /> Register agent
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {AGENTS.map((a) => (
            <Card
              key={a.type}
              className="transition-colors duration-150 hover:border-white/30"
            >
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-sm font-medium">
                    {a.displayName}
                  </CardTitle>
                  <CardDescription className="mt-1 font-mono text-xs">
                    {a.type}
                  </CardDescription>
                </div>
                <LiveBadge
                  variant={a.status === "active" ? "live" : "idle"}
                  label={a.status}
                />
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-xs text-[var(--fg-muted,#a1a1aa)]">
                  {a.description}
                </p>
                <div className="flex items-center justify-between border-t border-[var(--border-subtle,#52525b)] pt-3 text-xs font-mono">
                  <div>
                    <div className="text-[var(--fg-muted,#a1a1aa)]">Last run</div>
                    <div className="mt-0.5">{a.lastRun}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[var(--fg-muted,#a1a1aa)]">Success</div>
                    <div className="mt-0.5 font-bold">
                      {(a.successRate * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
