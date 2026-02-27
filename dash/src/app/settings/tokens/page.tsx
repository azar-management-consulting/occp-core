"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { TokenInfo, TokenListResult, TokenStoreResult } from "@/lib/api";
import { useT } from "@/lib/i18n";

const PROVIDERS = [
  { id: "anthropic", label: "Anthropic (Claude)", placeholder: "sk-ant-..." },
  { id: "openai", label: "OpenAI", placeholder: "sk-..." },
];

export default function TokensPage() {
  const t = useT();
  const [tokens, setTokens] = useState<TokenInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [validating, setValidating] = useState<string | null>(null);
  const [validationResults, setValidationResults] = useState<
    Record<string, { valid: boolean; detail: string }>
  >({});
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Form state
  const [provider, setProvider] = useState("anthropic");
  const [tokenValue, setTokenValue] = useState("");
  const [label, setLabel] = useState("");

  const loadTokens = useCallback(async () => {
    try {
      const data: TokenListResult = await api.listTokens();
      setTokens(data.tokens);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  useEffect(() => {
    if (toast) {
      const id = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(id);
    }
  }, [toast]);

  const handleStore = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenValue.trim()) return;
    setSaving(true);
    try {
      const result: TokenStoreResult = await api.storeToken(provider, tokenValue, label);
      if (result.stored) {
        setToast({ type: "success", msg: t.onboarding.tokenStored });
        setTokenValue("");
        setLabel("");
        await loadTokens();
      }
    } catch (err) {
      setToast({ type: "error", msg: (err as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const handleRevoke = async (prov: string) => {
    setRevoking(prov);
    try {
      await api.revokeToken(prov);
      setToast({ type: "success", msg: t.onboarding.tokenRevoked });
      await loadTokens();
    } catch (err) {
      setToast({ type: "error", msg: (err as Error).message });
    } finally {
      setRevoking(null);
    }
  };

  const handleValidate = async (prov: string) => {
    setValidating(prov);
    try {
      const result = await api.validateToken(prov);
      setValidationResults((prev) => ({
        ...prev,
        [prov]: { valid: result.valid, detail: result.detail },
      }));
    } catch (err) {
      setValidationResults((prev) => ({
        ...prev,
        [prov]: { valid: false, detail: (err as Error).message },
      }));
    } finally {
      setValidating(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-2 rounded font-mono text-xs border transition-all ${
            toast.type === "success"
              ? "bg-occp-success/10 text-occp-success border-occp-success/30"
              : "bg-occp-danger/10 text-occp-danger border-occp-danger/30"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="space-y-1">
        <h1 className="font-pixel text-[14px] text-occp-primary tracking-wider uppercase">
          {t.onboarding.storeToken}
        </h1>
        <p className="text-xs text-[var(--text-muted)] font-mono">
          {t.onboarding.storeTokenDesc}
        </p>
      </div>

      {/* Store Token Form */}
      <form onSubmit={handleStore} className="retro-card p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider uppercase">
              {t.onboarding.tokenProvider}
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-occp-dark/50 border border-occp-muted/20 rounded px-3 py-2 font-mono text-xs text-[var(--text-primary)] focus:border-occp-primary/50 focus:outline-none"
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider uppercase">
              {t.onboarding.tokenLabel}
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Production Key"
              className="w-full bg-occp-dark/50 border border-occp-muted/20 rounded px-3 py-2 font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/40 focus:border-occp-primary/50 focus:outline-none"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider uppercase">
            {t.onboarding.tokenKey}
          </label>
          <input
            type="password"
            value={tokenValue}
            onChange={(e) => setTokenValue(e.target.value)}
            placeholder={PROVIDERS.find((p) => p.id === provider)?.placeholder || ""}
            required
            className="w-full bg-occp-dark/50 border border-occp-muted/20 rounded px-3 py-2 font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/40 focus:border-occp-primary/50 focus:outline-none"
          />
          <p className="text-[10px] text-[var(--text-muted)]/60 font-mono">
            AES-256-GCM encrypted at rest. Never stored in plaintext.
          </p>
        </div>

        <button
          type="submit"
          disabled={saving || !tokenValue.trim()}
          className="retro-btn-primary text-xs disabled:opacity-50"
        >
          {saving ? "..." : t.onboarding.storeToken}
        </button>
      </form>

      {/* Stored Tokens */}
      <div className="retro-card p-5 space-y-4">
        <h2 className="font-pixel text-[11px] text-occp-accent tracking-wider uppercase">
          STORED TOKENS
        </h2>

        {loading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-3 bg-occp-muted/20 rounded w-48" />
            <div className="h-3 bg-occp-muted/10 rounded w-64" />
          </div>
        ) : tokens.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)] font-mono">
            No tokens stored yet. Add your first LLM provider key above.
          </p>
        ) : (
          <div className="space-y-2">
            {tokens.map((tk) => (
              <div
                key={tk.id}
                className="flex items-center justify-between p-3 rounded border border-occp-muted/15 bg-occp-dark/30"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      tk.is_active ? "bg-occp-success" : "bg-occp-muted/30"
                    }`}
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-[var(--text-primary)] font-bold">
                        {tk.provider.toUpperCase()}
                      </span>
                      {tk.label && (
                        <span className="font-mono text-[10px] text-[var(--text-muted)]">
                          {tk.label}
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-[10px] text-[var(--text-muted)]">
                      {tk.masked_value}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Validation result */}
                  {validationResults[tk.provider] && (
                    <span
                      className={`font-pixel text-[8px] px-1.5 py-0.5 rounded ${
                        validationResults[tk.provider].valid
                          ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                          : "bg-occp-danger/10 text-occp-danger border border-occp-danger/20"
                      }`}
                    >
                      {validationResults[tk.provider].valid ? "VALID" : "INVALID"}
                    </span>
                  )}
                  <button
                    onClick={() => handleValidate(tk.provider)}
                    disabled={validating === tk.provider}
                    className="font-pixel text-[9px] text-occp-accent px-2 py-0.5 rounded bg-occp-accent/10 border border-occp-accent/20 hover:bg-occp-accent/20 transition-all disabled:opacity-50"
                  >
                    {validating === tk.provider ? "..." : "TEST"}
                  </button>
                  <button
                    onClick={() => handleRevoke(tk.provider)}
                    disabled={revoking === tk.provider}
                    className="font-pixel text-[9px] text-occp-danger px-2 py-0.5 rounded bg-occp-danger/10 border border-occp-danger/20 hover:bg-occp-danger/20 transition-all disabled:opacity-50"
                  >
                    {revoking === tk.provider ? "..." : "REVOKE"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
