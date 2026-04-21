"use client";

import { motion, useInView } from "motion/react";
import { useRef } from "react";

const QUESTIONS = [
  {
    q: "Is OCCP open source?",
    a: "Yes. The Community Edition is MIT-licensed and lives at github.com/azar-management-consulting/occp-core. The Enterprise Edition with advanced policy features and SLA is commercial. All CE features remain free and open forever.",
  },
  {
    q: "Does it work with OpenAI, Anthropic, and local LLMs?",
    a: "OCCP is LLM-agnostic. Any model reachable via an OpenAI-compatible chat-completions endpoint — including Ollama, vLLM, Azure OpenAI, and Anthropic's Claude API — works out of the box. You configure the model per agent, not per installation.",
  },
  {
    q: "How does the kill switch work?",
    a: "A Redis key acts as a global circuit breaker. When triggered (via dashboard, CLI, or API), all active pipeline workers check the key on each gate and halt gracefully within one polling interval — under 200 ms in standard deployments. Partial results are preserved in the audit chain.",
  },
  {
    q: "What data stays on-prem?",
    a: "In self-hosted mode, everything: prompts, agent outputs, tool call payloads, and audit events never leave your infrastructure. In managed mode, only telemetry metadata (token counts, latencies, error codes) is transmitted — raw payloads are encrypted client-side before transmission.",
  },
  {
    q: "EU AI Act compliance — what exactly?",
    a: "OCCP implements Article 14 (human oversight) via mandatory approval gates for high-risk actions, Article 13 (transparency) via structured audit logs in machine-readable format, and Article 9 (risk management) via policy-as-code with Rego. OCCP is not a certification authority — compliance depends on your deployment and use case.",
  },
  {
    q: "Can I self-host?",
    a: "Yes, and it is the default recommended path for regulated industries. Run occp up with Docker Compose and you have the full pipeline locally in under five minutes. Kubernetes Helm charts are available for production deployments. No telemetry is sent in self-hosted mode by default.",
  },
] as const;

export function FAQ() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

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
        <p className="eyebrow mb-3">FAQ</p>
        <h2 id="faq-heading" className="section-heading">
          Common questions
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
        {QUESTIONS.map((item, i) => (
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
