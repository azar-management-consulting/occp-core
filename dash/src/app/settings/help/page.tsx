"use client";

import { useEffect, useState } from "react";
import { RotateCcw, Eye, BellRing, HelpCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useTour } from "@/components/onboarding/onboarding-provider";
import { HelpBubble } from "@/components/onboarding/help-bubble";
import {
  tOnboarding,
  type OnboardingLocale,
} from "@/lib/onboarding-i18n";

function readLocale(): OnboardingLocale {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem("occp_lang");
    if (v === "en" || v === "hu" || v === "de" || v === "fr" || v === "es" || v === "it" || v === "pt") return v;
  } catch {
    // ignore
  }
  return "en";
}

export default function SettingsHelpPage() {
  const tour = useTour();
  const [locale, setLocale] = useState<OnboardingLocale>("en");
  const [hintsEnabled, setHintsEnabled] = useState(true);
  const [resetToast, setResetToast] = useState<string | null>(null);

  useEffect(() => {
    setLocale(readLocale());
    if (typeof window !== "undefined") {
      try {
        const v = window.localStorage.getItem("occp_hints_enabled");
        setHintsEnabled(v !== "false");
      } catch {
        // ignore
      }
    }
  }, []);

  const t = (k: string, fb?: string) => tOnboarding(locale, k, fb);

  const handleRestart = () => {
    tour.restartTour();
  };

  const handleResetHints = () => {
    tour.resetAllHints();
    setHintsEnabled(true);
    setResetToast(t("settings.help.reset_hints_cta") + " ✓");
    setTimeout(() => setResetToast(null), 2000);
  };

  const handleToggle = (next: boolean) => {
    setHintsEnabled(next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(
          "occp_hints_enabled",
          next ? "true" : "false",
        );
      } catch {
        // ignore
      }
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-3">
          <HelpCircle aria-hidden="true" className="text-[var(--accent,#6366f1)]" />
          {t("settings.help.title")}
        </h1>
        <p className="text-[var(--fg-muted,#a1a1aa)]">
          {t("settings.help.subtitle")}
        </p>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-start gap-4 space-y-0">
          <RotateCcw
            aria-hidden="true"
            className="mt-1 text-[var(--fg-muted,#a1a1aa)]"
          />
          <div className="flex-1">
            <CardTitle className="text-base font-semibold">
              {t("settings.help.restart_title")}
            </CardTitle>
            <CardDescription className="mt-1">
              {t("settings.help.restart_body")}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex justify-end">
          <Button
            onClick={handleRestart}
            data-tour="restart-tour-button"
            data-restart-tour
          >
            {t("settings.help.restart_cta")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start gap-4 space-y-0">
          <Eye
            aria-hidden="true"
            className="mt-1 text-[var(--fg-muted,#a1a1aa)]"
          />
          <div className="flex-1">
            <CardTitle className="text-base font-semibold">
              {t("settings.help.reset_hints_title")}
            </CardTitle>
            <CardDescription className="mt-1">
              {t("settings.help.reset_hints_body")}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex items-center justify-end gap-3">
          {resetToast ? (
            <span className="text-xs text-[var(--accent,#6366f1)]">
              {resetToast}
            </span>
          ) : null}
          <Button variant="outline" onClick={handleResetHints}>
            {t("settings.help.reset_hints_cta")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start gap-4 space-y-0">
          <BellRing
            aria-hidden="true"
            className="mt-1 text-[var(--fg-muted,#a1a1aa)]"
          />
          <div className="flex-1">
            <CardTitle className="text-base font-semibold">
              {t("settings.help.toggle_title")}
            </CardTitle>
            <CardDescription className="mt-1">
              {t("settings.help.toggle_body")}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex items-center justify-end gap-3">
          <span className="text-xs text-[var(--fg-muted,#a1a1aa)]">
            {hintsEnabled ? "ON" : "OFF"}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={hintsEnabled}
            onClick={() => handleToggle(!hintsEnabled)}
            className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)]"
            style={{
              background: hintsEnabled
                ? "var(--occp-bubble-border)"
                : "var(--border-subtle, #52525b)",
            }}
          >
            <span
              className="inline-block h-5 w-5 transform rounded-full bg-white transition-transform"
              style={{
                transform: hintsEnabled
                  ? "translateX(22px)"
                  : "translateX(2px)",
              }}
            />
          </button>
        </CardContent>
      </Card>

      {/* Hint 7: Restart tour */}
      <HelpBubble
        hintKey="restarttour"
        anchor='[data-tour="restart-tour-button"]'
        variant="info"
        placement="left"
        title={t("hint.restarttour.title")}
        body={t("hint.restarttour.body")}
      />
    </div>
  );
}
