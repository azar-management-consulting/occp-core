"use client";

import type { AuditEntry } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface Props {
  entries: AuditEntry[];
  chainValid: boolean;
}

export function AuditTable({ entries, chainValid }: Props) {
  const t = useT();

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            chainValid ? "bg-occp-success animate-pulse" : "bg-occp-danger"
          }`}
        />
        <span className="font-pixel text-[11px] tracking-wider">
          {t.audit.hashChain}:{" "}
          <span className={chainValid ? "text-occp-success" : "text-occp-danger"}>
            {chainValid ? t.audit.valid : t.audit.broken}
          </span>
        </span>
      </div>
      <p className="field-hint">{t.audit.chainDesc}</p>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-left text-[var(--text-muted)] border-b border-occp-muted/30">
              <th className="pb-2 pr-4 font-pixel text-[11px] tracking-wider">{t.audit.time}</th>
              <th className="pb-2 pr-4 font-pixel text-[11px] tracking-wider">{t.audit.actor}</th>
              <th className="pb-2 pr-4 font-pixel text-[11px] tracking-wider">{t.audit.action}</th>
              <th className="pb-2 pr-4 font-pixel text-[11px] tracking-wider">{t.audit.task}</th>
              <th className="pb-2 pr-4 font-pixel text-[11px] tracking-wider">{t.audit.hash}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-occp-muted/10 hover:bg-white/[0.02]">
                <td className="py-2.5 pr-4 text-[var(--text-muted)]">
                  {new Date(e.timestamp).toLocaleTimeString()}
                </td>
                <td className="py-2.5 pr-4 text-occp-accent">{e.actor}</td>
                <td className="py-2.5 pr-4">{e.action}</td>
                <td className="py-2.5 pr-4 text-occp-primary">{e.task_id.slice(0, 8)}</td>
                <td className="py-2.5 pr-4 text-[var(--text-muted)]">
                  {e.hash.slice(0, 12)}...
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={5} className="py-8 text-center text-[var(--text-muted)]">
                  <span className="font-pixel text-[11px]">{t.audit.noEntries}</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
