"use client";

import * as React from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  ShieldCheck,
  ShieldX,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type StatusPillVariant =
  | "running"
  | "passed"
  | "failed"
  | "halted"
  | "pending"
  | "approved"
  | "rejected";

export interface StatusPillProps {
  variant: StatusPillVariant;
  /** Override the auto-derived label. Default = capitalized variant name. */
  label?: string;
  /** Compact mode: smaller padding, no icon. */
  compact?: boolean;
  /** Optional className passthrough. */
  className?: string;
}

interface VariantConfig {
  icon: LucideIcon;
  /** OKLCH border + text base color. */
  color: string;
  /** Tinted background (10% alpha of color). */
  bg: string;
  /** Spinning vs pulsing icon class. */
  iconAnimation?: string;
}

/**
 * Variant → visual config map.
 *
 * FELT (running animation): we ship Loader2 + `animate-spin` instead of
 * Activity + a custom pulse keyframe. Rationale:
 *   1. `animate-spin` is a Tailwind built-in — no globals.css churn for the
 *      icon itself (we still add a `pulse-status` keyframe for the OUTER
 *      pill background, see status-pill `running` className below).
 *   2. Loader2's spinner glyph is the universal "in progress" signal users
 *      already recognize from shadcn/ui, sonner toasts, and the rest of OCCP.
 *   3. Activity's heartbeat looks like a vitals chart, not progress — it
 *      reads as "live" rather than "working".
 */
const VARIANTS: Record<StatusPillVariant, VariantConfig> = {
  running: {
    icon: Loader2,
    color: "oklch(0.65 0.18 240)",
    bg: "oklch(0.65 0.18 240 / 0.1)",
    iconAnimation: "animate-spin",
  },
  passed: {
    icon: CheckCircle2,
    color: "oklch(0.72 0.18 145)",
    bg: "oklch(0.72 0.18 145 / 0.1)",
  },
  failed: {
    icon: XCircle,
    color: "oklch(0.65 0.22 27)",
    bg: "oklch(0.65 0.22 27 / 0.1)",
  },
  halted: {
    icon: AlertTriangle,
    color: "oklch(0.78 0.16 70)",
    bg: "oklch(0.78 0.16 70 / 0.1)",
  },
  pending: {
    icon: Clock,
    color: "oklch(0.55 0.01 260)",
    bg: "oklch(0.55 0.01 260 / 0.1)",
  },
  approved: {
    icon: ShieldCheck,
    color: "oklch(0.72 0.18 145)",
    bg: "oklch(0.72 0.18 145 / 0.1)",
  },
  rejected: {
    icon: ShieldX,
    color: "oklch(0.65 0.22 27)",
    bg: "oklch(0.65 0.22 27 / 0.1)",
  },
};

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function StatusPill({
  variant,
  label,
  compact = false,
  className,
}: StatusPillProps): React.JSX.Element {
  const cfg = VARIANTS[variant];
  const resolvedLabel = label ?? capitalize(variant);
  const Icon = cfg.icon;
  const iconSize = compact ? 12 : 14;

  return (
    <span
      role="status"
      aria-label={resolvedLabel}
      data-variant={variant}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-mono text-xs font-medium",
        compact ? "px-1.5 py-0" : "px-2 py-0.5",
        variant === "running" && "animate-[pulse-status_2s_ease-in-out_infinite]",
        className,
      )}
      style={{
        color: cfg.color,
        borderColor: cfg.color,
        backgroundColor: cfg.bg,
      }}
    >
      {!compact && (
        <Icon
          width={iconSize}
          height={iconSize}
          aria-hidden="true"
          className={cfg.iconAnimation}
          data-testid="status-pill-icon"
        />
      )}
      <span>{resolvedLabel}</span>
    </span>
  );
}

// Re-export for callers that want to enumerate the variant list.
export const STATUS_PILL_VARIANTS: readonly StatusPillVariant[] = [
  "running",
  "passed",
  "failed",
  "halted",
  "pending",
  "approved",
  "rejected",
] as const;

// Silence unused-import linter for the alternative icon kept for posterity.
void Activity;
