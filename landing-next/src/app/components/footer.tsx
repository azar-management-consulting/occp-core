import Link from "next/link";

const NAV = [
  {
    heading: "Product",
    links: [
      { label: "Features", href: "/features" },
      { label: "Pricing", href: "/pricing" },
      { label: "Changelog", href: "/changelog" },
      { label: "Roadmap", href: "/roadmap" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "Docs", href: "https://docs.occp.ai" },
      { label: "API Reference", href: "https://docs.occp.ai/api" },
      { label: "Templates", href: "https://docs.occp.ai/templates" },
      { label: "Blog", href: "/blog" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Security", href: "/security" },
      { label: "Careers", href: "/careers" },
      { label: "Contact", href: "mailto:hello@occp.ai" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { label: "Terms", href: "/legal/terms" },
      { label: "Privacy", href: "/legal/privacy" },
      { label: "SLA", href: "/legal/sla" },
      { label: "AUP", href: "/legal/aup" },
    ],
  },
] as const;

export function Footer() {
  return (
    <footer
      className="border-t"
      style={{ borderColor: "var(--color-border-subtle)" }}
      aria-label="Site footer"
    >
      {/* Trust bar */}
      <div
        className="border-b px-4 py-3"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <p className="text-center text-xs text-fg-muted">
          EU AI Act Art.&nbsp;14 ready&nbsp;·&nbsp;GDPR compliant&nbsp;·&nbsp;SOC2 (in progress)
        </p>
      </div>

      {/* Main nav grid */}
      <div className="mx-auto max-w-6xl px-4 py-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {NAV.map((col) => (
            <div key={col.heading}>
              <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-fg-muted">
                {col.heading}
              </p>
              <ul role="list" className="flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div
        className="border-t px-4 py-6"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <p className="text-xs text-fg-muted">
            © 2026 Azar Management Consulting&nbsp;·&nbsp;Made in EU{" "}
            <span aria-label="European Union flag">🇪🇺</span>
          </p>

          <div className="flex items-center gap-4">
            <Link
              href="https://github.com/azar-management-consulting/occp-core"
              className="text-xs text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="OCCP on GitHub"
            >
              GitHub
            </Link>
            <Link
              href="https://linkedin.com/company/azar-mc"
              className="text-xs text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Azar Management Consulting on LinkedIn"
            >
              LinkedIn
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
