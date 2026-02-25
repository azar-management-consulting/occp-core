"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { LLMHealthV2 } from "@/lib/api";
import { useT } from "@/lib/i18n";

const ENV_KEYS = [
  { key: "OCCP_ANTHROPIC_API_KEY", provider: "anthropic", label: "Anthropic" },
  { key: "OCCP_OPENAI_API_KEY", provider: "openai", label: "OpenAI" },
];

export default function LLMSetupPage() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<LLMHealthV2 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const t = useT();

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    try {
      const data = await api.llmHealthV2();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <Link
          href="/settings"
          className="text-xs font-mono text-[var(--text-muted)] hover:text-occp-primary transition-colors"
        >
          ← Settings
        </Link>
      </div>

      <div>
        <h1 className="font-pixel text-sm tracking-wide">
          <span className="text-occp-primary text-glow">{t.settings.llmPageTitle}</span>
        </h1>
        <p className="section-desc mt-2">{t.settings.llmPageDesc}</p>
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

      {/* Environment Variables */}
      <div className="retro-card p-6 space-y-4 crt-glow">
        <div>
          <h2 className="font-pixel text-[12px] text-occp-accent tracking-wider uppercase">
            {t.settings.envVars}
          </h2>
          <p className="section-desc mt-1">
            Set these in your shell or <code className="text-occp-primary">.env</code> file before starting OCCP.
          </p>
        </div>

        <div className="space-y-3">
          {ENV_KEYS.map(({ key, provider, label }) => {
            const providerData = result?.providers.find((p) => p.provider === provider);
            const isConfigured = providerData?.configured ?? false;

            return (
              <div
                key={key}
                className="flex items-center justify-between p-4 rounded bg-occp-dark/50 border border-occp-muted/20"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold">{label}</span>
                    {result && (
                      <span
                        className={`font-pixel text-[9px] px-1.5 py-0.5 rounded ${
                          isConfigured
                            ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                            : "bg-occp-muted/10 text-[var(--text-muted)] border border-occp-muted/20"
                        }`}
                      >
                        {isConfigured ? t.settings.keyPresent : t.settings.keyMissing}
                      </span>
                    )}
                  </div>
                  <code className="text-[11px] text-[var(--text-muted)] font-mono">{key}</code>
                </div>
                <div
                  className={`w-2.5 h-2.5 rounded-full ${
                    result
                      ? isConfigured
                        ? "bg-occp-success"
                        : "bg-occp-muted/40"
                      : "bg-occp-muted/20"
                  }`}
                />
              </div>
            );
          })}
        </div>

        {/* Test Button */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleTest}
            disabled={testing}
            className="retro-btn-primary text-xs"
          >
            {testing ? t.settings.testing : t.settings.testConnection}
          </button>
          {result && !error && (
            <span
              className={`font-pixel text-[11px] px-2 py-1 rounded ${
                result.status === "ok"
                  ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                  : result.status === "fallback"
                    ? "bg-occp-warning/10 text-occp-warning border border-occp-warning/20"
                    : "bg-occp-danger/10 text-occp-danger border border-occp-danger/20"
              }`}
            >
              {result.status === "ok"
                ? t.settings.testOk
                : result.status === "fallback"
                  ? t.settings.testOk + " (FALLBACK)"
                  : t.settings.testFail}
            </span>
          )}
        </div>

        {/* Active Provider */}
        {result && (
          <div className="p-3 rounded bg-occp-primary/5 border border-occp-primary/20">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-[var(--text-muted)]">Active:</span>
              <span className="text-occp-primary font-bold">{result.active_provider}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
