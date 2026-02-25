"use client";

import Link from "next/link";
import { useState } from "react";

/* ── ASCII Art Logo ─────────────────────────────────────── */
const ASCII_LOGO = `
 ██████╗  ██████╗ ██████╗██████╗
██╔═══██╗██╔════╝██╔════╝██╔══██╗
██║   ██║██║     ██║     ██████╔╝
██║   ██║██║     ██║     ██╔═══╝
╚██████╔╝╚██████╗╚██████╗██║
 ╚═════╝  ╚═════╝ ╚═════╝╚═╝`;

/* ── Code Copy Button ───────────────────────────────────── */
function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative group">
      {label && (
        <div className="text-[7px] font-pixel uppercase tracking-wider text-[var(--text-muted)] mb-1">
          {label}
        </div>
      )}
      <div className="retro-card px-4 py-3 font-mono text-sm overflow-x-auto">
        <code className="text-occp-accent">{code}</code>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          className="absolute top-2 right-2 text-[8px] font-pixel px-2 py-1 border border-[var(--muted)] rounded opacity-0 group-hover:opacity-100 transition-opacity hover:border-[var(--primary)] hover:text-[var(--primary)]"
        >
          {copied ? "OK!" : "COPY"}
        </button>
      </div>
    </div>
  );
}

/* ── Feature Card ───────────────────────────────────────── */
function FeatureCard({
  icon,
  title,
  desc,
  color,
}: {
  icon: string;
  title: string;
  desc: string;
  color: string;
}) {
  return (
    <div className="retro-card p-5 group hover:border-[var(--primary)] transition-all duration-300">
      <div
        className="text-2xl mb-3 transition-transform duration-300 group-hover:scale-110"
        style={{ filter: `drop-shadow(0 0 8px ${color})` }}
      >
        {icon}
      </div>
      <h3 className="font-pixel text-[8px] uppercase tracking-wider mb-2" style={{ color }}>
        {title}
      </h3>
      <p className="text-[var(--text-muted)] text-xs leading-relaxed">{desc}</p>
    </div>
  );
}

