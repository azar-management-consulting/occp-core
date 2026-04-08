"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { OnboardingStatus, OnboardingStartResult, VerificationResult } from "@/lib/api";
import { useT } from "@/lib/i18n";

const WIZARD_STEPS = [
  "landing_cta",
  "auth_check",
  "llm_token",
  "agent_init",
  "skills_config",
  "gsd_init",
  "mcp_config",
  "policy_config",
  "verification",
  "first_task",
] as const;

const STEP_ICONS = ["🚀", "🔐", "⚡", "🤖", "🧠", "⚙", "🔌", "🛡", "✓", "🎯"];

type WizardState = "landing" | "token_present" | "running" | "done";

export function WelcomePanel() {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stepping, setStepping] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null);
  const [launchingTask, setLaunchingTask] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);
  const t = useT();

  const loadStatus = useCallback(async () => {
    try {
      const data = await api.onboardingStatus();
      setStatus(data);
    } catch {
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
          ? {
              ...prev,
              wizard_state: result.wizard_state,
              current_step: result.current_step,
              current_step_name: result.current_step_name,
              completed_steps: result.completed_steps,
              steps: result.steps,
            }
          : null,
      );
      await loadStatus();
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : "Failed to start wizard");
    } finally {
      setStarting(false);
    }
  };

  const handleStep = async (stepName: string) => {
    setStepping(true);
    try {
      await api.onboardingStep(stepName);
      setWizardError(null);
      await loadStatus();
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : `Step "${stepName}" failed`);
    } finally {
      setStepping(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const result = await api.onboardingVerify();
      setVerifyResult(result);
      if (result.all_passed) {
        await api.onboardingStep("verification");
        setWizardError(null);
        await loadStatus();
      } else {
        const failed = result.checks.filter((c) => !c.passed).map((c) => c.name);
        setWizardError(`Verification failed: ${failed.join(", ")}`);
      }
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  };

  const handleFirstTask = async () => {
    setLaunchingTask(true);
    try {
      const result = await api.onboardingFirstTask();
      if (result.success) {
        await api.onboardingStep("first_task");
        setWizardError(null);
        await loadStatus();
      } else {
        setWizardError(result.error || "First task failed — pipeline may not be ready");
      }
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : "First task launch failed");
    } finally {
      setLaunchingTask(false);
    }
  };

  const wizardState: WizardState =
    (status?.wizard_state as WizardState) || "landing";

  const stepLabels: Record<string, string> = {
    landing_cta: t.onboarding.stepLanding,
    auth_check: t.onboarding.stepAuth,
    llm_token: t.onboarding.stepLlm,
    agent_init: t.onboarding.stepAgents,
    skills_config: t.onboarding.stepSkills,
    gsd_init: t.onboarding.stepGsd,
    mcp_config: t.onboarding.stepMcp,
    policy_config: t.onboarding.stepPolicies,
    verification: t.onboarding.stepVerify,
    first_task: t.onboarding.stepFirstTask,
  };

  if (loading) {
    return (
      <div className="retro-card p-6 crt-glow animate-pulse">
        <div className="h-4 bg-occp-muted/20 rounded w-48 mb-3" />
        <div className="h-3 bg-occp-muted/10 rounded w-72" />
      </div>
    );
  }

  // ── landing (no token, no auth context) ──
  if (wizardState === "landing") {
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
              href="/settings/tokens"
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

  // ── token_present (ready to start wizard) ──
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

  // ── running (10-step wizard) ──
  if (wizardState === "running") {
    const currentStepIndex = status?.current_step ?? 0;
    const completedSteps = status?.completed_steps ?? [];
    const totalSteps = status?.total_steps ?? WIZARD_STEPS.length;
    const progressPct = Math.round(
      (completedSteps.length / totalSteps) * 100,
    );

    return (
      <div className="retro-card p-6 crt-glow border-occp-primary/30 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="font-pixel text-[12px] text-occp-primary tracking-wider uppercase">
            {t.onboarding.title}
          </h2>
          <div className="flex items-center gap-3">
            <span className="font-pixel text-[10px] text-occp-accent">
              {t.onboarding.stepProgress
                .replace("{current}", String(completedSteps.length))
                .replace("{total}", String(totalSteps))}
            </span>
            <span className="font-mono text-[10px] text-[var(--text-muted)]">
              {progressPct}%
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex gap-0.5">
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
        <div className="space-y-1.5">
          {WIZARD_STEPS.map((step, i) => {
            const isCompleted = completedSteps.includes(step);
            const isCurrent = i === currentStepIndex;
            const isVerification = step === "verification";
            const isFirstTask = step === "first_task";

            return (
              <div
                key={step}
                className={`flex items-center justify-between p-2.5 rounded border transition-all ${
                  isCompleted
                    ? "bg-occp-success/5 border-occp-success/20"
                    : isCurrent
                      ? "bg-occp-primary/5 border-occp-primary/30"
                      : "bg-occp-dark/30 border-occp-muted/10"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm w-5 text-center">{STEP_ICONS[i]}</span>
                  <div>
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
                    {isCurrent && status?.step_descriptions?.[step] && (
                      <p className="text-[10px] text-[var(--text-muted)] font-mono mt-0.5">
                        {status.step_descriptions[step]}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isCompleted && (
                    <span className="font-pixel text-[9px] text-occp-success px-1.5 py-0.5 rounded bg-occp-success/10 border border-occp-success/20">
                      ✓
                    </span>
                  )}
                  {isCurrent && !isCompleted && isVerification && (
                    <button
                      onClick={handleVerify}
                      disabled={verifying}
                      className="font-pixel text-[9px] text-occp-accent px-2 py-0.5 rounded bg-occp-accent/10 border border-occp-accent/20 hover:bg-occp-accent/20 transition-all"
                    >
                      {verifying ? "..." : "VERIFY"}
                    </button>
                  )}
                  {isCurrent && !isCompleted && isFirstTask && (
                    <button
                      onClick={handleFirstTask}
                      disabled={launchingTask}
                      className="font-pixel text-[9px] text-occp-warning px-2 py-0.5 rounded bg-occp-warning/10 border border-occp-warning/20 hover:bg-occp-warning/20 transition-all"
                    >
                      {launchingTask ? "..." : "LAUNCH"}
                    </button>
                  )}
                  {isCurrent && !isCompleted && !isVerification && !isFirstTask && (
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

        {/* Wizard Error Banner */}
        {wizardError && (
          <div className="p-3 rounded border border-occp-danger/30 bg-occp-danger/5 flex items-start gap-2">
            <span className="font-pixel text-[10px] text-occp-danger shrink-0">⚠ ERROR</span>
            <span className="text-[10px] text-occp-danger font-mono break-all">{wizardError}</span>
            <button
              onClick={() => setWizardError(null)}
              className="ml-auto text-occp-danger/60 hover:text-occp-danger text-xs shrink-0"
            >
              ✕
            </button>
          </div>
        )}

        {/* Verification Results Inline */}
        {verifyResult && (
          <div className="p-3 rounded border border-occp-muted/20 bg-occp-dark/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-pixel text-[10px] text-occp-accent tracking-wider">
                VERIFICATION
              </span>
              <span
                className={`font-pixel text-[9px] px-2 py-0.5 rounded ${
                  verifyResult.all_passed
                    ? "bg-occp-success/10 text-occp-success border border-occp-success/20"
                    : "bg-occp-danger/10 text-occp-danger border border-occp-danger/20"
                }`}
              >
                {verifyResult.passed_count}/{verifyResult.total_checks} PASSED
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {verifyResult.checks.map((check) => (
                <div
                  key={check.name}
                  className={`flex items-center gap-2 p-1.5 rounded text-[10px] font-mono ${
                    check.passed
                      ? "text-occp-success bg-occp-success/5"
                      : "text-occp-danger bg-occp-danger/5"
                  }`}
                >
                  <span>{check.passed ? "✓" : "✗"}</span>
                  <span>{check.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}
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
