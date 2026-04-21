"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";

/**
 * SpendSparkline — 24h token-spend mini area chart.
 *
 * Props: `data: Array<{ hour: string; usd: number }>`.
 * Default export of 24 mock points (0.02 – 0.35 USD, sine-ish smooth).
 * Accent color via CSS var `--accent` with #6366f1 fallback.
 */
export type SpendPoint = { hour: string; usd: number };

const DEFAULT_DATA: SpendPoint[] = Array.from({ length: 24 }, (_, i) => {
  const base = 0.185 + Math.sin((i / 24) * Math.PI * 2) * 0.14;
  const jitter = Math.sin(i * 1.7) * 0.02;
  return {
    hour: `${String(i).padStart(2, "0")}:00`,
    usd: Math.max(0.02, Math.min(0.35, base + jitter)),
  };
});

export function SpendSparkline({ data = DEFAULT_DATA }: { data?: SpendPoint[] }) {
  const last = data[data.length - 1]?.usd ?? 0;
  const prev = data[data.length - 2]?.usd ?? last;
  const deltaPct = prev === 0 ? 0 : Math.round(((last - prev) / prev) * 100);
  const up = deltaPct >= 0;

  return (
    <div className="mt-2 flex items-center gap-3">
      <div className="h-10 flex-1">
        <ResponsiveContainer width="100%" height={40}>
          <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="spendSparkGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent, #6366f1)" stopOpacity={0.6} />
                <stop offset="100%" stopColor="var(--accent, #6366f1)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="usd"
              stroke="var(--accent, #6366f1)"
              strokeWidth={1.5}
              fill="url(#spendSparkGradient)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <span
        className={`whitespace-nowrap rounded px-1.5 py-0.5 font-mono text-[11px] ${
          up
            ? "bg-[var(--accent,#6366f1)]/15 text-[var(--accent,#6366f1)]"
            : "bg-[var(--success,#75ce64)]/15 text-[var(--success,#75ce64)]"
        }`}
      >
        ${last.toFixed(2)} {up ? "↑" : "↓"}
        {Math.abs(deltaPct)}%
      </span>
    </div>
  );
}
