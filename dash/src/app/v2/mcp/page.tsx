/**
 * Dashboard v2 — Connected MCP servers.
 *
 * Shows remote/proxy MCP connection state. "Connect server" routes to the
 * legacy catalog until a v2 install flow lands.
 */
import Link from "next/link";
import { Suspense } from "react";
import { Plug, Plus } from "lucide-react";
import { TaskCreateDialog } from "@/components/task-create-dialog";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { HelpBubble } from "@/components/onboarding/help-bubble";

type MCPStatus = "connected" | "disconnected";

type MCPServer = {
  name: string;
  status: MCPStatus;
  toolsCount: number;
  lastPing: string;
  version: string;
};

/* Mock data — replace with SSE/fetch */
const SERVERS: MCPServer[] = [
  { name: "wordpress-azar", status: "disconnected", toolsCount: 42, lastPing: "12m ago", version: "0.4.1" },
  { name: "wordpress-felnottkepzes", status: "disconnected", toolsCount: 42, lastPing: "12m ago", version: "0.4.1" },
  { name: "wordpress-magyarorszag", status: "connected", toolsCount: 42, lastPing: "3s ago", version: "0.4.1" },
  { name: "context7", status: "connected", toolsCount: 2, lastPing: "1s ago", version: "1.2.0" },
  { name: "GitGuardianDeveloper", status: "connected", toolsCount: 5, lastPing: "5s ago", version: "0.9.3" },
  { name: "ref", status: "connected", toolsCount: 2, lastPing: "2s ago", version: "0.3.0" },
  { name: "bio-research", status: "connected", toolsCount: 18, lastPing: "8s ago", version: "0.2.0" },
];

const STATUS_STYLES: Record<MCPStatus, string> = {
  connected: "bg-green-500/10 text-green-400 border-green-500/30",
  disconnected: "bg-red-500/10 text-red-400 border-red-500/30",
};

export default function MCPV2Page() {
  const connected = SERVERS.filter((s) => s.status === "connected").length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="MCP servers"
        description={`${connected} of ${SERVERS.length} servers online.`}
        actions={
          <Button asChild data-tour="mcp-connect-button">
            <Link href="/mcp?new=1">
              <Plus aria-hidden="true" /> Connect server
            </Link>
          </Button>
        }
      />

      {/* Servers table */}
      <Card>
        <CardHeader>
          <CardTitle>Connected servers</CardTitle>
          <CardDescription>
            Tool counts and ping status refresh on the SSE wire.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* TODO: swap mock check when API wires */}
          {SERVERS.length === 0 ? (
            <EmptyState
              icon={Plug}
              title="No MCP servers connected"
              description="Connect an MCP server to give your agents verified tool access to Slack, GitHub, and more."
              action={
                <Button asChild>
                  <Link href="/mcp?new=1">
                    <Plus aria-hidden="true" /> Connect a server
                  </Link>
                </Button>
              }
              helpBubble={{
                hintKey: "empty_mcp",
                variant: "pro-tip",
                title: "Tools your agents can call",
                body: "MCP servers are the tools your agents call. All tool calls are logged to the audit trail.",
              }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono" aria-label="MCP server connections">
                <thead className="text-xs uppercase tracking-wider text-[var(--fg-muted,#a1a1aa)]">
                  <tr className="border-b border-[var(--border-subtle,#52525b)]">
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Name</th>
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Status</th>
                    <th scope="col" className="py-2 pr-4 text-right font-medium">Tools</th>
                    <th scope="col" className="py-2 pr-4 text-left font-medium">Last ping</th>
                    <th scope="col" className="py-2 text-left font-medium">Version</th>
                  </tr>
                </thead>
                <tbody>
                  {SERVERS.map((s) => (
                    <tr
                      key={s.name}
                      className="border-b border-[var(--border-subtle,#52525b)] last:border-0 hover:bg-white/[0.02] transition-colors duration-150"
                    >
                      <td className="py-3 pr-4 font-bold">{s.name}</td>
                      <td className="py-3 pr-4">
                        <span
                          className={`inline-block rounded border px-2 py-0.5 text-xs uppercase tracking-wider ${STATUS_STYLES[s.status]}`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-right">{s.toolsCount}</td>
                      <td className="py-3 pr-4 text-[var(--fg-muted,#a1a1aa)]">
                        {s.lastPing}
                      </td>
                      <td className="py-3 text-[var(--fg-muted,#a1a1aa)]">
                        {s.version}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Hint 6: Connect server */}
      <HelpBubble
        hintKey="mcpconnect"
        anchor='[data-tour="mcp-connect-button"]'
        variant="pro-tip"
        placement="bottom"
        title="Expand your agent's toolbelt"
        body="Connect Slack, GitHub, or Supabase as MCP servers. Agents call these tools under full policy control."
      />

      {/* ?new=1 — placeholder dialog until iter-12 wires the real form */}
      <Suspense fallback={null}>
        <TaskCreateDialog variant="mcp" />
      </Suspense>
    </div>
  );
}
