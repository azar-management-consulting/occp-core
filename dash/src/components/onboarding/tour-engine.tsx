"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTour, type TourPersona } from "./onboarding-provider";
import { SpotlightOverlay } from "./spotlight-overlay";
import { StepCard } from "./step-card";
import { TOUR_STEPS, getStep, getSubtitleKey } from "@/lib/tour-steps";
import {
  tOnboarding,
  type OnboardingLocale,
} from "@/lib/onboarding-i18n";

/** Read locale from existing dash localStorage (`occp_lang`), default 'en'. */
function readLocale(): OnboardingLocale {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem("occp_lang");
    if (v === "en" || v === "hu" || v === "de" || v === "fr" || v === "es" || v === "it" || v === "pt") {
      return v;
    }
    return "en";
  } catch {
    return "en";
  }
}

/**
 * Drives the active wizard. Mounts portal on document.body.
 * Renders nothing when state is "idle" / "dismissed" / "completed".
 */
export function TourEngine() {
  const tour = useTour();
  const [mounted, setMounted] = useState(false);
  const [locale, setLocale] = useState<OnboardingLocale>("en");

  useEffect(() => {
    setMounted(true);
    setLocale(readLocale());
    // Listen to dash language switcher (re-render on language change).
    const onStorage = (e: StorageEvent) => {
      if (e.key === "occp_lang") setLocale(readLocale());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  if (!mounted) return null;
  if (typeof document === "undefined") return null;

  const isActive =
    tour.state === "step-1" ||
    tour.state === "step-2" ||
    tour.state === "step-3" ||
    tour.state === "step-4" ||
    tour.state === "step-5";

  if (!isActive) return null;

  const step = getStep(tour.state as Parameters<typeof getStep>[0]);
  if (!step) return null;

  // Step-1 special case: persona picker UI inside the card.
  const isStepOne = step.id === "step-1";
  const isStepFive = step.id === "step-5";

  const t = (k: string, fb?: string) => tOnboarding(locale, k, fb);

  const subtitleKey = getSubtitleKey(step, tour.persona);

  const stepNumber = Number(step.id.replace("step-", ""));
  const totalSteps = TOUR_STEPS.length;

  // Inline content for step-1 (persona picker) and step-5 (next-cards).
  const inlineContent = (() => {
    if (isStepOne) return <PersonaPicker persona={tour.persona} setPersona={tour.setPersona} t={t} />;
    if (isStepFive) return <DoneNextCards t={t} />;
    return null;
  })();

  return createPortal(
    <>
      <SpotlightOverlay anchorSelector={step.anchorSelector} />
      <StepCard
        anchorSelector={step.anchorSelector}
        variant={step.variant}
        title={t(step.i18n.title)}
        subtitle={subtitleKey ? t(subtitleKey) : undefined}
        content={inlineContent}
        primaryCta={t(step.i18n.primary)}
        onPrimary={() => {
          if (isStepFive) tour.completeTour();
          else tour.nextStep();
        }}
        secondaryCta={
          step.i18n.secondary && stepNumber > 1 ? t(step.i18n.secondary) : undefined
        }
        onSecondary={stepNumber > 1 ? tour.prevStep : undefined}
        skipCta={!isStepFive ? t("tour.welcome.cta_skip") : undefined}
        onSkip={!isStepFive ? tour.skipTour : undefined}
        stepNumber={stepNumber}
        totalSteps={totalSteps}
      />
    </>,
    document.body,
  );
}

interface PersonaPickerProps {
  persona: TourPersona;
  setPersona: (p: TourPersona) => void;
  t: (k: string, fb?: string) => string;
}

function PersonaPicker({ persona, setPersona, t }: PersonaPickerProps) {
  const opts: { id: NonNullable<TourPersona>; label: string }[] = [
    { id: "compliance", label: t("tour.welcome.persona_compliance") },
    { id: "engineer", label: t("tour.welcome.persona_engineer") },
    { id: "operator", label: t("tour.welcome.persona_operator") },
  ];
  return (
    <div>
      <p
        style={{
          fontSize: "0.75rem",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "var(--fg-muted, #a1a1aa)",
          marginBottom: 8,
        }}
      >
        {t("tour.welcome.persona_label")}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {opts.map((o) => {
          const isSelected = persona === o.id;
          return (
            <button
              key={o.id}
              type="button"
              onClick={() => setPersona(o.id)}
              style={{
                padding: "8px 14px",
                borderRadius: 6,
                border: `1px solid ${isSelected ? "var(--occp-bubble-border)" : "var(--border-subtle, #52525b)"}`,
                background: isSelected ? "oklch(0.72 0.18 145 / 0.1)" : "transparent",
                color: "var(--fg, #fafafa)",
                fontSize: "0.875rem",
                cursor: "pointer",
                fontFamily: "var(--font-mono), monospace",
              }}
              aria-pressed={isSelected}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DoneNextCards({ t }: { t: (k: string, fb?: string) => string }) {
  const cards = [
    { href: "/v2/pipeline", label: t("tour.done.next_pipeline") },
    { href: "/policy", label: t("tour.done.next_policy") },
    { href: "/v2/mcp", label: t("tour.done.next_mcp") },
    { href: "/v2/admin", label: t("tour.done.next_team") },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      {cards.map((c) => (
        <a
          key={c.href}
          href={c.href}
          style={{
            display: "block",
            padding: 12,
            borderRadius: 6,
            border: "1px solid var(--border-subtle, #52525b)",
            color: "var(--fg, #fafafa)",
            fontSize: "0.875rem",
            textDecoration: "none",
            textAlign: "center",
          }}
        >
          {c.label}
        </a>
      ))}
    </div>
  );
}
