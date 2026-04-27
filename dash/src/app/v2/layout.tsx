"use client";
/**
 * v2 parallel route layout — reuses the primary providers so /(v2)
 * shares Nav + AuthGuard + CommandPalette with the legacy routes.
 *
 * Behind feature flag NEXT_PUBLIC_DASH_V2=true (checked in middleware
 * or via a redirect from the default page in a follow-up commit).
 *
 * Breadcrumb decision: rendered PER-PAGE via <PageHeader>, NOT here.
 * This lets individual pages suppress or override it (e.g. Mission Control
 * home shows "Home" only). The layout only provides the <main> shell.
 */
import React, { useEffect, useState } from "react";
import { HelpBubble } from "@/components/onboarding/help-bubble";
import {
  tOnboarding,
  type OnboardingLocale,
} from "@/lib/onboarding-i18n";

function readDashLocale(): OnboardingLocale {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem("occp_lang");
    if (
      v === "hu" ||
      v === "de" ||
      v === "fr" ||
      v === "es" ||
      v === "it" ||
      v === "pt" ||
      v === "en"
    ) {
      return v;
    }
  } catch {
    // ignore
  }
  return "en";
}

export default function DashV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [locale, setLocale] = useState<OnboardingLocale>("en");
  useEffect(() => {
    setLocale(readDashLocale());
  }, []);

  return (
    <div className="dash-v2">
      {/* Skip-link target: id="main-content" satisfies WCAG 2.4.1 Bypass Blocks */}
      <main
        id="main-content"
        className="max-w-6xl mx-auto px-6 py-10 space-y-8"
      >
        {children}
      </main>

      {/* 3.2.6 Consistent Help — ⌘K entry point visible on every v2 page */}
      <div className="fixed bottom-4 right-4 z-40">
        <button
          type="button"
          data-tour="cmdk-trigger"
          onClick={() => {
            // react-hotkeys-hook listens on document by default — dispatching
            // on window does NOT bubble down. Use document.body for reliable
            // delivery to the bound mod+k handler.
            const evt = new KeyboardEvent("keydown", {
              key: "k",
              metaKey: true,
              ctrlKey: !navigator.platform.includes("Mac"),
              bubbles: true,
              cancelable: true,
            });
            document.dispatchEvent(evt);
          }}
          className="flex items-center gap-1.5 rounded-md border border-[var(--border-subtle,#52525b)] bg-[var(--bg-elev,#18181b)] px-3 py-1.5 text-xs text-[var(--fg-muted,#a1a1aa)] transition-colors duration-150 ease-out hover:text-[var(--fg,#fafafa)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-elev,#18181b)]"
          aria-label="Open keyboard shortcuts (Command K)"
        >
          <kbd aria-hidden="true" className="font-mono">
            ⌘K
          </kbd>
          <span>Shortcuts</span>
        </button>
      </div>

      {/* Hint 1: ⌘K command palette — first-render bubble */}
      <HelpBubble
        hintKey="cmdk"
        anchor='[data-tour="cmdk-trigger"]'
        variant="info"
        placement="top"
        title={tOnboarding(locale, "hint.cmdk.title")}
        body={tOnboarding(locale, "hint.cmdk.body")}
      />
    </div>
  );
}
