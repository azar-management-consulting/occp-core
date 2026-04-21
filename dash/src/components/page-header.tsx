import { Breadcrumb } from "@/components/breadcrumb";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Rendered right-aligned in the actions row (Button, etc.) */
  actions?: React.ReactNode;
  /** Placed inline beside the breadcrumb (e.g. <LiveBadge />) */
  badge?: React.ReactNode;
  className?: string;
}

/**
 * PageHeader — consistent page-level header for every v2 route.
 *
 * Structure (top → bottom):
 *   1. Breadcrumb row (+ optional badge inline-end)
 *   2. h1 title + description | actions (right-aligned)
 *
 * Decision: breadcrumb is rendered PER-PAGE (not in layout) so pages
 * that want to hide or override it can do so. The layout wrapper only
 * provides the <main> shell.
 */
export function PageHeader({
  title,
  description,
  actions,
  badge,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("space-y-3", className)}>
      {/* Breadcrumb row */}
      <div className="flex items-center gap-3">
        <Breadcrumb />
        {badge && <div className="ml-auto">{badge}</div>}
      </div>

      {/* Title + actions */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1 min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight text-[var(--fg,#fafafa)] truncate">
            {title}
          </h1>
          {description && (
            <p className="text-sm text-[var(--fg-muted,#a1a1aa)] leading-relaxed">
              {description}
            </p>
          )}
        </div>

        {actions && (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        )}
      </div>
    </header>
  );
}
