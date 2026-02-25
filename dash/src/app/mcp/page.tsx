"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MCPConnector, MCPInstallResult } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function MCPPage() {
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [installing, setInstalling] = useState<string | null>(null);
  const [installResult, setInstallResult] = useState<MCPInstallResult | null>(null);
  const t = useT();

  const loadCatalog = async () => {
    try {
      const res = await api.mcpCatalog();
      setConnectors(res.connectors);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load MCP catalog");
    }
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  const handleInstall = async (connectorId: string) => {
    setInstalling(connectorId);
    setError(null);
    setInstallResult(null);
    try {
      const result = await api.mcpInstall(connectorId);
      setInstallResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Install failed");
    } finally {
      setInstalling(null);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-pixel text-sm tracking-wide">
          <span className="text-occp-primary text-glow">{t.mcp.title}</span>
        </h1>
        <p className="section-desc mt-2">{t.mcp.subtitle}</p>
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

      {/* Install Result Modal */}
      {installResult && (
        <div className="retro-card border-occp-success/40 bg-occp-success/5 p-6 space-y-4 crt-glow">
          <div className="flex items-center justify-between">
            <h2 className="font-pixel text-[12px] text-occp-success tracking-wider uppercase">
              ✓ {installResult.connector_name}
            </h2>
            <button
              onClick={() => setInstallResult(null)}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] font-mono"
            >
              [{t.common.dismiss}]
            </button>
          </div>
          <div>
            <h3 className="font-pixel text-[11px] text-occp-accent mb-2">{t.mcp.configTitle}</h3>
            <p className="text-xs text-[var(--text-muted)] font-mono mb-3">{t.mcp.configDesc}</p>
            <pre className="bg-occp-dark/80 border border-occp-muted/30 rounded p-4 text-xs font-mono text-occp-primary overflow-x-auto">
              {JSON.stringify(installResult.mcp_json, null, 2)}
            </pre>
          </div>
          {installResult.instructions && (
            <p className="text-xs text-[var(--text-muted)] font-mono">{installResult.instructions}</p>
          )}
        </div>
      )}

      {/* Connector Grid */}
      {connectors.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {connectors.map((connector) => (
            <div key={connector.id} className="retro-card p-5 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-mono font-bold text-sm">{connector.name}</h3>
                  <span className="text-[11px] px-2 py-0.5 rounded font-mono bg-occp-accent/10 text-occp-accent border border-occp-accent/20 mt-1 inline-block">
                    {connector.category}
                  </span>
                </div>
              </div>

              <p className="text-xs text-[var(--text-muted)] font-mono leading-relaxed">
                {connector.description}
              </p>

              {connector.package && (
                <p className="text-[11px] text-[var(--text-muted)] font-mono">
                  <span className="text-occp-accent">{t.mcp.package}:</span> {connector.package}
                </p>
              )}

              <button
                onClick={() => handleInstall(connector.id)}
                disabled={installing === connector.id}
                className="retro-btn-primary w-full text-center"
              >
                {installing === connector.id ? t.mcp.installing : t.mcp.install}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="retro-card p-12 text-center crt-glow">
          <p className="font-pixel text-[12px] text-[var(--text-muted)]">
            {t.mcp.noConnectors}
          </p>
        </div>
      )}
    </div>
  );
}
