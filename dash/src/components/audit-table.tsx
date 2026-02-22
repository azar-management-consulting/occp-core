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
          className={`w-3 h-3 rounded-full ${chainValid ? "bg-occp-success" : "bg-occp-danger"}`}
        />
        <span className="text-sm font-medium">
          Hash chain: {chainValid ? "Valid" : "Broken"}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[var(--text-muted)] border-b border-occp-muted/30">
              <th className="pb-2 pr-4">Time</th>
              <th className="pb-2 pr-4">Actor</th>
              <th className="pb-2 pr-4">Action</th>
              <th className="pb-2 pr-4">Task</th>
              <th className="pb-2 pr-4">Hash</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-occp-muted/10">
                <td className="py-2 pr-4 text-xs text-[var(--text-muted)]">
                  {new Date(e.timestamp).toLocaleTimeString()}
                </td>
                <td className="py-2 pr-4">{e.actor}</td>
                <td className="py-2 pr-4">{e.action}</td>
                <td className="py-2 pr-4 font-mono text-xs">{e.task_id.slice(0, 8)}</td>
                <td className="py-2 pr-4 font-mono text-xs text-[var(--text-muted)]">
                  {e.hash.slice(0, 12)}...
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={5} className="py-8 text-center text-[var(--text-muted)]">
                  No audit entries yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
