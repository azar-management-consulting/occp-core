"use client";

import { Check } from "lucide-react";
import { motion, useInView } from "motion/react";
import { useRef } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";

type TierKey = "free" | "team" | "enterprise";

const TIERS: ReadonlyArray<{
  key: TierKey;
  ctaHref: string;
  highlighted?: boolean;
}> = [
  {
    key: "free",
    ctaHref: "https://dash.occp.ai/onboarding/start",
  },
  {
    key: "team",
    ctaHref: "https://dash.occp.ai/onboarding/team",
    highlighted: true,
  },
  {
    key: "enterprise",
    ctaHref: "mailto:enterprise@occp.ai",
  },
] as const;

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

export function PricingPreview() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const t = useTranslations("pricing");

  return (
    <section
      ref={ref}
      className="mx-auto max-w-6xl px-4 py-20"
      aria-labelledby="pricing-heading"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
        className="mb-12 text-center"
      >
        <p className="eyebrow mb-3">{t("eyebrow")}</p>
        <h2 id="pricing-heading" className="section-heading">
          {t("heading")}
        </h2>
        <p className="mt-4 text-fg-muted">
          {t("subtitleBefore")}{" "}
          <Link
            href="/pricing"
            className="text-brand underline underline-offset-2 hover:opacity-80"
          >
            {t("subtitleLink")}
          </Link>
          {t("subtitleAfter")}
        </p>
      </motion.div>

      <motion.ul
        role="list"
        variants={containerVariants}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        className="grid items-center gap-4 md:grid-cols-3"
      >
        {TIERS.map((tier) => {
          const name = t(`tiers.${tier.key}.name`);
          const price = t(`tiers.${tier.key}.price`);
          const period = t(`tiers.${tier.key}.period`);
          const description = t(`tiers.${tier.key}.description`);
          const cta = t(`tiers.${tier.key}.cta`);
          const features = t.raw(`tiers.${tier.key}.features`) as string[];

          return (
            <motion.li
              key={tier.key}
              variants={cardVariants}
              className={[
                "relative flex flex-col gap-6 rounded-xl border p-8 transition-shadow duration-200",
                tier.highlighted
                  ? "scale-105 ring-2 shadow-[0_0_40px_-8px_oklch(0.72_0.18_145/0.35)]"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              style={
                tier.highlighted
                  ? {
                      borderColor: "var(--color-brand)",
                      background: "var(--color-bg-elev)",
                    }
                  : { borderColor: "var(--color-border-subtle)" }
              }
            >
              {tier.highlighted && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand px-3 py-0.5 text-xs font-semibold text-bg">
                  {t("mostPopular")}
                </span>
              )}

              <div>
                <p className="text-sm font-medium text-fg-muted">{name}</p>
                <p className="mt-1 flex items-baseline gap-1">
                  <span className="text-4xl font-semibold tracking-tight">
                    {price}
                  </span>
                  {period && (
                    <span className="text-sm text-fg-muted">{period}</span>
                  )}
                </p>
                <p className="mt-2 text-sm text-fg-muted">{description}</p>
              </div>

              <ul role="list" className="flex flex-col gap-2.5">
                {features.map((feat) => (
                  <li key={feat} className="flex items-start gap-2.5 text-sm">
                    <Check
                      className="mt-0.5 h-4 w-4 shrink-0"
                      style={{ color: "var(--color-brand)" }}
                      aria-hidden="true"
                    />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={tier.ctaHref}
                className={[
                  "mt-auto inline-flex h-10 w-full items-center justify-center rounded-md text-sm font-medium transition",
                  tier.highlighted
                    ? "bg-brand text-bg hover:opacity-90 hover:shadow-[0_0_24px_-4px_oklch(0.72_0.18_145/0.5)]"
                    : "border border-border-subtle text-fg hover:bg-bg-elev",
                ].join(" ")}
              >
                {cta}
              </Link>
            </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}
