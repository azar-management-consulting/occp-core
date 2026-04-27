"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type TourStepId =
  | "step-1"
  | "step-2"
  | "step-3"
  | "step-4"
  | "step-5";

export type TourPersona =
  | "compliance"
  | "engineer"
  | "operator"
  | null;

export type TourState =
  | TourStepId
  | "idle"
  | "starting"
  | "dismissed"
  | "completed";

export interface OnboardingContextValue {
  state: TourState;
  persona: TourPersona;
  startTour: () => void;
  nextStep: () => void;
  prevStep: () => void;
  skipTour: () => void;
  completeTour: () => void;
  setPersona: (p: TourPersona) => void;
  /** Reset all hint bubble dismissals + tour state. Used by Settings → Help. */
  resetAllHints: () => void;
  /** Restart tour from step 1 (clears completion + dismissal flags). */
  restartTour: () => void;
}

const Ctx = createContext<OnboardingContextValue | null>(null);

const KEY_TOUR_STATE = "occp_tour_state_v1"; // "completed" | "dismissed"
const KEY_TOUR_PERSONA = "occp_tour_persona";
const KEY_HINTS_ENABLED = "occp_hints_enabled"; // "false" disables ALL hints
const KEY_HINT_PREFIX = "occp_hint_";

const STEP_ORDER: TourStepId[] = [
  "step-1",
  "step-2",
  "step-3",
  "step-4",
  "step-5",
];

function readLS(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLS(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // private mode / quota — ignore
  }
}

function removeLS(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

interface ProviderProps {
  children: React.ReactNode;
  /** Auto-start tour for first-time users (no tour_state set). Default: true. */
  autoStart?: boolean;
  /** Delay before auto-start (ms). Default: 1500. */
  autoStartDelayMs?: number;
}

/**
 * Mounts as a sibling of every page. Reads localStorage on first paint to
 * decide whether to show the tour. Writes go through here so localStorage
 * stays the single source of truth.
 *
 * SSR-safe: all window access guarded; useEffect-only mutations.
 */
export function OnboardingProvider({
  children,
  autoStart = true,
  autoStartDelayMs = 1500,
}: ProviderProps) {
  const [state, setState] = useState<TourState>("idle");
  const [persona, setPersonaState] = useState<TourPersona>(null);
  const autoStartFiredRef = useRef(false);

  // Load persisted state on mount (client only).
  useEffect(() => {
    const saved = readLS(KEY_TOUR_STATE);
    const savedPersona = readLS(KEY_TOUR_PERSONA) as TourPersona;
    if (savedPersona) setPersonaState(savedPersona);
    if (saved === "completed" || saved === "dismissed") {
      setState("idle");
      return;
    }
    if (autoStart && !autoStartFiredRef.current) {
      autoStartFiredRef.current = true;
      const t = window.setTimeout(() => {
        setState("starting");
      }, autoStartDelayMs);
      return () => window.clearTimeout(t);
    }
  }, [autoStart, autoStartDelayMs]);

  // Transition: starting → step-1 (immediate).
  useEffect(() => {
    if (state === "starting") setState("step-1");
  }, [state]);

  const startTour = useCallback(() => {
    removeLS(KEY_TOUR_STATE);
    setState("starting");
  }, []);

  const nextStep = useCallback(() => {
    setState((curr) => {
      const idx = STEP_ORDER.indexOf(curr as TourStepId);
      if (idx === -1) return curr;
      const next = STEP_ORDER[idx + 1];
      if (!next) {
        writeLS(KEY_TOUR_STATE, "completed");
        return "completed";
      }
      return next;
    });
  }, []);

  const prevStep = useCallback(() => {
    setState((curr) => {
      const idx = STEP_ORDER.indexOf(curr as TourStepId);
      if (idx <= 0) return curr;
      return STEP_ORDER[idx - 1];
    });
  }, []);

  const skipTour = useCallback(() => {
    writeLS(KEY_TOUR_STATE, "dismissed");
    setState("dismissed");
  }, []);

  const completeTour = useCallback(() => {
    writeLS(KEY_TOUR_STATE, "completed");
    setState("completed");
  }, []);

  const setPersona = useCallback((p: TourPersona) => {
    setPersonaState(p);
    if (p) writeLS(KEY_TOUR_PERSONA, p);
  }, []);

  const resetAllHints = useCallback(() => {
    if (typeof window === "undefined") return;
    try {
      const toRemove: string[] = [];
      for (let i = 0; i < window.localStorage.length; i++) {
        const k = window.localStorage.key(i);
        if (k && k.startsWith(KEY_HINT_PREFIX)) toRemove.push(k);
      }
      toRemove.forEach(removeLS);
      removeLS("occp_all_hints_dismissed");
      writeLS(KEY_HINTS_ENABLED, "true");
    } catch {
      // ignore
    }
  }, []);

  const restartTour = useCallback(() => {
    removeLS(KEY_TOUR_STATE);
    setState("starting");
  }, []);

  const value = useMemo<OnboardingContextValue>(
    () => ({
      state,
      persona,
      startTour,
      nextStep,
      prevStep,
      skipTour,
      completeTour,
      setPersona,
      resetAllHints,
      restartTour,
    }),
    [
      state,
      persona,
      startTour,
      nextStep,
      prevStep,
      skipTour,
      completeTour,
      setPersona,
      resetAllHints,
      restartTour,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTour(): OnboardingContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error(
      "useTour must be used within <OnboardingProvider>. Wrap dash in providers.tsx.",
    );
  }
  return ctx;
}

/** Read whether hints are enabled globally. Reactive helper for HelpBubble. */
export function readHintsGloballyEnabled(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(KEY_HINTS_ENABLED) !== "false";
  } catch {
    return true;
  }
}
