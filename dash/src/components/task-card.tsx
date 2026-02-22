"use client";

import { VAPProgress } from "./vap-progress";

interface Props {
  id: string;
  name: string;
  description: string;
  status: string;
  risk_level: string;
  created_at: string;
  onRun?: () => void;
}

const riskColors: Record<string, string> = {
  low: "bg-occp-success/20 text-occp-success",
  medium: "bg-occp-warning/20 text-occp-warning",
  high: "bg-occp-danger/20 text-occp-danger",
  critical: "bg-red-900/30 text-red-400",
};

export function TaskCard({ id, name, description, status, risk_level, created_at, onRun }: Props) {
  return (
    <div className="bg-occp-surface border border-occp-muted/30 rounded-xl p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-base">{name}</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1 line-clamp-2">{description}</p>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full font-medium ${riskColors[risk_level] || ""}`}>
          {risk_level}
        </span>
      </div>

      <VAPProgress status={status} />

      <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
        <span>ID: {id.slice(0, 12)}</span>
        <span>{new Date(created_at).toLocaleString()}</span>
      </div>

      {status === "pending" && onRun && (
        <button
          onClick={onRun}
          className="w-full py-2 bg-occp-primary hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Run Pipeline
        </button>
      )}
    </div>
  );
}
