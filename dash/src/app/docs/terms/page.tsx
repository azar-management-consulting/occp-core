"use client";

import Link from "next/link";

export default function TermsPage() {
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
              / Terms of Service
            </span>
          </div>
          <Link href="/docs" className="font-pixel text-[7px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
            BACK TO DOCS
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="retro-card p-8 md:p-12">
          <h1 className="font-pixel text-[12px] sm:text-[14px] text-[var(--primary)] text-glow uppercase tracking-wider mb-2">
            Terms of Service
          </h1>
          <p className="text-[var(--text-muted)] text-xs mb-8">
            Last updated: February 23, 2026 &mdash; Effective immediately
          </p>

          <div className="space-y-8 text-sm text-[var(--text-muted)] leading-relaxed">
            {/* 1 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                1. Acceptance of Terms
              </h2>
              <p>
                By accessing or using the OCCP platform (OpenCloud Control Plane), including the API at api.occp.ai, the dashboard at dash.occp.ai, and associated SDKs and tools, you agree to be bound by these Terms of Service. If you do not agree, do not use the platform.
              </p>
            </section>

            {/* 2 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                2. Service Description
              </h2>
              <p className="mb-3">
                OCCP is an open-source AI agent control plane that provides:
              </p>
              <ul className="space-y-1 text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span>Verified Autonomy Pipeline (VAP) for gated AI agent execution</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span>Policy engine with configurable risk thresholds and built-in guards</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span>Tamper-evident audit logging with cryptographic hash chain</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span>Agent registry and lifecycle management</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--primary)] mt-0.5">&#x25B8;</span>
                  <span>REST API, Python SDK, TypeScript SDK, and CLI</span>
                </li>
              </ul>
            </section>

            {/* 3 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                3. Open Source License
              </h2>
              <p>
                The OCCP core platform is released under the MIT License. You may use, modify, and distribute the software in accordance with the license terms. The hosted service at occp.ai may have additional terms and service-level agreements.
              </p>
            </section>

            {/* 4 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                4. User Responsibilities
              </h2>
              <p className="mb-3">You agree to:</p>
              <ul className="space-y-1 text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-occp-warning mt-0.5">&#x25B8;</span>
                  <span>Use the platform in compliance with applicable laws and regulations</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-warning mt-0.5">&#x25B8;</span>
                  <span>Maintain the security of your authentication credentials</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-warning mt-0.5">&#x25B8;</span>
                  <span>Not attempt to circumvent the policy engine or audit controls</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-warning mt-0.5">&#x25B8;</span>
                  <span>Not use the platform for malicious AI agent deployment</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-warning mt-0.5">&#x25B8;</span>
                  <span>Ensure your AI agents comply with ethical AI guidelines</span>
                </li>
              </ul>
            </section>

            {/* 5 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                5. API Usage & Rate Limits
              </h2>
              <p>
                The hosted API service may enforce rate limits to ensure fair usage. Current limits are documented in the API reference. Excessive automated usage that degrades service for others may result in temporary access restrictions.
              </p>
            </section>

            {/* 6 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                6. Intellectual Property
              </h2>
              <p>
                The OCCP name, logo, and branding are trademarks of Azar Management Consulting. The open-source codebase is licensed under MIT, but the hosted service, documentation design, and brand assets remain proprietary.
              </p>
            </section>

            {/* 7 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                7. Disclaimer of Warranties
              </h2>
              <p>
                THE PLATFORM IS PROVIDED &ldquo;AS IS&rdquo; WITHOUT WARRANTY OF ANY KIND. WE DO NOT GUARANTEE THAT AI AGENTS GOVERNED BY OCCP WILL BEHAVE AS EXPECTED IN ALL SCENARIOS. THE POLICY ENGINE PROVIDES RISK MITIGATION, NOT ABSOLUTE SAFETY GUARANTEES.
              </p>
            </section>

            {/* 8 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                8. Limitation of Liability
              </h2>
              <p>
                To the maximum extent permitted by law, Azar Management Consulting shall not be liable for any indirect, incidental, special, or consequential damages arising from the use of OCCP, including damages caused by AI agent actions, even if gated by the policy engine.
              </p>
            </section>

            {/* 9 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                9. Governing Law
              </h2>
              <p>
                These terms shall be governed by and construed in accordance with the laws of Hungary and the European Union. Any disputes shall be submitted to the competent courts of Budapest, Hungary.
              </p>
            </section>

            {/* 10 */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                10. Contact
              </h2>
              <p>
                For questions about these terms, contact us at{" "}
                <span className="text-occp-accent">legal@occp.ai</span>.
              </p>
            </section>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-muted)]">
            <Link href="/docs" className="hover:text-[var(--text)] transition-colors">Docs</Link>
            <Link href="/docs/privacy" className="hover:text-[var(--text)] transition-colors">Privacy</Link>
            <Link href="/docs/security" className="hover:text-[var(--text)] transition-colors">Security</Link>
          </div>
          <div className="font-mono text-[10px] text-[var(--text-muted)]/30 mt-4">
            **** AZAR MANAGEMENT CONSULTING ****
          </div>
        </div>
      </div>
    </div>
  );
}
