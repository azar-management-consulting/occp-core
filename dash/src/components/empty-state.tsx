"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  HelpBubble,
  type HintVariant,
} from "@/components/onboarding/help-bubble";

export interface EmptyStateHelpBubble {
  hintKey: string;
  variant?: HintVariant;
  title?: string;
  body: string;
  placement?: "top" | "bottom" | "left" | "right";
}

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
  /** First-render hint pointing at the action CTA. */
  helpBubble?: EmptyStateHelpBubble;
}

/**
 * EmptyState — shown when a list or table has no data yet.
 *
 * Layout: centered flex column, max-w-sm, py-16.
 * Icon: 48×48 rounded muted tile.
 * a11y: role="status" so screen readers announce the empty state.
 *
 * Optional helpBubble: anchored to the action CTA via internal ref.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  helpBubble,
}: EmptyStateProps) {
  const actionRef = useRef<HTMLDivElement>(null);

  // Forward focus management is up to the consumer's CTA.
  useEffect(() => {
    // No-op — placeholder for future autofocus heuristic.
  }, []);

  return (
    <div
      role="status"
      className={cn(
        "mx-auto flex max-w-sm flex-col items-center gap-4 py-16 text-center",
        className,
      )}
    >
      {/* Icon tile */}
      <div
        className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--bg-elev,#18181b)] border border-[var(--border-subtle,#52525b)]"
        aria-hidden="true"
      >
        <Icon
          size={22}
          className="text-[var(--fg-muted,#a1a1aa)]"
          strokeWidth={1.5}
        />
      </div>

      {/* Text */}
      <div className="space-y-1">
        <p className="text-base font-semibold text-[var(--fg,#fafafa)]">
          {title}
        </p>
        <p className="text-sm text-[var(--fg-muted,#a1a1aa)] leading-snug text-balance">
          {description}
        </p>
      </div>

      {/* Optional CTA */}
      {action && (
        <div ref={actionRef} className="mt-2">
          {action}
        </div>
      )}

      {/* Optional help bubble pointing at the CTA */}
      {helpBubble && action ? (
        <HelpBubble
          hintKey={helpBubble.hintKey}
          anchor={actionRef as React.RefObject<Element | null>}
          variant={helpBubble.variant ?? "info"}
          placement={helpBubble.placement ?? "bottom"}
          title={helpBubble.title}
          body={helpBubble.body}
        />
      ) : null}
    </div>
  );
}
