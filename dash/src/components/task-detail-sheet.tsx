"use client";

import * as React from "react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

export interface TaskDetailSheetProps {
  /** Open state — controlled by parent via querystring (e.g. ?row=task-042). */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Sub-title (timestamp, hash, etc.) */
  subtitle?: string;
  /** Inline content — JSON dump, fields, etc. */
  children: React.ReactNode;
  /** Optional className passthrough on the body wrapper. */
  bodyClassName?: string;
}

/**
 * Generic row-click side drawer.
 *
 * Re-uses the Radix Dialog–backed Sheet primitive at
 * `dash/src/components/ui/sheet.tsx`:
 *   - Esc key closure handled by Radix Dialog.
 *   - Built-in close button rendered (top-right) by SheetContent
 *     unless `hideCloseButton` is passed — here we keep it.
 *   - aria-labelledby is wired automatically through SheetTitle (Radix
 *     attaches the title node id to the dialog root).
 *
 * Width: w-full on mobile, sm:max-w-md fallback, lg:max-w-[480px] override
 * via SheetContent className.
 */
export function TaskDetailSheet({
  open,
  onOpenChange,
  title,
  subtitle,
  children,
  bodyClassName,
}: TaskDetailSheetProps): React.JSX.Element {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col p-0 sm:max-w-md lg:max-w-[480px]"
      >
        <SheetHeader className="space-y-1 border-b border-[var(--border-subtle,#27272a)] px-5 py-4 text-left">
          <SheetTitle className="text-lg font-semibold text-[var(--fg,#fafafa)]">
            {title}
          </SheetTitle>
          {subtitle ? (
            <SheetDescription className="font-mono text-sm text-[var(--fg-muted,#a1a1aa)]">
              {subtitle}
            </SheetDescription>
          ) : null}
        </SheetHeader>

        <div
          className={cn(
            "flex-1 overflow-y-auto p-5 text-sm text-[var(--fg,#fafafa)]",
            bodyClassName,
          )}
          data-testid="task-detail-sheet-body"
        >
          {children}
        </div>
      </SheetContent>
    </Sheet>
  );
}