/* ── Nav Link Card ──────────────────────────────────────── */
function NavCard({
  href,
  num,
  title,
  desc,
  color,
}: {
  href: string;
  num: string;
  title: string;
  desc: string;
  color: string;
}) {
  return (
    <Link href={href} className="block">
      <div className="retro-card p-5 group hover:border-[var(--primary)] transition-all duration-300 cursor-pointer h-full">
        <div className="flex items-start gap-3">
          <span
            className="font-pixel text-[10px] opacity-40 mt-0.5"
            style={{ color }}
          >
            {num}
          </span>
          <div>
            <h3
              className="font-pixel text-[9px] uppercase tracking-wider mb-1.5 group-hover:text-glow transition-all"
              style={{ color }}
            >
              {title}
            </h3>
            <p className="text-[var(--text-muted)] text-xs leading-relaxed">
              {desc}
            </p>
            <span className="inline-block mt-3 text-[7px] font-pixel uppercase tracking-widest text-[var(--text-muted)] group-hover:text-[var(--primary)] transition-colors">
              EXPLORE &gt;
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

/* ── Endpoint Row ───────────────────────────────────────── */
function EndpointRow({
  method,
  path,
  desc,
}: {
  method: string;
  path: string;
  desc: string;
}) {
  const methodColor: Record<string, string> = {
    GET: "text-occp-success",
    POST: "text-occp-warning",
    DELETE: "text-occp-danger",
    PUT: "text-c64-purple",
    PATCH: "text-occp-accent",
  };
  return (
    <div className="flex items-center gap-4 px-4 py-2.5 border-b border-[var(--muted)]/30 hover:bg-[var(--surface-bright)] transition-colors text-xs">
      <span className={`font-pixel text-[8px] w-12 ${methodColor[method] || "text-[var(--text)]"}`}>
        {method}
      </span>
      <code className="text-occp-accent font-mono flex-1">{path}</code>
      <span className="text-[var(--text-muted)] hidden sm:block">{desc}</span>
    </div>
  );
}

/* ── VAP Stage ──────────────────────────────────────────── */
function VAPStage({
  num,
  label,
  desc,
  color,
  active,
}: {
  num: string;
  label: string;
  desc: string;
  color: string;
  active?: boolean;
}) {
  return (
    <div className={`flex-1 text-center ${active ? "scale-105" : ""} transition-transform`}>
      <div
        className="w-12 h-12 mx-auto rounded-lg flex items-center justify-center font-pixel text-[10px] border-2 mb-2 transition-all"
        style={{
          borderColor: color,
          background: `${color}15`,
          color,
          boxShadow: active ? `0 0 20px ${color}40` : "none",
        }}
      >
        {num}
      </div>
      <div className="font-pixel text-[7px] uppercase tracking-wider mb-1" style={{ color }}>
        {label}
      </div>
      <div className="text-[10px] text-[var(--text-muted)] leading-tight">{desc}</div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   MAIN DOCS PAGE
   ════════════════════════════════════════════════════════════ */
export default function DocsPage() {
  return (
    <div className="min-h-screen">
      {/* ── STICKY TOP NAV ──────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-[var(--muted)]/50 backdrop-blur-md bg-[var(--bg)]/80">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/docs" className="font-pixel text-[9px] text-[var(--primary)] text-glow tracking-wider">
              OCCP
            </Link>
            <div className="hidden md:flex items-center gap-5">
              {[
                { label: "OVERVIEW", href: "#overview" },
                { label: "QUICKSTART", href: "#quickstart" },
                { label: "ARCHITECTURE", href: "#architecture" },
                { label: "API", href: "#api" },
                { label: "MODULES", href: "#modules" },
                { label: "SECURITY", href: "#security" },
              ].map((l) => (
                <a
                  key={l.label}
                  href={l.href}
                  className="font-pixel text-[7px] uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
                >
                  {l.label}
                </a>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/azar-management-consulting/occp-core"
              target="_blank"
              rel="noopener"
              className="font-pixel text-[7px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
            >
              GITHUB
            </a>
            <span className="font-pixel text-[7px] text-occp-accent">v0.8.0</span>
            <Link href="/login" className="retro-btn-primary !text-[8px] !px-3 !py-1.5 font-pixel">
              DASHBOARD
            </Link>
          </div>
        </div>
      </nav>

      {/* ── HERO: C64 BOOT ─────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--primary)]/5 via-transparent to-transparent pointer-events-none" />
        <div className="max-w-6xl mx-auto px-6 pt-16 pb-20">
          <div className="retro-card crt-glow p-8 md:p-12 text-center relative overflow-hidden">
            {/* Decorative corner accents */}
            <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-[var(--primary)]/30" />
            <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-[var(--primary)]/30" />
            <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-[var(--primary)]/30" />
            <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-[var(--primary)]/30" />

            <pre className="font-mono text-[var(--primary)] text-[8px] sm:text-[10px] leading-tight mb-6 text-glow select-none hidden sm:block">
              {ASCII_LOGO}
            </pre>
            <div className="sm:hidden font-pixel text-xl text-[var(--primary)] text-glow mb-4">
              OCCP
            </div>

            <div className="font-pixel text-[8px] sm:text-[10px] text-occp-accent text-glow-cyan mb-4 tracking-widest">
              OPENCLOUD CONTROL PLANE
            </div>

            <p className="text-[var(--text)] text-sm sm:text-base max-w-2xl mx-auto leading-relaxed mb-2">
              Verified Autonomy Pipeline for AI agents.
              <br className="hidden sm:block" />
              Every action planned, gated, executed, validated, and shipped &mdash; with a cryptographic audit trail.
            </p>

            <div className="flex items-center justify-center gap-2 mt-6 mb-8">
              <span className="inline-block w-2 h-2 rounded-full bg-occp-success animate-pulse" />
              <span className="font-mono text-xs text-occp-success">SYSTEM ONLINE</span>
              <span className="text-[var(--text-muted)] text-xs mx-2">|</span>
              <span className="font-mono text-xs text-[var(--text-muted)]">api.occp.ai</span>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a href="#quickstart" className="retro-btn-primary font-pixel !text-[8px] !px-6 !py-3 tracking-wider">
                GET STARTED
              </a>
              <a
                href="https://github.com/azar-management-consulting/occp-core"
                target="_blank"
                rel="noopener"
                className="retro-btn font-pixel !text-[8px] !px-6 !py-3 tracking-wider"
              >
                VIEW SOURCE
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── OVERVIEW ───────────────────────────────────── */}
      <section id="overview" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-[var(--primary)] opacity-40">01</span>
          <h2 className="font-pixel text-[10px] text-[var(--primary)] text-glow uppercase tracking-widest">
            What is OCCP?
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-[var(--primary)]/20 to-transparent" />
        </div>

        <div className="grid md:grid-cols-2 gap-8 items-start">
          <div className="space-y-4 text-sm text-[var(--text-muted)] leading-relaxed">
            <p>
              <strong className="text-[var(--text)]">OCCP</strong> is an open-source control plane that
              governs how AI agents operate in production. Every agent action flows through a{" "}
              <strong className="text-occp-accent">5-stage Verified Autonomy Pipeline (VAP)</strong> &mdash;
              ensuring nothing runs unchecked.
            </p>
            <p>
              Built for teams that deploy autonomous agents but need deterministic safety guarantees,
              immutable audit logs, and policy-gated execution.
            </p>
            <div className="retro-card p-4 mt-4">
              <div className="font-pixel text-[7px] text-occp-warning mb-2 uppercase tracking-wider">
                KEY PRINCIPLE
              </div>
              <p className="text-xs text-[var(--text)] italic">
                &ldquo;Trust but verify&rdquo; &mdash; every agent action is planned, policy-checked,
                executed, validated, and recorded with cryptographic integrity.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <FeatureCard
              icon="&#x1F6E1;&#xFE0F;"
              title="Policy Engine"
              desc="Gate every action with configurable risk policies before execution."
              color="var(--accent)"
            />
            <FeatureCard
              icon="&#x1F517;"
              title="Hash Chain Audit"
              desc="Tamper-proof audit log with SHA-256 hash chain integrity."
              color="var(--success)"
            />
            <FeatureCard
              icon="&#x1F916;"
              title="Agent Registry"
              desc="Register, manage, and monitor AI agents with capability declarations."
              color="var(--primary)"
            />
            <FeatureCard
              icon="&#x26A1;"
              title="Real-time Pipeline"
              desc="WebSocket-powered live monitoring of VAP stage transitions."
              color="var(--warning)"
            />
            <FeatureCard
              icon="&#x1F50C;"
              title="MCP Connectors"
              desc="Model Context Protocol catalog — install and configure tool integrations."
              color="var(--purple)"
            />
            <FeatureCard
              icon="&#x1F9E0;"
              title="Skills Inventory"
              desc="Agent capabilities with token impact analysis and trust scoring."
              color="var(--danger)"
            />
            <FeatureCard
              icon="&#x1F680;"
              title="Onboarding Wizard"
              desc="Guided 6-step setup for LLM, MCP, skills, policies, and session scope."
              color="var(--accent)"
            />
            <FeatureCard
              icon="&#x2699;&#xFE0F;"
              title="LLM Health v2"
              desc="Multi-provider status with cascade failover chain monitoring."
              color="var(--success)"
            />
          </div>
        </div>
      </section>

      {/* ── QUICKSTART ─────────────────────────────────── */}
      <section id="quickstart" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-occp-accent opacity-40">02</span>
          <h2 className="font-pixel text-[10px] text-occp-accent text-glow-cyan uppercase tracking-widest">
            Quick Start
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-occp-accent/20 to-transparent" />
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <div className="retro-card p-6 relative">
            <div className="absolute -top-3 -left-1 font-pixel text-[20px] text-[var(--primary)] opacity-10">
              01
            </div>
            <div className="font-pixel text-[8px] text-[var(--primary)] mb-3 uppercase tracking-wider">
              Install
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Clone the repo and install Python dependencies.
            </p>
            <div className="space-y-2">
              <CodeBlock code="git clone https://github.com/azar-management-consulting/occp-core.git" />
              <CodeBlock code="cd occp-core && pip install -e ." />
            </div>
          </div>

          {/* Step 2 */}
          <div className="retro-card p-6 relative">
            <div className="absolute -top-3 -left-1 font-pixel text-[20px] text-occp-accent opacity-10">
              02
            </div>
            <div className="font-pixel text-[8px] text-occp-accent mb-3 uppercase tracking-wider">
              Configure
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Set your Anthropic API key and start the server.
            </p>
            <div className="space-y-2">
              <CodeBlock code='export OCCP_ANTHROPIC_API_KEY="sk-ant-..."' />
              <CodeBlock code="occp serve --port 8000" />
            </div>
          </div>

          {/* Step 3 */}
          <div className="retro-card p-6 relative">
            <div className="absolute -top-3 -left-1 font-pixel text-[20px] text-occp-success opacity-10">
              03
            </div>
            <div className="font-pixel text-[8px] text-occp-success mb-3 uppercase tracking-wider">
              Run Pipeline
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-4">
              Submit your first task to the Verified Autonomy Pipeline.
            </p>
            <div className="space-y-2">
              <CodeBlock
                code={`curl -X POST localhost:8000/api/v1/pipeline/run \\
  -H "Authorization: Bearer $TOKEN" \\
  -d '{"task_id": "task-001"}'`}
              />
            </div>
          </div>
        </div>

        {/* Docker alternative */}
        <div className="mt-8 retro-card p-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">&#x1F433;</span>
            <span className="font-pixel text-[8px] text-c64-purple uppercase tracking-wider">
              Docker (Recommended for Production)
            </span>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <CodeBlock code="docker compose up -d" label="Start services" />
            <CodeBlock code="curl -s https://api.occp.ai/api/v1/status | jq" label="Verify" />
          </div>
          <p className="text-[10px] text-[var(--text-muted)] mt-3">
            Production deploy: non-root container (uid 1001), read-only rootfs, no-new-privileges,
            127.0.0.1-only port binding, tmpfs /tmp.
          </p>
        </div>
      </section>

      {/* ── ARCHITECTURE: VAP PIPELINE ─────────────────── */}
      <section id="architecture" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-occp-success opacity-40">03</span>
          <h2 className="font-pixel text-[10px] text-occp-success text-glow-green uppercase tracking-widest">
            Architecture
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-occp-success/20 to-transparent" />
        </div>

        {/* VAP Pipeline Visualization */}
        <div className="retro-card crt-glow p-8 mb-8">
          <div className="font-pixel text-[8px] text-center text-[var(--text-muted)] mb-6 uppercase tracking-widest">
            Verified Autonomy Pipeline (VAP)
          </div>

          <div className="flex items-start gap-2 sm:gap-4 relative">
            {/* Connecting line */}
            <div className="absolute top-6 left-[10%] right-[10%] h-px bg-gradient-to-r from-[var(--primary)]/40 via-occp-accent/40 to-occp-success/40 hidden sm:block" />

            <VAPStage num="01" label="Plan" desc="Decompose task into atomic steps" color="var(--primary)" active />
            <VAPStage num="02" label="Gate" desc="Policy check against risk thresholds" color="var(--accent)" />
            <VAPStage num="03" label="Exec" desc="LLM-powered autonomous execution" color="var(--warning)" />
            <VAPStage num="04" label="Valid" desc="Output verification & constraints" color="var(--purple)" />
            <VAPStage num="05" label="Ship" desc="Deploy with audit hash chain" color="var(--success)" />
          </div>
        </div>

        {/* Architecture ASCII diagram */}
        <div className="retro-card p-6">
          <div className="font-pixel text-[7px] text-[var(--text-muted)] mb-4 uppercase tracking-wider">
            System Overview
          </div>
          <pre className="font-mono text-[10px] sm:text-xs text-occp-accent leading-relaxed overflow-x-auto">
{`  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │   CLI / SDK  │────▶│   FastAPI     │────▶│  SQLite DB  │
  │  (Python/TS) │     │   REST API    │     │  + Audit    │
  └─────────────┘     └──────┬───────┘     └─────────────┘
                             │
                    ┌────────┴────────┐
                    │   VAP Engine    │
                    │  5-Stage Pipeline│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌───────────┐ ┌────────────┐
     │ Policy Engine │ │  Anthropic │ │  Dashboard  │
     │ (Risk Gates) │ │  Claude AI │ │  (Next.js)  │
     └──────────────┘ └───────────┘ └────────────┘`}
          </pre>
        </div>
      </section>

      {/* ── API REFERENCE ──────────────────────────────── */}
      <section id="api" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-occp-warning opacity-40">04</span>
          <h2 className="font-pixel text-[10px] text-occp-warning uppercase tracking-widest">
            API Reference
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-occp-warning/20 to-transparent" />
        </div>

        <div className="retro-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--muted)] flex items-center justify-between">
            <span className="font-pixel text-[7px] text-[var(--text-muted)] uppercase tracking-wider">
              Base URL: https://api.occp.ai/api/v1
            </span>
            <span className="font-pixel text-[7px] text-occp-accent">REST + WebSocket</span>
          </div>

          {/* Auth */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-[var(--primary)] uppercase tracking-wider">Authentication</span>
          </div>
          <EndpointRow method="POST" path="/auth/login" desc="Obtain JWT access token" />

          {/* Status */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-success uppercase tracking-wider">Health</span>
          </div>
          <EndpointRow method="GET" path="/status" desc="Platform health & version" />

          {/* Tasks */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-accent uppercase tracking-wider">Tasks</span>
          </div>
          <EndpointRow method="GET" path="/tasks" desc="List all tasks" />
          <EndpointRow method="POST" path="/tasks" desc="Create a new task" />
          <EndpointRow method="GET" path="/tasks/:id" desc="Get task details" />

          {/* Pipeline */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-warning uppercase tracking-wider">Pipeline</span>
          </div>
          <EndpointRow method="POST" path="/pipeline/run" desc="Execute VAP pipeline for a task" />
          <EndpointRow method="GET" path="/pipeline/ws" desc="WebSocket live pipeline events" />

          {/* Agents */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-c64-purple uppercase tracking-wider">Agents</span>
          </div>
          <EndpointRow method="GET" path="/agents" desc="List registered agents" />
          <EndpointRow method="POST" path="/agents" desc="Register a new agent" />
          <EndpointRow method="DELETE" path="/agents/:id" desc="Unregister an agent" />

          {/* Policy */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-danger uppercase tracking-wider">Policy</span>
          </div>
          <EndpointRow method="POST" path="/policy/test" desc="Test policy against a task" />

          {/* Audit */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-[var(--text-muted)] uppercase tracking-wider">Audit</span>
          </div>
          <EndpointRow method="GET" path="/audit" desc="Query immutable audit log" />

          {/* Onboarding */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-accent uppercase tracking-wider">Onboarding</span>
          </div>
          <EndpointRow method="GET" path="/onboarding/status" desc="Current onboarding state & progress" />
          <EndpointRow method="POST" path="/onboarding/start" desc="Initialize onboarding wizard" />
          <EndpointRow method="POST" path="/onboarding/step/:step" desc="Complete a wizard step" />

          {/* MCP */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-c64-purple uppercase tracking-wider">MCP Connectors</span>
          </div>
          <EndpointRow method="GET" path="/mcp/catalog" desc="List available MCP server connectors" />
          <EndpointRow method="POST" path="/mcp/install" desc="Install & configure a connector" />

          {/* Skills */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-danger uppercase tracking-wider">Skills</span>
          </div>
          <EndpointRow method="GET" path="/skills" desc="List skills with token impact" />
          <EndpointRow method="POST" path="/skills/:id/enable" desc="Enable a skill" />
          <EndpointRow method="POST" path="/skills/:id/disable" desc="Disable a skill" />

          {/* LLM Health */}
          <div className="px-4 py-2 bg-[var(--surface-bright)] border-b border-[var(--muted)]/30">
            <span className="font-pixel text-[7px] text-occp-success uppercase tracking-wider">LLM Health</span>
          </div>
          <EndpointRow method="GET" path="/llm/health" desc="Multi-provider status & failover chain" />
        </div>
      </section>

      {/* ── MODULES / NAVIGATION CARDS ─────────────────── */}
      <section id="modules" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-c64-purple opacity-40">05</span>
          <h2 className="font-pixel text-[10px] text-c64-purple uppercase tracking-widest">
            Explore Modules
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-c64-purple/20 to-transparent" />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <NavCard
            href="/pipeline"
            num="01"
            title="Pipeline"
            desc="Submit tasks and monitor the 5-stage VAP execution flow in real-time via WebSocket."
            color="var(--primary)"
          />
          <NavCard
            href="/agents"
            num="02"
            title="Agents"
            desc="Register AI agents, declare capabilities, and manage lifecycle from a central registry."
            color="var(--accent)"
          />
          <NavCard
            href="/policy"
            num="03"
            title="Policy Engine"
            desc="Test and configure risk-based policies that gate agent actions before execution."
            color="var(--warning)"
          />
          <NavCard
            href="/audit"
            num="04"
            title="Audit Log"
            desc="Immutable hash-chain audit trail. Every action cryptographically linked and queryable."
            color="var(--success)"
          />
          <NavCard
            href="#api"
            num="05"
            title="REST API"
            desc="Full REST API with JWT auth. Python and TypeScript SDKs available for integration."
            color="var(--purple)"
          />
          <NavCard
            href="/mcp"
            num="06"
            title="MCP Connectors"
            desc="Model Context Protocol catalog. Install, configure and manage tool server integrations."
            color="var(--purple)"
          />
          <NavCard
            href="/skills"
            num="07"
            title="Skills Inventory"
            desc="Agent capabilities with token impact analysis, trust scoring, and enable/disable controls."
            color="var(--danger)"
          />
          <NavCard
            href="/settings"
            num="08"
            title="Settings"
            desc="LLM provider health monitoring, tool policy groups, and session configuration."
            color="var(--accent)"
          />
          <NavCard
            href="https://github.com/azar-management-consulting/occp-core"
            num="09"
            title="Source Code"
            desc="MIT licensed. FastAPI backend, Next.js dashboard, Python SDK, TypeScript SDK, CLI."
            color="var(--success)"
          />
        </div>
      </section>

      {/* ── TECH STACK ─────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-[var(--text-muted)] opacity-40">06</span>
          <h2 className="font-pixel text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
            Tech Stack
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-[var(--text-muted)]/20 to-transparent" />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Backend", value: "FastAPI + Python 3.12", color: "var(--success)" },
            { label: "Frontend", value: "Next.js 15 + React 19", color: "var(--primary)" },
            { label: "Database", value: "SQLite + aiosqlite", color: "var(--accent)" },
            { label: "Auth", value: "JWT (PyJWT)", color: "var(--warning)" },
            { label: "AI Engine", value: "Anthropic Claude", color: "var(--purple)" },
            { label: "Deploy", value: "Docker + GitHub Actions", color: "var(--danger)" },
            { label: "SDK", value: "Python + TypeScript", color: "var(--primary)" },
            { label: "Hosting", value: "Hetzner Cloud VPS", color: "var(--accent)" },
          ].map((t) => (
            <div key={t.label} className="retro-card p-3 text-center">
              <div className="font-pixel text-[7px] uppercase tracking-wider mb-1" style={{ color: t.color }}>
                {t.label}
              </div>
              <div className="text-xs text-[var(--text)]">{t.value}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── SECURITY ──────────────────────────────────── */}
      <section id="security" className="max-w-6xl mx-auto px-6 pb-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="font-pixel text-[10px] text-occp-danger opacity-40">07</span>
          <h2 className="font-pixel text-[10px] text-occp-danger uppercase tracking-widest">
            Security &amp; Compliance
          </h2>
          <div className="flex-1 h-px bg-gradient-to-r from-occp-danger/20 to-transparent" />
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Security posture */}
          <div className="retro-card p-6">
            <div className="font-pixel text-[8px] text-occp-success mb-4 uppercase tracking-wider">
              Hardening Status
            </div>
            <div className="space-y-2 font-mono text-[11px]">
              {[
                { label: "Non-root container", value: "uid=1001" },
                { label: "Read-only rootfs", value: "API + Dash" },
                { label: "No-new-privileges", value: "enabled" },
                { label: "Port binding", value: "127.0.0.1" },
                { label: "TLS termination", value: "Caddy" },
                { label: "Branch protection", value: "enforced" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <span className="text-[var(--text-muted)]">{item.label}</span>
                  <span className="flex items-center gap-2">
                    <span className="text-occp-success">{item.value}</span>
                    <span className="text-[8px] text-occp-success font-pixel">PASS</span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Guards */}
          <div className="space-y-3">
            <div className="retro-card p-4">
              <div className="font-pixel text-[7px] text-[var(--primary)] mb-1.5 uppercase tracking-wider">
                PII Guard
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Detects and blocks personally identifiable information (emails, SSNs, credit cards) before it reaches the LLM.
              </p>
            </div>
            <div className="retro-card p-4">
              <div className="font-pixel text-[7px] text-occp-warning mb-1.5 uppercase tracking-wider">
                Prompt Injection Guard
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Pattern-matching detection of system prompt overrides, role manipulation, and instruction bypass attempts.
              </p>
            </div>
            <div className="retro-card p-4">
              <div className="font-pixel text-[7px] text-occp-accent mb-1.5 uppercase tracking-wider">
                Resource Limit Guard
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Enforces payload size limits, execution timeouts, and concurrency caps to prevent resource exhaustion.
              </p>
            </div>
          </div>
        </div>

        {/* Legal links */}
        <div className="mt-8 retro-card p-6">
          <div className="font-pixel text-[8px] text-[var(--text-muted)] mb-4 uppercase tracking-wider">
            Legal &amp; Compliance
          </div>
          <div className="grid sm:grid-cols-3 gap-4">
            <Link href="/docs/privacy" className="block group">
              <div className="retro-card p-4 hover:border-[var(--primary)] transition-all">
                <div className="font-pixel text-[8px] text-[var(--primary)] mb-1.5 uppercase tracking-wider group-hover:text-glow">
                  Privacy Policy
                </div>
                <p className="text-[10px] text-[var(--text-muted)]">
                  GDPR Art. 13-14 compliant data processing disclosure. EU data residency.
                </p>
              </div>
            </Link>
            <Link href="/docs/terms" className="block group">
              <div className="retro-card p-4 hover:border-[var(--primary)] transition-all">
                <div className="font-pixel text-[8px] text-occp-accent mb-1.5 uppercase tracking-wider group-hover:text-glow-cyan">
                  Terms of Service
                </div>
                <p className="text-[10px] text-[var(--text-muted)]">
                  Usage terms, license info, liability limitations. Governed by EU/Hungarian law.
                </p>
              </div>
            </Link>
            <Link href="/docs/security" className="block group">
              <div className="retro-card p-4 hover:border-[var(--primary)] transition-all">
                <div className="font-pixel text-[8px] text-occp-danger mb-1.5 uppercase tracking-wider group-hover:text-glow">
                  Security Policy
                </div>
                <p className="text-[10px] text-[var(--text-muted)]">
                  Vulnerability reporting, hardening details, responsible disclosure program.
                </p>
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* ── FOOTER ─────────────────────────────────────── */}
      <footer className="border-t border-[var(--muted)]/30">
        <div className="max-w-6xl mx-auto px-6 py-10">
          <div className="grid sm:grid-cols-3 gap-8 mb-8">
            {/* Brand */}
            <div>
              <span className="font-pixel text-[9px] text-[var(--primary)] text-glow">OCCP</span>
              <p className="text-[var(--text-muted)] text-xs mt-2 leading-relaxed">
                OpenCloud Control Plane v0.8.0. Open-source AI agent governance with verified autonomy.
              </p>
            </div>

            {/* Product */}
            <div>
              <div className="font-pixel text-[7px] text-[var(--text-muted)] uppercase tracking-wider mb-3">
                Product
              </div>
              <div className="space-y-2">
                <Link href="/docs#overview" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  Documentation
                </Link>
                <Link href="/docs#api" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  API Reference
                </Link>
                <a
                  href="https://github.com/azar-management-consulting/occp-core"
                  target="_blank"
                  rel="noopener"
                  className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
                >
                  GitHub
                </a>
                <Link href="/login" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  Dashboard
                </Link>
              </div>
            </div>

            {/* Legal */}
            <div>
              <div className="font-pixel text-[7px] text-[var(--text-muted)] uppercase tracking-wider mb-3">
                Legal
              </div>
              <div className="space-y-2">
                <Link href="/docs/privacy" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  Privacy Policy
                </Link>
                <Link href="/docs/terms" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  Terms of Service
                </Link>
                <Link href="/docs/security" className="block text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
                  Security Policy
                </Link>
                <span className="block text-xs text-[var(--text-muted)]">MIT License</span>
              </div>
            </div>
          </div>

          <div className="border-t border-[var(--muted)]/20 pt-6 text-center">
            <div className="font-mono text-[10px] text-[var(--text-muted)]/40">
              **** AZAR MANAGEMENT CONSULTING ****
            </div>
            <div className="font-mono text-[10px] text-[var(--text-muted)]/30 mt-1">
              READY.
              <span className="inline-block w-2 h-4 bg-[var(--primary)] ml-1 animate-blink" />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
