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
import { useTranslations } from "next-intl";

type CardKey =
  | "vap"
  | "euAiAct"
  | "mcpCatalog"
  | "cost"
  | "killSwitch"
  | "auditChain";

const CARDS: ReadonlyArray<{
  key: CardKey;
  icon: typeof ShieldCheck;
  href: string;
}> = [
  { key: "vap", icon: ShieldCheck, href: "https://docs.occp.ai/concepts/vap" },
  {
    key: "euAiAct",
    icon: FileText,
    href: "https://docs.occp.ai/compliance/eu-ai-act",
  },
  { key: "mcpCatalog", icon: Wrench, href: "https://docs.occp.ai/tools/mcp" },
  {
    key: "cost",
    icon: DollarSign,
    href: "https://docs.occp.ai/observability/cost",
  },
  {
    key: "killSwitch",
    icon: Power,
    href: "https://docs.occp.ai/operations/kill-switch",
  },
  {
    key: "auditChain",
    icon: Link2,
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
  const t = useTranslations("features");

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
        <p className="eyebrow mb-3">{t("eyebrow")}</p>
        <h2
          id="features-heading"
          className="section-heading mx-auto max-w-2xl"
        >
          {t("heading")}
        </h2>
      </motion.div>

      <motion.ul
        role="list"
        variants={containerVariants}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {CARDS.map((f) => {
          const Icon = f.icon;
          const title = t(`cards.${f.key}.title`);
          const description = t(`cards.${f.key}.description`);
          return (
            <motion.li
              key={f.key}
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
                  {title}
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted line-clamp-3">
                  {description}
                </p>
              </div>

              <a
                href={f.href}
                className="mt-auto text-sm font-medium text-brand transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                aria-label={t("learnMoreAria", { title })}
              >
                {t("learnMore")}
              </a>
            </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}
