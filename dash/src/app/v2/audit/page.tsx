/**
 * Dashboard v2 — Audit log viewer.
 *
 * Reverse-chronological, searchable (search is form-stub; wire to query
 * params in follow-up). Hash-chain verification lives in the legacy route
 * until ported.
 */
import Link from "next/link";
import { ScrollText, Download, Search } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Decision = "allow" | "deny" | "approve" | "n/a";

type AuditRow = {
  ts: string;
  taskId: string;
  actor: string;
  action: string;
  decision: Decision;
};

/* Mock data — replace with SSE/fetch */
const ENTRIES: AuditRow[] = [
  { ts: "2026-04-21T08:42:11Z", taskId: "task-042", actor: "eng-core", action: "pipeline.start", decision: "allow" },
  { ts: "2026-04-21T08:41:55Z", taskId: "task-041", actor: "wp-web", action: "tool.call:wp.post.update", decision: "allow" },
  { ts: "2026-04-21T08:41:30Z", taskId: "task-040", actor: "content-forge", action: "pipeline.complete", decision: "n/a" },
  { ts: "2026-04-21T08:40:12Z", taskId: "task-039", actor: "hitl", action: "approval.request", decision: "approve" },
  { ts: "2026-04-21T08:39:44Z", taskId: "task-038", actor: "policy-engine", action: "gate.eval", decision: "deny" },
  { ts: "2026-04-21T08:38:09Z", taskId: "task-037", actor: "mcp-bridge", action: "tool.call:fs.write", decision: "allow" },
  { ts: "2026-04-21T08:36:02Z", taskId: "task-036", actor: "eng-core", action: "pipeline.complete", decision: "n/a" },
];

const DECISION_STYLES: Record<Decision, string> = {
  allow: "bg-green-500/10 text-green-400 border-green-500/30",
  deny: "bg-red-500/10 text-red-400 border-red-500/30",
  approve: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  "n/a": "bg-white/5 text-[var(--fg-muted,#999)] border-[var(--border-subtle,#333)]",
};

export default function AuditV2Page() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            <ScrollText className="inline-block mr-2 -mt-1" /> Audit log
          </h1>
          <p className="text-[var(--fg-muted,#999)]">
            Immutable, hash-chained decision record. {ENTRIES.length} most
            recent entries.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="#">
            <Download /> Export CSV
          </Link>
        </Button>
      </div>

      {/* Search bar */}
      <form action="/audit" className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fg-muted,#999)]"
            size={16}
          />
          <input
            name="q"
            type="search"
            placeholder="Search by task_id, actor, action…"
            className="w-full rounded border border-[var(--border-subtle,#333)] bg-transparent py-2 pl-9 pr-3 text-sm outline-none focus:border-white/60"
          />
        </div>
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>

      {/* Log table */}
      <Card>
        <CardHeader>
          <CardTitle>Recent entries</CardTitle>
          <CardDescription>Reverse chronological.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm font-mono">
              <thead className="text-xs uppercase tracking-wider text-[var(--fg-muted,#999)]">
                <tr className="border-b border-[var(--border-subtle,#333)]">
                  <th className="py-2 pr-4 text-left font-medium">Timestamp</th>
                  <th className="py-2 pr-4 text-left font-medium">Task</th>
                  <th className="py-2 pr-4 text-left font-medium">Actor</th>
                  <th className="py-2 pr-4 text-left font-medium">Action</th>
                  <th className="py-2 text-left font-medium">Decision</th>
                </tr>
              </thead>
              <tbody>
                {ENTRIES.map((e) => (
                  <tr
                    key={`${e.ts}-${e.taskId}-${e.action}`}
                    className="border-b border-[var(--border-subtle,#333)] last:border-0 hover:bg-white/[0.02]"
                  >
                    <td className="py-3 pr-4 text-[var(--fg-muted,#999)]">
                      {e.ts}
                    </td>
                    <td className="py-3 pr-4">
                      <Link
                        href={`/pipeline/${e.taskId}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {e.taskId}
                      </Link>
                    </td>
                    <td className="py-3 pr-4">{e.actor}</td>
                    <td className="py-3 pr-4">{e.action}</td>
                    <td className="py-3">
                      <span
                        className={`inline-block rounded border px-2 py-0.5 text-xs uppercase tracking-wider ${DECISION_STYLES[e.decision]}`}
                      >
                        {e.decision}
                      </span>
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
