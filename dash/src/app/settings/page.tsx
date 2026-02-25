"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LLMHealthV2, LLMProviderStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";

const TOOL_GROUPS = [
  { id: "runtime", tools: ["bash", "python", "node"], icon: "⚙" },
  { id: "filesystem", tools: ["read", "write", "glob", "grep"], icon: "📁" },
  { id: "web", tools: ["fetch", "search", "scrape"], icon: "🌐" },
  { id: "ui", tools: ["browser", "screenshot", "click"], icon: "🖥" },
];

export default function SettingsPage() {
  const [llm, setLlm] = useState<LLMHealthV2 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const t = useT();

  const loadLLM = async () => {
    try {
      const data = await api.llmHealthV2();
      setLlm(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load LLM health");
    }
  };

  useEffect(() => {
    loadLLM();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-pixel text-sm tracking-wide">
          <span className="text-occp-primary text-glow">{t.settings.title}</span>
        </h1>
        <p className="section-desc mt-2">{t.settings.subtitle}</p>
      </div>

      {/* Error */}
      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4 flex justify-between items-center">
          <div>
            <span className="font-pixel text-[11px] text-occp-danger mr-2">✗ {t.common.error}</span>
            <span className="text-sm text-occp-danger font-mono">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] font-mono"
          >
            [{t.common.dismiss}]
          </button>
        </div>
      )}

      {/* LLM Providers Section */}
      <div className="retro-card p-6 space-y-4 crt-glow">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
              {t.settings.llmTitle}
            </h2>
            <p className="section-desc mt-1">{t.settings.llmDesc}</p>
          </div>
          {llm && (
            <span
              className={`font-pixel text-[11px] px-2 py-1 rounded ${
                llm.status === "ok"
                  ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                  : llm.status === "fallback"
                    ? "bg-occp-warning/10 text-occp-warning border border-occp-warning/20"
                    : "bg-occp-danger/10 text-occp-danger border border-occp-danger/20"
              }`}
            >
              {llm.status.toUpperCase()}
            </span>
          )}
        </div>

        {llm ? (
          <div className="space-y-3">
            {/* Active Provider Badge */}
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-[var(--text-muted)]">{t.settings.status}:</span>
              <span className="text-occp-primary font-bold">{llm.active_provider}</span>
              {llm.token_present && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-occp-success/10 text-occp-success border border-occp-success/20">
                  TOKEN ✓
                </span>
              )}
            </div>

            {/* Provider List */}
            <div className="space-y-2">
              {llm.providers.map((provider: LLMProviderStatus) => (
                <div
                  key={provider.provider}
                  className="flex items-center justify-between p-3 rounded bg-occp-dark/50 border border-occp-muted/20"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        provider.status === "ok"
                          ? "bg-occp-success"
                          : provider.status === "error"
                            ? "bg-occp-danger"
                            : "bg-occp-muted/40"
                      }`}
                    />
                    <div>
                      <span className="font-mono text-sm font-bold">{provider.provider}</span>
                      {provider.model && (
                        <span className="text-[11px] text-[var(--text-muted)] font-mono ml-2">
                          {t.settings.model}: {provider.model}
                        </span>
                      )}
                    </div>
                  </div>
                  <span
                    className={`font-pixel text-[10px] px-2 py-0.5 rounded ${
                      provider.configured
                        ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                        : "bg-occp-muted/10 text-[var(--text-muted)] border border-occp-muted/20"
                    }`}
                  >
                    {provider.configured ? t.settings.configured : t.settings.notConfigured}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="animate-pulse space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-occp-muted/10 rounded" />
            ))}
          </div>
        )}
      </div>

      {/* Tool Policies Section */}
      <div className="retro-card p-6 space-y-4 crt-glow">
        <div>
          <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
            {t.settings.toolsTitle}
          </h2>
          <p className="section-desc mt-1">{t.settings.toolsDesc}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {TOOL_GROUPS.map((group) => (
            <div
              key={group.id}
              className="p-4 rounded bg-occp-dark/50 border border-occp-muted/20 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-mono font-bold text-sm">
                  <span className="mr-2">{group.icon}</span>
                  {group.id.toUpperCase()}
                </h3>
                <span className="text-[10px] font-pixel px-2 py-0.5 rounded bg-occp-success/10 text-occp-success border border-occp-success/20">
                  {t.settings.active}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {group.tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[11px] px-2 py-0.5 rounded font-mono bg-occp-primary/10 text-occp-primary border border-occp-primary/20"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
