"use client";
/**
 * v2 parallel route layout — reuses the primary providers so /(v2)
 * shares Nav + AuthGuard + CommandPalette with the legacy routes.
 *
 * Behind feature flag NEXT_PUBLIC_DASH_V2=true (checked in middleware
 * or via a redirect from the default page in a follow-up commit).
 */
import React from "react";

export default function DashV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="dash-v2">
      {/* ARIA landmark: <main> satisfies WCAG 2.4 Navigable + screen reader landmark nav */}
      <main className="max-w-screen-xl mx-auto p-4 md:p-6">
        {children}
      </main>
      {/* 3.2.6 Consistent Help — keyboard shortcut entry point visible on every v2 page */}
      <div className="fixed bottom-4 right-4 z-40">
        <button
          type="button"
          onClick={() =>
            window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))
          }
          className="flex items-center gap-1.5 rounded-md border border-[var(--border-subtle,#52525b)] bg-[var(--bg-elev,#18181b)] px-3 py-1.5 text-xs text-[var(--fg-muted,#a1a1aa)] transition-colors hover:text-[var(--fg,#fafafa)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-elev,#18181b)]"
          aria-label="Open keyboard shortcuts (Command K)"
        >
          <kbd aria-hidden="true" className="font-mono">⌘K</kbd>
          <span>Shortcuts</span>
        </button>
      </div>
    </div>
  );
}
