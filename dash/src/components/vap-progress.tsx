"use client";

const STAGES = [
  { key: "planning", label: "PLAN", icon: "01" },
  { key: "gated", label: "GATE", icon: "02" },
  { key: "executing", label: "EXEC", icon: "03" },
  { key: "validating", label: "VALID", icon: "04" },
  { key: "shipping", label: "SHIP", icon: "05" },
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
    <div className="flex items-center gap-1.5">
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
          <div key={stage.key} className="flex items-center gap-1.5">
            <div
              className={`w-8 h-8 rounded flex items-center justify-center font-pixel text-[12px] transition-all ${
                state === "completed"
                  ? "bg-occp-success/20 text-occp-success border border-occp-success/30"
                  : state === "active"
                  ? "bg-occp-primary/20 text-occp-primary border border-occp-primary/30 animate-pulse"
                  : state === "failed"
                  ? "bg-occp-danger/20 text-occp-danger border border-occp-danger/30"
                  : "bg-occp-muted/30 text-[var(--text-muted)] border border-occp-muted/20"
              }`}
            >
              {state === "completed" ? "\u2713" : stage.icon}
            </div>
            <span
              className={`text-[12px] font-pixel tracking-wider ${
                state === "active"
                  ? "text-occp-primary"
                  : state === "completed"
                  ? "text-occp-success"
                  : state === "failed"
                  ? "text-occp-danger"
                  : "text-[var(--text-muted)]/50"
              }`}
            >
              {stage.label}
            </span>
            {i < STAGES.length - 1 && (
              <div
                className={`w-4 h-px ${
                  i < current
                    ? "bg-occp-success"
                    : state === "failed"
                    ? "bg-occp-danger/30"
                    : "bg-occp-muted/30"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
