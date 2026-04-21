import { Brain, ShieldCheck, Play, CheckCircle2, Rocket } from "lucide-react";

/**
 * PipelineViz — Verified Autonomy Pipeline visualization.
 *
 * Pure CSS + Tailwind animation. No video, no Lottie, no deps beyond
 * lucide-react (already present). Honors prefers-reduced-motion.
 *
 * Total cycle: 5 stages × 0.8s + 2s idle = 6s. Delay per node via
 * inline --d custom property feeding the shared @keyframes `stagePulse`.
 */
const STAGES = [
  { label: "Plan",     icon: Brain,        aria: "Plan stage" },
  { label: "Gate",     icon: ShieldCheck,  aria: "Policy gate stage" },
  { label: "Execute",  icon: Play,         aria: "Execute stage" },
  { label: "Validate", icon: CheckCircle2, aria: "Validate stage" },
  { label: "Ship",     icon: Rocket,       aria: "Ship stage" },
] as const;

export function PipelineViz() {
  return (
    <div
      role="img"
      aria-label="Verified Autonomy Pipeline: Plan, Gate, Execute, Validate, Ship"
      className="occp-pipeline-viz mx-auto mt-14 w-full max-w-5xl"
    >
      <ol className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          return (
            <li
              key={s.label}
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
