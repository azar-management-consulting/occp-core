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
import { PageHeader } from "@/components/page-header";
import { LiveBadge } from "@/components/live-badge";
import { EmptyState } from "@/components/empty-state";
import { StatusPill, type StatusPillVariant } from "@/components/status-pill";
import { HelpBubble } from "@/components/onboarding/help-bubble";

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
  "n/a": "bg-white/5 text-[var(--fg-muted,#a1a1aa)] border-[var(--border-subtle,#52525b)]",
};

export default function AuditV2Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Audit log"
        description={`Immutable, hash-chained decision record. ${ENTRIES.length} most recent entries.`}
        badge={<LiveBadge variant="live" />}
        actions={
          /* TODO(a11y): href="#" is a stub — replace with /api/audit/export once endpoint is wired */
          <Button asChild variant="outline">
            <Link href="#">
              <Download aria-hidden="true" /> Export CSV
            </Link>
          </Button>
        }
      />

      {/* Search bar */}
      <form action="/audit" className="flex items-center gap-2">
        <div className="relative flex-1">
          <label htmlFor="audit-search" className="sr-only">
            Search audit log by task ID, actor, or action
          </label>
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fg-muted,#a1a1aa)]"
            size={16}
            aria-hidden="true"
          />
          <input
            id="audit-search"
            name="q"
            type="search"
            placeholder="Search by task_id, actor, action…"
            className="w-full rounded border border-[var(--border-subtle,#52525b)] bg-transparent py-2 pl-9 pr-3 text-sm outline-none transition-colors duration-150 focus:border-white/60 focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)]"
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
          {/* TODO: swap mock check when API wires */}
          {ENTRIES.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="No audit entries yet"
              description="Audit rows appear as soon as your first pipeline task runs. They are immutable and hash-chained."
              action={
                <Button asChild>
                  <Link href="/v2/pipeline">Go to Pipeline</Link>
                </Button>
              }
              helpBubble={{
                hintKey: "empty_audit",
                variant: "info",
                title: "Hash-chained audit log",
                body: "Run a task first — its audit row will appear here within seconds.",
              }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono" aria-label="Audit log entries">
                <thead className="sticky top-0 z-10 bg-[var(--bg-elev,#18181b)]/80 backdrop-blur-sm text-xs uppercase tracking-wider text-[var(--fg-muted,#a1a1aa)]">
                  <tr className="border-b border-[var(--border-subtle,#52525b)]">
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Timestamp</th>
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Task</th>
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Actor</th>
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Action</th>
                    <th scope="col" className="py-2 text-left font-medium">Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {ENTRIES.map((e, idx) => (
                    <tr
                      key={`${e.ts}-${e.taskId}-${e.action}`}
                      data-tour={idx === 0 ? "first-audit-row" : undefined}
                      className="border-b border-[var(--border-subtle,#52525b)] last:border-0 hover:bg-white/[0.03] transition-colors duration-150 cursor-pointer"
                    >
                      <td className="py-3 pr-4 text-[var(--fg-muted,#a1a1aa)]">
                        {e.ts}
                      </td>
                      <td className="py-3 pr-4">
                        <Link
                          href={`/pipeline/${e.taskId}`}
                          className="underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] rounded-sm"
                        >
                          {e.taskId}
                        </Link>
                      </td>
                      <td className="py-3 pr-4">{e.actor}</td>
                      <td className="py-3 pr-4">{e.action}</td>
                      <td className="py-3">
                        <StatusPill variant={e.decision as StatusPillVariant} compact />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Hint 5: First audit row */}
      <HelpBubble
        hintKey="auditrow"
        anchor='[data-tour="first-audit-row"]'
        variant="info"
        placement="top"
        title="Tamper-proof record"
        body="Every row is SHA-256 hash-chained to the previous entry. Click a row to inspect the chain proof."
      />
    </div>
  );
}
