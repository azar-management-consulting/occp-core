"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LLMHealthData, LLMProviderHealth } from "@/lib/api";

const PROVIDER_META: Record<string, { label: string; icon: string }> = {
  anthropic: { label: "ANTHROPIC", icon: "◆" },
  openai: { label: "OPENAI", icon: "◇" },
  echo: { label: "ECHO", icon: "○" },
};

function HealthBar({ rate }: { rate: number }) {
  const segments = 10;
  const filled = Math.round(rate * segments);
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-3 rounded-[1px] transition-all duration-300 ${
            i < filled
              ? rate >= 0.9
                ? "bg-occp-success shadow-[0_0_4px_rgba(117,206,100,0.4)]"
                : rate >= 0.7
                  ? "bg-occp-warning shadow-[0_0_4px_rgba(237,241,113,0.3)]"
                  : "bg-occp-danger shadow-[0_0_4px_rgba(210,125,111,0.4)]"
              : "bg-[var(--muted)]/30"
          }`}
        />
      ))}
    </div>
  );
}

function ProviderRow({ name, health }: { name: string; health: LLMProviderHealth }) {
  const meta = PROVIDER_META[name] || { label: name.toUpperCase(), icon: "●" };
  return (
    <div className="retro-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-sm ${health.healthy ? "text-occp-success" : "text-occp-danger"}`}>
            {meta.icon}
          </span>
          <span className="font-pixel text-[9px] tracking-wider">{meta.label}</span>
        </div>
        <span
          className={`text-[9px] font-pixel px-2 py-0.5 rounded tracking-wider ${
            health.healthy
              ? "bg-occp-success/15 text-occp-success border border-occp-success/30"
              : "bg-occp-danger/15 text-occp-danger border border-occp-danger/30"
          }`}
        >
          {health.healthy ? "ONLINE" : "DEGRADED"}
        </span>
      </div>

      <HealthBar rate={health.success_rate} />

      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-[9px] text-[var(--text-muted)] font-mono uppercase">Calls</p>
          <p className="text-sm font-bold font-mono text-occp-primary">{health.total_calls}</p>
        </div>
        <div>
          <p className="text-[9px] text-[var(--text-muted)] font-mono uppercase">Latency</p>
          <p className="text-sm font-bold font-mono text-occp-accent">
            {health.avg_latency_ms > 0 ? `${Math.round(health.avg_latency_ms)}ms` : "—"}
          </p>
        </div>
        <div>
          <p className="text-[9px] text-[var(--text-muted)] font-mono uppercase">Errors</p>
          <p className={`text-sm font-bold font-mono ${health.failures > 0 ? "text-occp-danger" : "text-occp-success"}`}>
            {health.failures}
          </p>
        </div>
      </div>
    </div>
  );
}

export function LLMHealthPanel() {
  const [data, setData] = useState<LLMHealthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .llmHealth()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));

    // Auto-refresh every 30s
    const interval = setInterval(() => {
      api.llmHealth().then(setData).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="space-y-3">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          LLM Providers
        </h2>
        <div className="retro-card p-6 text-center crt-glow">
          <p className="font-pixel text-[9px] text-[var(--text-muted)] animate-pulse">
            LOADING PROVIDER STATUS...
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-3">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          LLM Providers
        </h2>
        <div className="retro-card p-6 text-center border-occp-danger/30">
          <p className="font-pixel text-[9px] text-occp-danger">PROVIDER STATUS UNAVAILABLE</p>
        </div>
      </div>
    );
  }

  const providers = Object.entries(data.providers);
  // Sort: anthropic first, openai second, echo last
  const order = ["anthropic", "openai", "echo"];
  providers.sort((a, b) => {
    const ai = order.indexOf(a[0]);
    const bi = order.indexOf(b[0]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-pixel text-[10px] text-occp-accent tracking-wider uppercase">
          LLM Providers
        </h2>
        <span
          className={`text-[9px] font-pixel px-2 py-0.5 rounded tracking-wider ${
            data.status === "healthy"
              ? "text-occp-success"
              : "text-occp-warning"
          }`}
        >
          {data.status === "healthy" ? "● ALL SYSTEMS GO" : "▲ DEGRADED"}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {providers.map(([name, health]) => (
          <ProviderRow key={name} name={name} health={health} />
        ))}
      </div>
    </div>
  );
}
