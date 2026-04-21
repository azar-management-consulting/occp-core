"use client";

import {
  ShieldCheck,
  FileText,
  Wrench,
  DollarSign,
  Power,
  Link2,
} from "lucide-react";
import { motion, useInView } from "motion/react";
import { useRef } from "react";

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Verified Autonomy Pipeline",
    description:
      "Five deterministic gates — Plan, Gate, Execute, Validate, Ship — block any action that violates your policy before it reaches production.",
    href: "https://docs.occp.ai/concepts/vap",
  },
  {
    icon: FileText,
    title: "EU AI Act Art. 14 built-in",
    description:
      "Human-in-the-loop escalation, transparent decision logging, and risk classification ship as first-class primitives, not bolt-ons.",
    href: "https://docs.occp.ai/compliance/eu-ai-act",
  },
  {
    icon: Wrench,
    title: "MCP-native tool catalog",
    description:
      "Every tool in the catalog is typed, versioned, and schema-validated against the Model Context Protocol spec before agents can invoke it.",
    href: "https://docs.occp.ai/tools/mcp",
  },
  {
    icon: DollarSign,
    title: "Cost observability",
    description:
      "Per-token USD spend tracked in real time via OpenTelemetry spans. Budget limits and alerts configurable per agent, per policy.",
    href: "https://docs.occp.ai/observability/cost",
  },
  {
    icon: Power,
    title: "Kill switch",
    description:
      "Redis-backed global kill switch halts all running pipelines in under 200 ms. Circuit breaker per agent, per environment, per org.",
    href: "https://docs.occp.ai/operations/kill-switch",
  },
  {
    icon: Link2,
    title: "Audit chain",
    description:
      "Append-only SHA-256 hash chain on every action event. Tamper detection on read. Exportable to S3 or any SIEM.",
    href: "https://docs.occp.ai/audit/chain",
  },
] as const;

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

export function FeaturesGrid() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section
      ref={ref}
      className="mx-auto max-w-6xl px-4 py-20"
      aria-labelledby="features-heading"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
        className="mb-12 text-center"
      >
        <p className="eyebrow mb-3">The platform</p>
        <h2
          id="features-heading"
          className="section-heading mx-auto max-w-2xl"
        >
          Everything a governance-grade agent control plane needs
        </h2>
      </motion.div>

      <motion.ul
        role="list"
        variants={containerVariants}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {FEATURES.map((f) => {
          const Icon = f.icon;
          return (
            <motion.li
              key={f.title}
              variants={cardVariants}
              className="group relative flex flex-col gap-4 rounded-xl border p-6 transition-colors duration-200 hover:bg-bg-elev"
              style={{ borderColor: "var(--color-border-subtle)" }}
            >
              <div
                className="flex h-9 w-9 items-center justify-center rounded-lg"
                style={{ background: "oklch(0.72 0.18 145 / 0.10)" }}
              >
                <Icon
                  className="h-4 w-4"
                  style={{ color: "var(--color-brand)" }}
                  aria-hidden="true"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <h3 className="text-base font-semibold leading-snug">
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted line-clamp-3">
                  {f.description}
                </p>
              </div>

              <a
                href={f.href}
                className="mt-auto text-sm font-medium text-brand transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                aria-label={`Learn more about ${f.title}`}
              >
                Learn more →
              </a>
            </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}
