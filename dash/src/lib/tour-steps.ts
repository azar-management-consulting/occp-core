/**
 * Wizard step definitions — 5 steps. Persona-adapted copy in Step 3.
 * Anchor selectors must match real DOM. Verify before commit-9 ships.
 */
import type { TourPersona, TourStepId } from "@/components/onboarding/onboarding-provider";

export interface TourStepDef {
  id: TourStepId;
  /** localStorage key (i18n) — composed via tOnboarding(). */
  i18n: {
    title: string;
    subtitle?: string | { compliance?: string; engineer?: string; operator?: string };
    primary: string;
    secondary?: string;
  };
  anchorSelector: string | null;
  variant: "info" | "pro-tip" | "warning";
}

export const TOUR_STEPS: TourStepDef[] = [
  {
    id: "step-1",
    i18n: {
      title: "tour.welcome.title",
      subtitle: "tour.welcome.subtitle",
      primary: "tour.welcome.cta_primary",
    },
    anchorSelector: null, // centered modal
    variant: "pro-tip",
  },
  {
    id: "step-2",
    i18n: {
      title: "tour.apikey.title",
      subtitle: "tour.apikey.subtitle",
      primary: "tour.apikey.cta_primary",
      secondary: "tour.apikey.cta_back",
    },
    anchorSelector: '[data-tour="api-key-tile"]',
    variant: "pro-tip",
  },
  {
    id: "step-3",
    i18n: {
      title: "tour.firsttask.title",
      subtitle: {
        compliance: "tour.firsttask.subtitle_compliance",
        engineer: "tour.firsttask.subtitle_engineer",
        operator: "tour.firsttask.subtitle_engineer",
      },
      primary: "tour.firsttask.cta_primary",
      secondary: "tour.apikey.cta_back",
    },
    anchorSelector: '[data-tour="new-task-button"]',
    variant: "pro-tip",
  },
  {
    id: "step-4",
    i18n: {
      title: "tour.brian.title",
      subtitle: "tour.brian.subtitle",
      primary: "tour.brian.cta_primary",
      secondary: "tour.apikey.cta_back",
    },
    anchorSelector: '[data-brian-trigger]',
    variant: "pro-tip",
  },
  {
    id: "step-5",
    i18n: {
      title: "tour.done.title",
      subtitle: "tour.done.subtitle",
      primary: "tour.done.cta_primary",
    },
    anchorSelector: null, // centered modal
    variant: "info",
  },
];

export function getStep(id: TourStepId): TourStepDef | undefined {
  return TOUR_STEPS.find((s) => s.id === id);
}

export function getSubtitleKey(
  step: TourStepDef,
  persona: TourPersona,
): string | undefined {
  const s = step.i18n.subtitle;
  if (!s) return undefined;
  if (typeof s === "string") return s;
  if (persona && s[persona]) return s[persona];
  return s.engineer ?? s.compliance ?? s.operator;
}
