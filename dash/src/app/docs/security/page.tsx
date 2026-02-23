"use client";

import Link from "next/link";

export default function SecurityPage() {
  return (
    <div className="min-h-screen">
      {/* ── NAV ──────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-[var(--muted)]/50 backdrop-blur-md bg-[var(--bg)]/80">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/docs" className="font-pixel text-[9px] text-[var(--primary)] text-glow tracking-wider">
              OCCP
            </Link>
            <span className="font-pixel text-[7px] text-[var(--text-muted)] uppercase tracking-wider">
              / Security
            </span>
          </div>
          <Link href="/docs" className="font-pixel text-[7px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
            BACK TO DOCS
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="retro-card p-8 md:p-12">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-3 h-3 rounded-full bg-occp-success animate-pulse" />
            <span className="font-pixel text-[7px] text-occp-success uppercase tracking-widest">
              Hardened
            </span>
          </div>
          <h1 className="font-pixel text-[12px] sm:text-[14px] text-[var(--primary)] text-glow uppercase tracking-wider mb-2">
            Security Policy
          </h1>
          <p className="text-[var(--text-muted)] text-xs mb-8">
            OCCP security model, vulnerability reporting, and hardening measures.
          </p>

          <div className="space-y-8 text-sm text-[var(--text-muted)] leading-relaxed">
            {/* Security Model */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                1. Security Model
              </h2>
              <p className="mb-4">
                OCCP implements a defense-in-depth security model where every layer provides independent protection. The Verified Autonomy Pipeline (VAP) ensures no AI agent action executes without passing through multiple security gates.
              </p>

              <div className="grid sm:grid-cols-2 gap-3">
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-[var(--primary)] mb-2 uppercase tracking-wider">
                    PII Guard
                  </div>
                  <p className="text-xs">
                    Regex-based detection of personally identifiable information (emails, phone numbers, SSNs, credit cards) in agent inputs and outputs. Blocks PII leakage before it reaches the LLM.
                  </p>
                </div>
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-occp-warning mb-2 uppercase tracking-wider">
                    Prompt Injection Guard
                  </div>
                  <p className="text-xs">
                    Pattern-matching detection of common prompt injection techniques including system prompt override attempts, role manipulation, and instruction bypass patterns.
                  </p>
                </div>
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-occp-accent mb-2 uppercase tracking-wider">
                    Resource Limit Guard
                  </div>
                  <p className="text-xs">
                    Prevents resource exhaustion by enforcing limits on task payload sizes, execution timeouts, and concurrent operations.
                  </p>
                </div>
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-occp-success mb-2 uppercase tracking-wider">
                    Audit Hash Chain
                  </div>
                  <p className="text-xs">
                    Every action is recorded in a tamper-evident SHA-256 hash chain. Each entry links to the previous via cryptographic hash, making retroactive modification detectable.
                  </p>
                </div>
              </div>
            </section>

            {/* Infrastructure Hardening */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                2. Infrastructure Hardening
              </h2>
              <div className="retro-card p-5 font-mono text-xs overflow-x-auto">
                <div className="space-y-2">
                  {[
                    { check: "Non-root container", value: "uid=1001(occp)", status: "PASS" },
                    { check: "Read-only rootfs", value: "true (API + Dash)", status: "PASS" },
                    { check: "No-new-privileges", value: "security_opt enabled", status: "PASS" },
                    { check: "Port binding", value: "127.0.0.1 only", status: "PASS" },
                    { check: "Temp filesystem", value: "tmpfs /tmp", status: "PASS" },
                    { check: "TLS termination", value: "Caddy reverse proxy", status: "PASS" },
                    { check: "Branch protection", value: "enforce_admins: true", status: "PASS" },
                    { check: "CI gates", value: "5 required checks", status: "PASS" },
                  ].map((item) => (
                    <div key={item.check} className="flex items-center gap-4">
                      <span className="text-occp-success w-10">[{item.status}]</span>
                      <span className="text-[var(--text)] w-40">{item.check}</span>
                      <span className="text-[var(--text-muted)]">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Authentication */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                3. Authentication & Authorization
              </h2>
              <ul className="space-y-2 text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">JWT tokens</strong> with HMAC-SHA256 signing (minimum 32-byte keys per RFC 7518)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">Token expiry</strong> enforced with configurable TTL</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">CORS policy</strong> restricted to configured origins</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">Security headers</strong>: X-Content-Type-Options: nosniff, X-Frame-Options: SAMEORIGIN</span>
                </li>
              </ul>
            </section>

            {/* Responsible Disclosure */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-danger uppercase tracking-wider mb-3">
                4. Vulnerability Reporting
              </h2>
              <div className="retro-card p-5 border-[var(--danger)]/30">
                <p className="mb-4">
                  If you discover a security vulnerability in OCCP, we ask that you disclose it responsibly.
                </p>
                <div className="space-y-3 text-xs">
                  <div className="flex items-start gap-3">
                    <span className="font-pixel text-[8px] text-occp-danger w-16">EMAIL</span>
                    <span className="text-occp-accent">security@occp.ai</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="font-pixel text-[8px] text-occp-danger w-16">SCOPE</span>
                    <span>API endpoints, authentication, policy bypass, audit chain tampering, dependency vulnerabilities</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="font-pixel text-[8px] text-occp-danger w-16">SLA</span>
                    <span>Acknowledgment within 48 hours, fix timeline within 7 days for critical issues</span>
                  </div>
                </div>
                <div className="mt-4 p-3 bg-[var(--danger)]/5 rounded border border-[var(--danger)]/20">
                  <p className="text-xs text-[var(--text)]">
                    Please do NOT open public GitHub issues for security vulnerabilities. Use the email above for responsible disclosure.
                  </p>
                </div>
              </div>
            </section>

            {/* Dependency Security */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                5. Dependency Security
              </h2>
              <p className="mb-3">
                OCCP uses GitHub&apos;s automated security scanning:
              </p>
              <ul className="space-y-1 text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">Dependabot</strong> monitors Python (pip) and Node.js (npm) dependencies</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">Secret scanning</strong> prevents credential leaks in commits</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span><strong className="text-[var(--text)]">Branch protection</strong> requires CI pass + admin enforcement</span>
                </li>
              </ul>
            </section>

            {/* Data Handling */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                6. AI Data Handling
              </h2>
              <p>
                When using Anthropic Claude as the AI engine, task data is sent to Anthropic&apos;s API for inference. Anthropic&apos;s data retention policies apply. OCCP&apos;s PII Guard runs <strong className="text-[var(--text)]">before</strong> data reaches the LLM, providing a pre-filtering layer. For maximum data sovereignty, self-hosted LLM backends can be configured.
              </p>
            </section>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-muted)]">
            <Link href="/docs" className="hover:text-[var(--text)] transition-colors">Docs</Link>
            <Link href="/docs/privacy" className="hover:text-[var(--text)] transition-colors">Privacy</Link>
            <Link href="/docs/terms" className="hover:text-[var(--text)] transition-colors">Terms</Link>
          </div>
          <div className="font-mono text-[10px] text-[var(--text-muted)]/30 mt-4">
            **** AZAR MANAGEMENT CONSULTING ****
          </div>
        </div>
      </div>
    </div>
  );
}
