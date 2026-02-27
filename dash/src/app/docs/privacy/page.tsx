"use client";

import Link from "next/link";

export default function PrivacyPage() {
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
              / Privacy Policy
            </span>
          </div>
          <Link href="/docs" className="font-pixel text-[7px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors">
            BACK TO DOCS
          </Link>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="retro-card p-8 md:p-12">
          {/* Header */}
          <div className="flex items-center gap-3 mb-2">
            <div className="w-3 h-3 rounded-full bg-occp-success animate-pulse" />
            <span className="font-pixel text-[7px] text-occp-success uppercase tracking-widest">
              GDPR Aligned
            </span>
          </div>
          <h1 className="font-pixel text-[12px] sm:text-[14px] text-[var(--primary)] text-glow uppercase tracking-wider mb-2">
            Privacy Policy
          </h1>
          <p className="text-[var(--text-muted)] text-xs mb-8">
            Last updated: February 23, 2026 &mdash; Effective immediately
          </p>

          <div className="space-y-8 text-sm text-[var(--text-muted)] leading-relaxed">
            {/* 1. Controller */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                1. Data Controller
              </h2>
              <p>
                <strong className="text-[var(--text)]">Azar Management Consulting</strong> (&ldquo;we&rdquo;, &ldquo;us&rdquo;) is the data controller for personal data processed through the OCCP platform (OpenCloud Control Plane).
              </p>
              <div className="retro-card p-4 mt-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <span className="text-[var(--text-muted)]">Entity:</span>
                  <span className="text-[var(--text)]">Azar Management Consulting</span>
                  <span className="text-[var(--text-muted)]">Email:</span>
                  <span className="text-occp-accent">privacy@occp.ai</span>
                  <span className="text-[var(--text-muted)]">Website:</span>
                  <span className="text-occp-accent">https://occp.ai</span>
                </div>
              </div>
            </section>

            {/* 2. Data We Collect */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                2. Data We Collect
              </h2>
              <p className="mb-3">We process the following categories of personal data:</p>
              <div className="space-y-3">
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-[var(--primary)] mb-2 uppercase tracking-wider">
                    Account Data
                  </div>
                  <p className="text-xs">Username, email address, and hashed authentication credentials required for platform access.</p>
                </div>
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-occp-warning mb-2 uppercase tracking-wider">
                    Usage & Audit Data
                  </div>
                  <p className="text-xs">API requests, pipeline execution logs, audit trail entries, and agent interaction records. These are stored in our tamper-evident hash chain for security and compliance.</p>
                </div>
                <div className="retro-card p-4">
                  <div className="font-pixel text-[7px] text-occp-success mb-2 uppercase tracking-wider">
                    Technical Data
                  </div>
                  <p className="text-xs">IP addresses, browser type, and session tokens for authentication and security monitoring purposes.</p>
                </div>
              </div>
            </section>

            {/* 3. Legal Basis */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                3. Legal Basis for Processing (GDPR Art. 6)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[var(--muted)]">
                      <th className="font-pixel text-[7px] text-left py-2 pr-4 text-[var(--primary)] uppercase tracking-wider">Purpose</th>
                      <th className="font-pixel text-[7px] text-left py-2 text-[var(--primary)] uppercase tracking-wider">Legal Basis</th>
                    </tr>
                  </thead>
                  <tbody className="text-[var(--text-muted)]">
                    <tr className="border-b border-[var(--muted)]/30">
                      <td className="py-2 pr-4">Platform access & authentication</td>
                      <td className="py-2">Contract performance (Art. 6(1)(b))</td>
                    </tr>
                    <tr className="border-b border-[var(--muted)]/30">
                      <td className="py-2 pr-4">Security monitoring & audit logs</td>
                      <td className="py-2">Legitimate interest (Art. 6(1)(f))</td>
                    </tr>
                    <tr className="border-b border-[var(--muted)]/30">
                      <td className="py-2 pr-4">Service improvement & analytics</td>
                      <td className="py-2">Legitimate interest (Art. 6(1)(f))</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4">Marketing communications</td>
                      <td className="py-2">Consent (Art. 6(1)(a))</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            {/* 4. Data Retention */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                4. Data Retention
              </h2>
              <p>
                Audit log entries are retained for the lifetime of the platform instance for security and compliance purposes. Account data is retained for the duration of the service agreement plus 30 days. Technical logs are automatically purged after 90 days.
              </p>
            </section>

            {/* 5. Data Storage */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                5. Data Storage & Security
              </h2>
              <p className="mb-3">
                All data is stored on Hetzner Cloud infrastructure located in the European Union (Germany). We implement the following security measures:
              </p>
              <ul className="space-y-1 text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span>TLS 1.3 encryption for all data in transit</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span>SHA-256 hash chain for audit log integrity</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span>Non-root Docker containers with read-only filesystems</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span>JWT-based authentication with HMAC-SHA256 signing</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-occp-success mt-0.5">&#x25B8;</span>
                  <span>PII detection guard preventing sensitive data leakage</span>
                </li>
              </ul>
            </section>

            {/* 6. Your Rights */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                6. Your Rights (GDPR Art. 15-22)
              </h2>
              <p className="mb-3">Under the General Data Protection Regulation, you have the right to:</p>
              <div className="grid sm:grid-cols-2 gap-3">
                {[
                  { title: "Access", desc: "Request a copy of your personal data" },
                  { title: "Rectification", desc: "Correct inaccurate personal data" },
                  { title: "Erasure", desc: "Request deletion of your data" },
                  { title: "Portability", desc: "Receive your data in a structured format" },
                  { title: "Restriction", desc: "Restrict processing of your data" },
                  { title: "Objection", desc: "Object to data processing" },
                ].map((r) => (
                  <div key={r.title} className="retro-card p-3">
                    <div className="font-pixel text-[7px] text-[var(--primary)] mb-1 uppercase tracking-wider">
                      {r.title}
                    </div>
                    <p className="text-[10px] text-[var(--text-muted)]">{r.desc}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs">
                To exercise any of these rights, contact us at{" "}
                <span className="text-occp-accent">privacy@occp.ai</span>. We will respond within 30 days as required by GDPR.
              </p>
            </section>

            {/* 7. Sub-processors */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                7. Sub-processors (GDPR Art. 28)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[var(--muted)]">
                      <th className="font-pixel text-[7px] text-left py-2 pr-4 text-[var(--primary)] uppercase tracking-wider">Provider</th>
                      <th className="font-pixel text-[7px] text-left py-2 pr-4 text-[var(--primary)] uppercase tracking-wider">Purpose</th>
                      <th className="font-pixel text-[7px] text-left py-2 text-[var(--primary)] uppercase tracking-wider">Location</th>
                    </tr>
                  </thead>
                  <tbody className="text-[var(--text-muted)]">
                    <tr className="border-b border-[var(--muted)]/30">
                      <td className="py-2 pr-4 text-[var(--text)]">Hetzner Online GmbH</td>
                      <td className="py-2 pr-4">Infrastructure hosting</td>
                      <td className="py-2">Germany, EU</td>
                    </tr>
                    <tr className="border-b border-[var(--muted)]/30">
                      <td className="py-2 pr-4 text-[var(--text)]">Anthropic PBC</td>
                      <td className="py-2 pr-4">AI model inference (Claude)</td>
                      <td className="py-2">United States</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4 text-[var(--text)]">GitHub Inc.</td>
                      <td className="py-2 pr-4">Source code hosting, CI/CD</td>
                      <td className="py-2">United States</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs mt-3">
                For US-based sub-processors, appropriate safeguards (EU Standard Contractual Clauses) are in place.
              </p>
            </section>

            {/* 8. Cookies */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                8. Cookies
              </h2>
              <p>
                OCCP uses only strictly necessary cookies for authentication (JWT session tokens). We do not use tracking cookies, analytics cookies, or third-party advertising cookies. No cookie consent banner is required as we only use essential cookies per ePrivacy Directive Art. 5(3).
              </p>
            </section>

            {/* 9. Contact */}
            <section>
              <h2 className="font-pixel text-[8px] text-occp-accent uppercase tracking-wider mb-3">
                9. Contact & Supervisory Authority
              </h2>
              <p className="mb-3">
                For any privacy-related inquiries, contact{" "}
                <span className="text-occp-accent">privacy@occp.ai</span>.
              </p>
              <p>
                You have the right to lodge a complaint with a supervisory authority, in particular in the Member State of your habitual residence, place of work, or place of the alleged infringement (GDPR Art. 77).
              </p>
            </section>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-muted)]">
            <Link href="/docs" className="hover:text-[var(--text)] transition-colors">Docs</Link>
            <Link href="/docs/terms" className="hover:text-[var(--text)] transition-colors">Terms</Link>
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
