"use client";

import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslations } from "next-intl";

type IntegrationKey =
  | "mcp"
  | "openTelemetry"
  | "supabase"
  | "cloudflare"
  | "github"
  | "slack";

const INTEGRATIONS: ReadonlyArray<{ key: IntegrationKey; label: string }> = [
  { key: "mcp", label: "MCP" },
  { key: "openTelemetry", label: "OpenTelemetry" },
  { key: "supabase", label: "Supabase" },
  { key: "cloudflare", label: "Cloudflare" },
  { key: "github", label: "GitHub" },
  { key: "slack", label: "Slack" },
] as const;

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
};

const tileVariants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

export function SocialProof() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const t = useTranslations("socialProof");

  return (
    <section
      ref={ref}
      className="border-t py-16"
      style={{ borderColor: "var(--color-border-subtle)" }}
      aria-labelledby="integrations-heading"
    >
      <div className="mx-auto max-w-6xl px-4">
        <motion.p
          id="integrations-heading"
          initial={{ opacity: 0, y: 12 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.4 }}
          className="mb-8 text-center text-xl font-semibold tracking-tight"
        >
          {t("heading")}
        </motion.p>

        <motion.ul
          role="list"
          variants={containerVariants}
          initial="hidden"
          animate={inView ? "visible" : "hidden"}
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
        >
          {INTEGRATIONS.map((item) => (
            <motion.li
              key={item.key}
              variants={tileVariants}
              title={t(`titles.${item.key}`)}
              className="flex h-16 items-center justify-center rounded-lg border text-sm font-medium transition-colors duration-150 hover:bg-bg-elev"
              style={{
                borderColor: "var(--color-border-subtle)",
                color: "var(--color-fg-muted)",
              }}
            >
              {item.label}
            </motion.li>
          ))}
        </motion.ul>
      </div>
    </section>
  );
}
