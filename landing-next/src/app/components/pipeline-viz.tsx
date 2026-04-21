"use client";

import { Brain, ShieldCheck, Play, CheckCircle2, Rocket } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * PipelineViz — Verified Autonomy Pipeline visualization, i18n-aware.
 * Icons stay constant; labels + aria strings are translated.
 */
export function PipelineViz() {
  const t = useTranslations("pipeline");

  const STAGES = [
    { key: "Plan",     label: t("stagePlan"),     aria: t("ariaPlan"),     icon: Brain },
    { key: "Gate",     label: t("stageGate"),     aria: t("ariaGate"),     icon: ShieldCheck },
    { key: "Execute",  label: t("stageExecute"),  aria: t("ariaExecute"),  icon: Play },
    { key: "Validate", label: t("stageValidate"), aria: t("ariaValidate"), icon: CheckCircle2 },
    { key: "Ship",     label: t("stageShip"),     aria: t("ariaShip"),     icon: Rocket },
  ] as const;

  return (
    <div
      role="img"
      aria-label={t("ariaLabel")}
      className="occp-pipeline-viz mx-auto mt-14 w-full max-w-5xl"
    >
      <ol className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          return (
            <li
              key={s.key}
              aria-label={s.aria}
              style={{ ["--d" as string]: `${i * 0.8}s` }}
              className="occp-pipeline-node group relative flex flex-1 items-center gap-3 rounded-lg border border-border-subtle bg-bg-elev/40 px-4 py-3 sm:flex-col sm:justify-center sm:text-center"
            >
              <Icon className="h-5 w-5 text-brand" aria-hidden="true" />
              <span className="font-mono text-sm uppercase tracking-wider">
                {s.label}
              </span>
            </li>
          );
        })}
      </ol>

      <style>{`
        .occp-pipeline-node {
          transition: transform .3s ease, box-shadow .3s ease, border-color .3s ease;
        }
        @media (prefers-reduced-motion: no-preference) {
          .occp-pipeline-node {
            animation: occpStagePulse 6s ease-in-out infinite;
            animation-delay: var(--d, 0s);
          }
        }
        @keyframes occpStagePulse {
          0%, 66%, 100% {
            transform: scale(1);
            border-color: var(--color-border-subtle, rgba(120,120,255,.2));
            box-shadow: 0 0 0 rgba(120,120,255,0);
          }
          6%, 12% {
            transform: scale(1.05);
            border-color: var(--color-brand);
            box-shadow: 0 0 24px color-mix(in oklab, var(--color-brand) 55%, transparent);
          }
        }
      `}</style>
    </div>
  );
}
