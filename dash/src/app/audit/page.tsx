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
          <h1 className="text-2xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">
            Tamper-evident SHA-256 hash chain of all pipeline operations
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[var(--text-muted)]">
            {total} {total === 1 ? "entry" : "entries"}
          </span>
          <button
            onClick={load}
            className="px-4 py-2 text-sm bg-occp-surface border border-occp-muted/30 rounded-lg hover:bg-white/5 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-occp-danger/10 border border-occp-danger/30 rounded-lg p-4 text-sm text-occp-danger">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-[var(--text-muted)]">
          Loading audit log...
        </div>
      ) : (
        <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-6">
          <AuditTable entries={entries} chainValid={chainValid} />
        </div>
      )}
    </div>
  );
}
