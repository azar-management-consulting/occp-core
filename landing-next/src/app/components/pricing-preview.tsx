"use client";

import { Check } from "lucide-react";
import { motion, useInView } from "motion/react";
import { useRef } from "react";
import Link from "next/link";

type Tier = {
  name: string;
  price: string;
  period?: string;
  description: string;
  cta: string;
  ctaHref: string;
  highlighted?: boolean;
  features: string[];
};

const TIERS: Tier[] = [
  {
    name: "Free",
    price: "$0",
    description: "Self-host, MIT license, Community Edition features.",
    cta: "Start free",
    ctaHref: "https://dash.occp.ai/onboarding/start",
    features: [
      "Full Verified Autonomy Pipeline",
      "Up to 3 agents",
      "Community MCP tool catalog",
      "Audit chain (local storage)",
      "Community support (GitHub)",
    ],
  },
  {
    name: "Team",
    price: "$29",
    period: "/mo",
    description: "Hosted, managed infra, priority support.",
    cta: "Start team",
    ctaHref: "https://dash.occp.ai/onboarding/team",
    highlighted: true,
    features: [
      "Everything in Free",
      "Unlimited agents",
      "Hosted + managed infra",
      "Cost observability dashboard",
      "Priority email support",
    ],
  },
  {
    name: "Enterprise",
    price: "Contact",
    description: "Dedicated instance, SSO, SLA, custom policy.",
    cta: "Contact us",
    ctaHref: "mailto:enterprise@occp.ai",
    features: [
      "Everything in Team",
      "SSO (SAML / OIDC)",
      "99.9% uptime SLA",
      "Dedicated instance",
      "Custom policy engineering",
    ],
  },
];

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
        <p className="eyebrow mb-3">Pricing</p>
        <h2 id="pricing-heading" className="section-heading">
          Simple, transparent pricing
        </h2>
        <p className="mt-4 text-fg-muted">
          Full pricing details on the{" "}
          <Link
            href="/pricing"
            className="text-brand underline underline-offset-2 hover:opacity-80"
          >
            pricing page
          </Link>
          . No hidden metering.
        </p>
      </motion.div>

      <motion.ul
        role="list"
        variants={containerVariants}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        className="grid items-center gap-4 md:grid-cols-3"
      >
        {TIERS.map((tier) => (
          <motion.li
            key={tier.name}
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
                Most popular
              </span>
            )}

            <div>
              <p className="text-sm font-medium text-fg-muted">{tier.name}</p>
              <p className="mt-1 flex items-baseline gap-1">
                <span className="text-4xl font-semibold tracking-tight">
                  {tier.price}
                </span>
                {tier.period && (
                  <span className="text-sm text-fg-muted">{tier.period}</span>
                )}
              </p>
              <p className="mt-2 text-sm text-fg-muted">{tier.description}</p>
            </div>

            <ul role="list" className="flex flex-col gap-2.5">
              {tier.features.map((feat) => (
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
              {tier.cta}
            </Link>
          </motion.li>
        ))}
      </motion.ul>
    </section>
  );
}
