import Link from "next/link";
import { CodeTabs } from "./code-tabs";

/**
 * OCCP Landing Hero — 2026-Q2 redesign.
 *
 * Copy per .planning/OCCP_LANDING_10_2026.md §2:
 *   H1: "Ship AI agents you can defend in an audit."
 *   Sub: "Every autonomous action verified, logged, and reversible — before it runs."
 *   Primary CTA: "Start free — no credit card" → dash.occp.ai/onboarding/start
 *   Secondary CTA (ghost): "Read the docs" → docs.occp.ai
 */
export function Hero() {
  return (
    <section className="mx-auto grid max-w-7xl gap-12 px-6 py-20 lg:grid-cols-2 lg:py-28">
      {/* Left: copy */}
      <div className="flex flex-col justify-center">
        <span className="mb-6 inline-block w-fit rounded-full border border-brand-subtle bg-brand-subtle/10 px-3 py-1 text-xs font-mono uppercase tracking-wider text-brand">
          v1.0 · Open Source · SOC2 Type II · EU AI Act Art. 14
        </span>

        <h1 className="mb-5 text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
          Ship AI agents you can{" "}
          <span className="cursor-blink text-brand">defend in an audit</span>
        </h1>

        <p className="mb-8 max-w-xl text-lg text-fg-muted">
          Every autonomous action verified, logged, and reversible — before it runs. The
          open-source Agent Control Plane with a 5-gate Verified Autonomy Pipeline.
          Policy-enforced. Tamper-evident. Self-hosted or managed.
        </p>

        <div className="flex flex-wrap gap-3">
          <Link
            href="https://dash.occp.ai/onboarding/start"
            className="inline-flex items-center justify-center rounded-md bg-brand px-6 py-3 text-base font-medium text-bg shadow-sm transition hover:opacity-90"
          >
            Start free — no credit card
          </Link>
          <Link
            href="https://docs.occp.ai"
            className="inline-flex items-center justify-center rounded-md border border-border-subtle px-6 py-3 text-base font-medium text-fg transition hover:bg-bg-elev"
          >
            Read the docs
          </Link>
          <Link
            href="https://github.com/azar-management-consulting/occp-core"
            className="inline-flex items-center self-center text-sm font-medium text-fg-muted transition hover:text-fg"
          >
            ★ Star on GitHub
          </Link>
        </div>

        <p className="mt-10 text-sm text-fg-muted">
          <span className="font-mono uppercase tracking-wider">Built on</span> OpenAI ·
          Anthropic · MCP · OpenTelemetry · FastAPI · Postgres
        </p>
      </div>

      {/* Right: code snippet split */}
      <div className="flex items-center">
        <CodeTabs />
      </div>
    </section>
  );
}
