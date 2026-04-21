import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * EmptyState — shown when a list or table has no data yet.
 *
 * Layout: centered flex column, max-w-sm, py-16.
 * Icon: 48×48 rounded muted tile.
 * a11y: role="status" so screen readers announce the empty state.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "mx-auto flex max-w-sm flex-col items-center gap-4 py-16 text-center",
        className
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
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
