import { cn } from "@/lib/utils";

type LiveBadgeVariant = "live" | "idle" | "error" | "loading";

interface LiveBadgeProps {
  variant?: LiveBadgeVariant;
  label?: string;
  className?: string;
}

const STYLES: Record<
  LiveBadgeVariant,
  { dot: string; text: string; pulse: boolean; ariaLabel: string }
> = {
  live: {
    dot: "bg-[var(--success,#75ce64)]",
    text: "text-[var(--success,#75ce64)]",
    pulse: true,
    ariaLabel: "Live",
  },
  idle: {
    dot: "bg-[var(--fg-muted,#a1a1aa)]",
    text: "text-[var(--fg-muted,#a1a1aa)]",
    pulse: false,
    ariaLabel: "Idle",
  },
  error: {
    dot: "bg-[var(--danger,#d27d6f)]",
    text: "text-[var(--danger,#d27d6f)]",
    pulse: false,
    ariaLabel: "Error",
  },
  loading: {
    dot: "bg-[var(--warning,#edf171)]",
    text: "text-[var(--warning,#edf171)]",
    pulse: true,
    ariaLabel: "Loading",
  },
};

/**
 * LiveBadge — pulsing status indicator.
 *
 * Variants: live (green), idle (gray), error (red), loading (amber).
 * Pulse animation only on live + loading to avoid visual noise.
 * a11y: role="status" aria-label for screen readers.
 */
export function LiveBadge({
  variant = "live",
  label,
  className,
}: LiveBadgeProps) {
  const s = STYLES[variant];
  const displayLabel = label ?? s.ariaLabel;

  return (
    <span
      role="status"
      aria-label={`Status: ${displayLabel}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle,#52525b)] bg-[var(--bg-elev,#18181b)] px-2.5 py-1 text-xs font-medium",
        className
      )}
    >
      {/* Dot */}
      <span className="relative flex h-2 w-2 shrink-0" aria-hidden="true">
        {s.pulse && (
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
              s.dot
            )}
          />
        )}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", s.dot)} />
      </span>

      {/* Label */}
      <span className={s.text}>{displayLabel}</span>
    </span>
  );
}
