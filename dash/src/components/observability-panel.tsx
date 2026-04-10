"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface DailyCheck {
  healthy: boolean;
  score: number;
  alerts: string[];
  autodev: {
    total_runs: number;
    active_runs: number;
    recent_fails: number;
  };
  budget: {
    runs_used: number;
    runs_limit: number;
    budget_pct: number;
    merges_used: number;
  };
  observability: {
    uptime_seconds: number;
    anomaly_count: number;
    tasks_total: number;
    tasks_by_outcome: Record<string, number>;
    narrative: string;
  };
  governance: {
    proposals_open: number;
    unknown_verdicts: number;
    pending_approvals: number;
  };
  kill_switch: {
    state: string;
    is_active: boolean;
  };
}

export function ObservabilityPanel() {
  const [data, setData] = useState<DailyCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<DailyCheck>("/daily-check")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="retro-card p-6 animate-pulse">
        <div className="h-4 bg-occp-primary/20 rounded w-1/3 mb-4" />
        <div className="h-3 bg-occp-primary/10 rounded w-full mb-2" />
        <div className="h-3 bg-occp-primary/10 rounded w-2/3" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="retro-card p-6 border-red-500/30">
        <h3 className="font-pixel text-xs text-red-400 mb-2">OBSERVABILITY ERROR</h3>
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const scoreColor =
    data.score >= 8 ? "text-green-400" :
    data.score >= 5 ? "text-yellow-400" : "text-red-400";

  const ksColor = data.kill_switch.is_active ? "text-red-400" : "text-green-400";

  return (
    <div className="retro-card p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-pixel text-xs text-occp-primary tracking-wider">
          L6 SYSTEM HEALTH
        </h3>
        <div className="flex items-center gap-3">
          <span className={`font-pixel text-lg ${scoreColor}`}>
            {data.score}/10
          </span>
          <span className={`text-xs px-2 py-0.5 rounded ${
            data.healthy ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
          }`}>
            {data.healthy ? "HEALTHY" : "ALERT"}
          </span>
        </div>
      </div>

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <div className="bg-red-900/20 border border-red-500/30 rounded p-3">
          <p className="text-xs text-red-400 font-semibold mb-1">ALERTS:</p>
          {data.alerts.map((a, i) => (
            <p key={i} className="text-xs text-red-300">• {a}</p>
          ))}
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricBox
          label="Pipeline Tasks"
          value={data.observability.tasks_total}
          sub={Object.entries(data.observability.tasks_by_outcome)
            .map(([k, v]) => `${k}: ${v}`)
            .join(", ") || "no activity"}
        />
        <MetricBox
          label="Anomalies"
          value={data.observability.anomaly_count}
          sub={data.observability.anomaly_count === 0 ? "all clear" : "investigate!"}
          alert={data.observability.anomaly_count > 0}
        />
        <MetricBox
          label="AutoDev Runs"
          value={data.autodev.total_runs}
          sub={`${data.budget.runs_used}/${data.budget.runs_limit} budget`}
        />
        <MetricBox
          label="Proposals"
          value={data.governance.proposals_open}
          sub={`${data.governance.pending_approvals} pending approval`}
        />
      </div>

      {/* Kill Switch + Uptime */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${
            data.kill_switch.is_active ? "bg-red-500 animate-pulse" : "bg-green-500"
          }`} />
          <span className={ksColor}>
            Kill Switch: {data.kill_switch.state.toUpperCase()}
          </span>
        </div>
        <span className="text-occp-primary/40">
          uptime: {Math.floor(data.observability.uptime_seconds / 3600)}h {Math.floor((data.observability.uptime_seconds % 3600) / 60)}m
        </span>
      </div>

      {/* Narrative */}
      <p className="text-xs text-occp-primary/50 leading-relaxed border-t border-occp-primary/10 pt-3">
        {data.observability.narrative}
      </p>
    </div>
  );
}

function MetricBox({
  label, value, sub, alert = false,
}: {
  label: string;
  value: number;
  sub: string;
  alert?: boolean;
}) {
  return (
    <div className={`rounded p-3 ${
      alert ? "bg-red-900/20 border border-red-500/20" : "bg-occp-primary/5 border border-occp-primary/10"
    }`}>
      <p className="text-xs text-occp-primary/40 mb-1">{label}</p>
      <p className={`text-xl font-bold ${alert ? "text-red-400" : "text-occp-primary"}`}>
        {value}
      </p>
      <p className="text-[10px] text-occp-primary/30 mt-1 truncate">{sub}</p>
    </div>
  );
}
