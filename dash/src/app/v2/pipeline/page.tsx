/**
 * Dashboard v2 — Pipeline runs table.
 *
 * Mirrors the legacy /pipeline route behind NEXT_PUBLIC_DASH_V2.
 * Server component: filter tabs are rendered as links (no client state yet);
 * wire to search params + SSE in follow-up.
 */
import Link from "next/link";
import { GitBranch, Plus } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type RunStatus = "running" | "passed" | "failed" | "halted";

type PipelineRun = {
  id: string;
  status: RunStatus;
  agent: string;
  started: string;
  duration: string;
  tokens: number;
  costUsd: number;
};

/* Mock data — replace with SSE/fetch */
const RUNS: PipelineRun[] = [
  { id: "task-042", status: "running", agent: "eng-core", started: "08:42:11", duration: "00:01:24", tokens: 18_420, costUsd: 0.42 },
  { id: "task-041", status: "passed", agent: "wp-web", started: "08:38:05", duration: "00:02:11", tokens: 24_180, costUsd: 0.58 },
  { id: "task-040", status: "passed", agent: "content-forge", started: "08:33:47", duration: "00:03:55", tokens: 41_905, costUsd: 1.12 },
  { id: "task-039", status: "halted", agent: "infra-ops", started: "08:27:02", duration: "00:00:38", tokens: 3_210, costUsd: 0.08 },
  { id: "task-038", status: "failed", agent: "brain-research", started: "08:19:14", duration: "00:04:02", tokens: 52_408, costUsd: 1.44 },
  { id: "task-037", status: "passed", agent: "mcp-bridge", started: "08:11:00", duration: "00:01:47", tokens: 12_055, costUsd: 0.29 },
  { id: "task-036", status: "passed", agent: "eng-core", started: "08:02:33", duration: "00:02:56", tokens: 29_770, costUsd: 0.71 },
];

const FILTERS: { key: string; label: string; count: number }[] = [
  { key: "all", label: "All", count: RUNS.length },
  { key: "running", label: "Running", count: RUNS.filter((r) => r.status === "running").length },
  { key: "passed", label: "Passed", count: RUNS.filter((r) => r.status === "passed").length },
  { key: "failed", label: "Failed", count: RUNS.filter((r) => r.status === "failed").length },
  { key: "halted", label: "Halted", count: RUNS.filter((r) => r.status === "halted").length },
];

const STATUS_STYLES: Record<RunStatus, string> = {
  running: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  passed: "bg-green-500/10 text-green-400 border-green-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/30",
  halted: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
};

export default function PipelineV2Page() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            <GitBranch className="inline-block mr-2 -mt-1" aria-hidden="true" /> Pipeline
          </h1>
          <p className="text-[var(--fg-muted,#a1a1aa)]">
            Verified Autonomy runs. Press{" "}
            <kbd className="rounded border border-[var(--border-subtle,#52525b)] px-1.5 py-0.5 text-xs">
              N
            </kbd>{" "}
            for a new task.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/pipeline?new=1">
              <Plus aria-hidden="true" /> New task
            </Link>
          </Button>
        </div>
      </div>

      {/* Filter tabs */}
      <nav aria-label="Filter pipeline runs" className="flex gap-1 border-b border-[var(--border-subtle,#52525b)]">
        {FILTERS.map((f, i) => (
          <Link
            key={f.key}
            href={f.key === "all" ? "?" : `?status=${f.key}`}
            aria-current={i === 0 ? "page" : undefined}
            className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors ${
              i === 0
                ? "border-white text-white"
                : "border-transparent text-[var(--fg-muted,#a1a1aa)] hover:text-white"
            }`}
          >
            {f.label}{" "}
            <span className="ml-1 text-xs text-[var(--fg-muted,#a1a1aa)]" aria-label={`${f.count} results`}>
              {f.count}
            </span>
          </Link>
        ))}
      </nav>

      {/* Runs table */}
      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
          <CardDescription>
            {RUNS.length} pipelines — sortable/filterable wiring lands with the
            SSE commit.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm font-mono" aria-label="Pipeline runs">
              <thead className="text-xs uppercase tracking-wider text-[var(--fg-muted,#a1a1aa)]">
                <tr className="border-b border-[var(--border-subtle,#52525b)]">
                  <th scope="col" className="py-2 pr-4 text-left font-medium">ID</th>
                  <th scope="col" className="py-2 pr-4 text-left font-medium">Status</th>
                  <th scope="col" className="py-2 pr-4 text-left font-medium">Agent</th>
                  <th scope="col" className="py-2 pr-4 text-left font-medium">Started</th>
                  <th scope="col" className="py-2 pr-4 text-left font-medium">Duration</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">Tokens</th>
                  <th scope="col" className="py-2 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {RUNS.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-[var(--border-subtle,#52525b)] last:border-0 hover:bg-white/[0.02]"
                  >
                    <td className="py-3 pr-4">
                      <Link
                        href={`/pipeline/${r.id}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {r.id}
                      </Link>
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-block rounded border px-2 py-0.5 text-xs uppercase tracking-wider ${STATUS_STYLES[r.status]}`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4">{r.agent}</td>
                    <td className="py-3 pr-4 text-[var(--fg-muted,#a1a1aa)]">
                      {r.started}
                    </td>
                    <td className="py-3 pr-4">{r.duration}</td>
                    <td className="py-3 pr-4 text-right">
                      {r.tokens.toLocaleString("en-US")}
                    </td>
                    <td className="py-3 text-right">
                      ${r.costUsd.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
