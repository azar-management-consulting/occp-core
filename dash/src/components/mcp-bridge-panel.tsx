"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface BridgeStats {
  total: number;
  ok: number;
  error: number;
  denied: number;
  timeout: number;
  tools_registered: number;
  success_rate: number;
}

/**
 * L4 MCP Runtime Bridge status panel.
 *
 * Shows the 7 built-in tools registered with the server-side MCP bridge,
 * live dispatch stats, and success rate. Added in v0.9.0 when L4
 * Autonomous Control Plane milestone was reached.
 */
export function MCPBridgePanel() {
  const [tools, setTools] = useState<string[]>([]);
  const [stats, setStats] = useState<BridgeStats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .mcpBridgeTools()
        .then((d) => {
          setTools(d.tools);
          setStats(d.stats);
          setErr(null);
        })
        .catch((e: unknown) =>
          setErr(e instanceof Error ? e.message : "Failed to load"),
        );
    load();
    const i = setInterval(load, 10_000);
    return () => clearInterval(i);
  }, []);

  return (
    <div className="space-y-3">
      <div>
        <h2 className="font-pixel text-[13px] text-occp-accent tracking-wider uppercase">
          L4 MCP Runtime Bridge
        </h2>
        <p className="section-desc">
          Server-side tool dispatch surface. Policy-gated, audit-logged,
          parallel execution via semaphore (max=8).
        </p>
      </div>

      {err && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-3">
          <span className="text-xs text-occp-danger font-mono">{err}</span>
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="retro-card p-5">
            <p className="text-[12px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
              Tools
            </p>
            <p className="text-xl font-bold font-mono mt-1.5 text-occp-primary">
              {stats.tools_registered}
            </p>
          </div>
          <div className="retro-card p-5">
            <p className="text-[12px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
              Dispatches
            </p>
            <p className="text-xl font-bold font-mono mt-1.5 text-occp-accent">
              {stats.total}
            </p>
          </div>
          <div className="retro-card p-5">
            <p className="text-[12px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
              Success %
            </p>
            <p className="text-xl font-bold font-mono mt-1.5 text-occp-success">
              {(stats.success_rate * 100).toFixed(1)}%
            </p>
          </div>
          <div className="retro-card p-5">
            <p className="text-[12px] text-[var(--text-muted)] font-mono uppercase tracking-widest">
              Denied
            </p>
            <p
              className={`text-xl font-bold font-mono mt-1.5 ${
                stats.denied > 0 ? "text-occp-warning" : "text-[var(--text-muted)]"
              }`}
            >
              {stats.denied}
            </p>
          </div>
        </div>
      )}

      {tools.length > 0 && (
        <div className="retro-card p-4">
          <p className="text-[11px] font-pixel text-[var(--text-muted)] uppercase tracking-wider mb-3">
            Registered Tools
          </p>
          <div className="flex flex-wrap gap-2">
            {tools.map((t) => (
              <code
                key={t}
                className="text-[11px] font-mono bg-[var(--bg-muted,rgba(0,0,0,0.25))] text-occp-accent px-2 py-1 rounded border border-occp-primary/20"
              >
                {t}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
