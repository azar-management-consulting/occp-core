"use client";

import { motion, useInView } from "motion/react";
import { useRef } from "react";
import { useTranslations } from "next-intl";

type FAQItem = { q: string; a: string };

export function FAQ() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const t = useTranslations("faq");
  const items = t.raw("items") as FAQItem[];

  return (
    <section
      ref={ref}
      className="mx-auto max-w-3xl px-4 py-20"
      aria-labelledby="faq-heading"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.4 }}
        className="mb-12 text-center"
      >
        <p className="eyebrow mb-3">{t("eyebrow")}</p>
        <h2 id="faq-heading" className="section-heading">
          {t("heading")}
        </h2>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="flex flex-col"
        style={{
          borderTop: "1px solid var(--color-border-subtle)",
        }}
      >
        {items.map((item, i) => (
          <details
            key={i}
            className="group py-5"
            style={{ borderBottom: "1px solid var(--color-border-subtle)" }}
          >
            <summary
              className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
            >
              <span>{item.q}</span>
              {/* Chevron rotates when details is open via CSS */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="shrink-0 text-fg-muted transition-transform duration-200 group-open:rotate-90"
                aria-hidden="true"
              >
                <path d="M6 3l5 5-5 5" />
              </svg>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              {item.a}
            </p>
          </details>
        ))}
      </motion.div>
    </section>
  );
}
