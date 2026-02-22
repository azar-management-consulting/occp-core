"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/lib/api";
import { AuditTable } from "@/components/audit-table";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [chainValid, setChainValid] = useState(true);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.auditLog();
      setEntries(data.entries);
      setChainValid(data.chain_valid);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit log");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">AUDIT</span>{" "}
            <span className="text-[var(--text)]">LOG</span>
          </h1>
          <p className="text-[var(--text-muted)] text-xs font-mono mt-2">
            Tamper-evident SHA-256 hash chain of all pipeline operations
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-[var(--text-muted)] font-mono">
            {total} {total === 1 ? "entry" : "entries"}
          </span>
          <button onClick={load} className="retro-btn text-[10px] font-pixel tracking-wider">
            REFRESH
          </button>
        </div>
      </div>

      {error && (
        <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4">
          <span className="font-pixel text-[9px] text-occp-danger mr-2">?ERROR</span>
          <span className="text-sm text-occp-danger font-mono">{error}</span>
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-[var(--text-muted)] font-mono">
          LOADING AUDIT LOG...
          <span className="inline-block w-2 h-3 bg-occp-primary ml-1 animate-blink align-middle" />
        </div>
      ) : (
        <div className="retro-card p-6 crt-glow">
          <AuditTable entries={entries} chainValid={chainValid} />
        </div>
      )}
    </div>
  );
}
