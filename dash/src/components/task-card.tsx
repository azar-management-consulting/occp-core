"use client";

import { VAPProgress } from "./vap-progress";
import { useT } from "@/lib/i18n";

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
  low: "bg-occp-success/15 text-occp-success border border-occp-success/30",
  medium: "bg-occp-warning/15 text-occp-warning border border-occp-warning/30",
  high: "bg-occp-danger/15 text-occp-danger border border-occp-danger/30",
  critical: "bg-red-900/20 text-red-400 border border-red-500/30",
};

export function TaskCard({ id, name, description, status, risk_level, created_at, onRun }: Props) {
  const t = useT();

  return (
    <div className="retro-card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-mono font-bold text-sm">{name}</h3>
          <p className="text-xs text-[var(--text-muted)] font-mono mt-1 line-clamp-2">
            {description}
          </p>
        </div>
        <span
          className={`text-[11px] px-2 py-0.5 rounded font-pixel tracking-wider ${riskColors[risk_level] || ""}`}
        >
          {risk_level.toUpperCase()}
        </span>
      </div>

      <VAPProgress status={status} />

      <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] font-mono">
        <span>{t.common.id}: {id.slice(0, 12)}</span>
        <span>{new Date(created_at).toLocaleString()}</span>
      </div>

      {status === "pending" && onRun && (
        <button
          onClick={onRun}
          className="retro-btn-primary w-full py-2 font-pixel text-[11px] tracking-wider"
        >
          {t.common.runPipeline}
        </button>
      )}
    </div>
  );
}
