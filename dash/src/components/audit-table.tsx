"use client";

import type { AuditEntry } from "@/lib/api";

interface Props {
  entries: AuditEntry[];
  chainValid: boolean;
}

export function AuditTable({ entries, chainValid }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            chainValid ? "bg-occp-success animate-pulse" : "bg-occp-danger"
          }`}
        />
        <span className="font-pixel text-[9px] tracking-wider">
          HASH CHAIN:{" "}
          <span className={chainValid ? "text-occp-success" : "text-occp-danger"}>
            {chainValid ? "VALID" : "BROKEN"}
          </span>
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-left text-[var(--text-muted)] border-b border-occp-muted/30">
              <th className="pb-2 pr-4 font-pixel text-[8px] tracking-wider">TIME</th>
              <th className="pb-2 pr-4 font-pixel text-[8px] tracking-wider">ACTOR</th>
              <th className="pb-2 pr-4 font-pixel text-[8px] tracking-wider">ACTION</th>
              <th className="pb-2 pr-4 font-pixel text-[8px] tracking-wider">TASK</th>
              <th className="pb-2 pr-4 font-pixel text-[8px] tracking-wider">HASH</th>
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
                  <span className="font-pixel text-[9px]">NO AUDIT ENTRIES</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
