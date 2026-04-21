import { cn } from "@/lib/utils";

type SkeletonVariant = "text" | "title" | "card";

interface SkeletonProps {
  variant?: SkeletonVariant;
  className?: string;
}

const VARIANT_CLASSES: Record<SkeletonVariant, string> = {
  text: "h-4",
  title: "h-6",
  card: "h-32",
};

/**
 * Skeleton — animated loading placeholder.
 *
 * Usage:
 *   <Skeleton />                    → text (h-4, w-24 default)
 *   <Skeleton variant="title" />    → h-6
 *   <Skeleton variant="card" />     → h-32
 *   <Skeleton className="w-full" /> → override width
 *
 * Base: animate-pulse rounded-md bg-muted/60 (Tailwind 4 token).
 * aria-hidden="true" — decorative; parent should use aria-busy.
 */
export function Skeleton({ variant = "text", className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-md bg-[var(--border-subtle,#52525b)]/40",
        variant === "text" && "w-24",
        variant === "title" && "w-40",
        variant === "card" && "w-full",
        VARIANT_CLASSES[variant],
        className
      )}
    />
  );
}

/** Convenience: a row of text skeletons that simulates a paragraph. */
export function SkeletonParagraph({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" aria-hidden="true" aria-busy="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          className={i === lines - 1 ? "w-3/5" : "w-full"}
        />
      ))}
    </div>
  );
}
