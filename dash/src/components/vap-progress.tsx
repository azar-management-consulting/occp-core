"use client";

const STAGES = [
  { key: "planning", label: "Plan", icon: "1" },
  { key: "gated", label: "Gate", icon: "2" },
  { key: "executing", label: "Execute", icon: "3" },
  { key: "validating", label: "Validate", icon: "4" },
  { key: "shipping", label: "Ship", icon: "5" },
] as const;

const STATUS_ORDER: Record<string, number> = {
  pending: -1,
  planning: 0,
  gated: 1,
  executing: 2,
  validating: 3,
  shipping: 4,
  completed: 5,
  failed: -2,
  rejected: -2,
};

interface Props {
  status: string;
}

export function VAPProgress({ status }: Props) {
  const current = STATUS_ORDER[status] ?? -1;

  return (
    <div className="flex items-center gap-2">
      {STAGES.map((stage, i) => {
        let state: "idle" | "active" | "completed" | "failed" = "idle";
        if (status === "failed" || status === "rejected") {
          state = i <= Math.max(current, 1) ? "failed" : "idle";
        } else if (i < current) {
          state = "completed";
        } else if (i === current) {
          state = "active";
        }

        return (
          <div key={stage.key} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                state === "completed"
                  ? "bg-occp-success text-white"
                  : state === "active"
                  ? "bg-occp-primary text-white animate-pulse"
                  : state === "failed"
                  ? "bg-occp-danger text-white"
                  : "bg-occp-muted text-[var(--text-muted)]"
              }`}
            >
              {state === "completed" ? "\u2713" : stage.icon}
            </div>
            <span
              className={`text-xs ${
                state === "active"
                  ? "text-occp-primary font-medium"
                  : state === "completed"
                  ? "text-occp-success"
                  : "text-[var(--text-muted)]"
              }`}
            >
              {stage.label}
            </span>
            {i < STAGES.length - 1 && (
              <div
                className={`w-8 h-0.5 ${
                  i < current ? "bg-occp-success" : "bg-occp-muted"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
