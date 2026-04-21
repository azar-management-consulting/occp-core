"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { CodeTabs } from "./code-tabs";
import { PipelineViz } from "./pipeline-viz";

/**
 * OCCP Landing Hero — 2026-Q2 redesign, i18n-aware.
 *
 * All user-visible copy lives in `messages/<locale>.json` (namespace: "hero").
 * The extra "social proof" line below the CTAs is kept in English as a
 * compliance shorthand badge; consider moving to messages if it ever changes.
 */

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94], delay },
  }),
};

export function Hero() {
  const t = useTranslations("hero");

  return (
    <section className="mx-auto max-w-7xl px-6 py-20 lg:py-28">
      <div className="grid gap-12 lg:grid-cols-2">
        {/* Left: copy */}
        <div className="flex flex-col justify-center">
          <motion.span
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0}
            className="mb-6 inline-block w-fit rounded-full border border-brand-subtle bg-brand-subtle/10 px-3 py-1 text-xs font-mono uppercase tracking-wider text-brand"
          >
            {t("badge")}
          </motion.span>

          <motion.h1
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0.08}
            className="mb-5 font-semibold tracking-tight leading-[0.95]"
            style={{ fontSize: "clamp(2.5rem, 4vw + 1rem, 5rem)" }}
          >
            {t("headlinePrefix")}{" "}
            <span
              className="gradient-text"
              style={{
                background:
                  "linear-gradient(90deg, var(--color-brand), var(--color-brand-subtle))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              {t("headlineHighlight")}
            </span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0.16}
            className="mb-8 max-w-xl text-lg leading-relaxed text-fg-muted"
          >
            {t("subtitle")}
          </motion.p>

          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0.24}
            className="flex flex-wrap items-center gap-3"
          >
            {/* Primary CTA */}
            <Link
              href="https://dash.occp.ai/onboarding/start"
              className="inline-flex h-12 items-center justify-center rounded-md bg-brand px-6 text-base font-medium text-bg shadow-sm transition-all duration-200 hover:opacity-90 hover:shadow-[0_0_30px_-5px_oklch(0.72_0.18_145/0.5)]"
            >
              {t("ctaPrimary")}
            </Link>

            {/* Secondary ghost CTA */}
            <Link
              href="https://docs.occp.ai"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-md border border-border-subtle px-6 text-base font-medium text-fg transition hover:bg-bg-elev"
            >
              {t("ctaSecondary")}
              <ArrowRight className="h-4 w-4 text-fg-muted" aria-hidden="true" />
            </Link>

            {/* GitHub link */}
            <Link
              href="https://github.com/azar-management-consulting/occp-core"
              className="inline-flex items-center self-center text-sm font-medium text-fg-muted transition hover:text-fg"
            >
              {t("ctaGithub")}
            </Link>
          </motion.div>

          {/* Social proof — text only, no fake logos */}
          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0.32}
            className="mt-6 text-sm text-fg-muted"
          >
            Anthropic-compatible · EU AI Act-ready · MCP-native
          </motion.p>

          <motion.p
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            custom={0.38}
            className="mt-4 text-sm text-fg-muted"
          >
            <span className="font-mono uppercase tracking-wider">
              {t("builtOn")}
            </span>{" "}
            {t("builtOnList")}
          </motion.p>
        </div>

        {/* Right: code snippet */}
        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          custom={0.2}
          className="flex items-center"
        >
          <CodeTabs />
        </motion.div>
      </div>

      {/* Verified Autonomy Pipeline */}
      <motion.div
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        custom={0.4}
      >
        <PipelineViz />
      </motion.div>
    </section>
  );
}
