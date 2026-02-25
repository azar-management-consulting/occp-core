"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { OnboardingStatus, OnboardingStartResult } from "@/lib/api";
import { useT } from "@/lib/i18n";

const WIZARD_STEPS = [
  "llm_health",
  "mcp_install",
  "skills_install",
  "tool_policies",
  "session_scope",
  "verification",
] as const;

const STEP_ICONS = ["⚡", "🔌", "🧠", "🛡", "🔒", "✓"];

type WizardState = "token_missing" | "token_present" | "running" | "done";

export function WelcomePanel() {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stepping, setStepping] = useState(false);
  const t = useT();

  const loadStatus = useCallback(async () => {
    try {
      const data = await api.onboardingStatus();
      setStatus(data);
    } catch {
      // API might not be available yet — show token_missing state
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleStart = async () => {
    setStarting(true);
    try {
      const result: OnboardingStartResult = await api.onboardingStart();
      setStatus((prev) =>
        prev
          ? { ...prev, wizard_state: result.wizard_state, current_step: result.current_step }
          : null
      );
      await loadStatus();
    } catch {
      // ignore start errors
    } finally {
      setStarting(false);
    }
  };

  const handleStep = async (stepName: string) => {
    setStepping(true);
    try {
      await api.onboardingStep(stepName);
      await loadStatus();
    } catch {
      // ignore step errors
    } finally {
      setStepping(false);
    }
  };

  const wizardState: WizardState = status?.wizard_state as WizardState || "token_missing";

  const stepLabels: Record<string, string> = {
    llm_health: t.onboarding.stepLlm,
    mcp_install: t.onboarding.stepMcp,
    skills_install: t.onboarding.stepSkills,
    tool_policies: t.onboarding.stepPolicies,
    session_scope: t.onboarding.stepSession,
    verification: t.onboarding.stepVerify,
  };

  if (loading) {
    return (
      <div className="retro-card p-6 crt-glow animate-pulse">
        <div className="h-4 bg-occp-muted/20 rounded w-48 mb-3" />
        <div className="h-3 bg-occp-muted/10 rounded w-72" />
      </div>
    );
  }

  // ── token_missing ──
  if (wizardState === "token_missing") {
    return (
      <div className="retro-card p-6 crt-glow border-occp-warning/30">
        <div className="flex items-start gap-4">
          <div className="text-2xl">🔑</div>
          <div className="flex-1 space-y-3">
            <div>
              <h2 className="font-pixel text-[12px] text-occp-warning tracking-wider uppercase">
                {t.onboarding.tokenMissing}
              </h2>
              <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                {t.onboarding.tokenMissingDesc}
              </p>
            </div>
            <Link
              href="/settings"
              className="retro-btn-primary inline-block text-center text-xs"
            >
              {t.onboarding.addToken} →
            </Link>
          </div>
          <div className="flex-shrink-0">
            <span className="inline-block w-2 h-4 bg-occp-warning animate-blink" />
          </div>
        </div>
      </div>
    );
  }

  // ── token_present ──
  if (wizardState === "token_present") {
    return (
      <div className="retro-card p-6 crt-glow border-occp-success/30">
        <div className="flex items-start gap-4">
          <div className="text-2xl">✦</div>
          <div className="flex-1 space-y-3">
            <div>
              <p className="text-xs text-occp-success font-mono">
                {t.onboarding.welcomeGreet}
              </p>
              <h2 className="font-pixel text-[12px] text-occp-primary tracking-wider uppercase mt-2">
                {t.onboarding.title}
              </h2>
              <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                {t.onboarding.subtitle}
              </p>
            </div>
            <button
              onClick={handleStart}
              disabled={starting}
              className="retro-btn-primary text-xs"
            >
              {starting ? t.onboarding.running : t.onboarding.startGuided}
            </button>
          </div>
          <div className="flex-shrink-0">
            <span className="inline-block w-2 h-4 bg-occp-success animate-blink" />
          </div>
        </div>
      </div>
    );
  }

  // ── running ──
  if (wizardState === "running") {
    const currentStepIndex = status?.current_step ?? 0;
    const completedSteps = status?.completed_steps ?? [];
    const totalSteps = status?.total_steps ?? WIZARD_STEPS.length;
    const currentStepName = WIZARD_STEPS[currentStepIndex] || WIZARD_STEPS[0];

    return (
      <div className="retro-card p-6 crt-glow border-occp-primary/30 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="font-pixel text-[12px] text-occp-primary tracking-wider uppercase">
            {t.onboarding.title}
          </h2>
          <span className="font-pixel text-[10px] text-occp-accent">
            {t.onboarding.stepProgress
              .replace("{current}", String(currentStepIndex + 1))
              .replace("{total}", String(totalSteps))}
          </span>
        </div>

        {/* Progress bar */}
        <div className="flex gap-1">
          {WIZARD_STEPS.map((step, i) => (
            <div
              key={step}
              className={`flex-1 h-1.5 rounded-full transition-all ${
                completedSteps.includes(step)
                  ? "bg-occp-success"
                  : i === currentStepIndex
                    ? "bg-occp-primary animate-pulse"
                    : "bg-occp-muted/20"
              }`}
            />
          ))}
        </div>

        {/* Step list */}
        <div className="space-y-2">
          {WIZARD_STEPS.map((step, i) => {
            const isCompleted = completedSteps.includes(step);
            const isCurrent = i === currentStepIndex;

            return (
              <div
                key={step}
                className={`flex items-center justify-between p-3 rounded border transition-all ${
                  isCompleted
                    ? "bg-occp-success/5 border-occp-success/20"
                    : isCurrent
                      ? "bg-occp-primary/5 border-occp-primary/30"
                      : "bg-occp-dark/30 border-occp-muted/10"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm">{STEP_ICONS[i]}</span>
                  <span
                    className={`font-mono text-xs ${
                      isCompleted
                        ? "text-occp-success"
                        : isCurrent
                          ? "text-occp-primary font-bold"
                          : "text-[var(--text-muted)]"
                    }`}
                  >
                    {stepLabels[step] || step}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {isCompleted && (
                    <span className="font-pixel text-[9px] text-occp-success px-1.5 py-0.5 rounded bg-occp-success/10 border border-occp-success/20">
                      ✓
                    </span>
                  )}
                  {isCurrent && !isCompleted && (
                    <button
                      onClick={() => handleStep(step)}
                      disabled={stepping}
                      className="font-pixel text-[9px] text-occp-primary px-2 py-0.5 rounded bg-occp-primary/10 border border-occp-primary/20 hover:bg-occp-primary/20 transition-all"
                    >
                      {stepping ? "..." : "RUN"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ── done ──
  return (
    <div className="retro-card p-6 crt-glow border-occp-success/30">
      <div className="flex items-start gap-4">
        <div className="text-2xl">✦</div>
        <div className="flex-1 space-y-4">
          <div>
            <h2 className="font-pixel text-[12px] text-occp-success tracking-wider uppercase">
              {t.onboarding.complete}
            </h2>
            <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
              {t.onboarding.completeDesc}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/pipeline" className="retro-btn-primary text-xs text-center">
              {t.onboarding.createTask}
            </Link>
            <Link
              href="/mcp"
              className="text-xs font-mono px-3 py-1.5 rounded bg-occp-accent/10 text-occp-accent border border-occp-accent/20 hover:bg-occp-accent/20 transition-all"
            >
              {t.onboarding.installMcp}
            </Link>
            <Link
              href="/skills"
              className="text-xs font-mono px-3 py-1.5 rounded bg-occp-accent/10 text-occp-accent border border-occp-accent/20 hover:bg-occp-accent/20 transition-all"
            >
              {t.onboarding.addSkill}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
