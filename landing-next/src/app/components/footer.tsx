import Link from "next/link";
import { useTranslations } from "next-intl";

type ColumnKey = "product" | "resources" | "company" | "legal";

const NAV: ReadonlyArray<{
  key: ColumnKey;
  links: ReadonlyArray<{ key: string; href: string }>;
}> = [
  {
    key: "product",
    links: [
      { key: "features", href: "/features" },
      { key: "pricing", href: "/pricing" },
      { key: "changelog", href: "/changelog" },
      { key: "roadmap", href: "/roadmap" },
    ],
  },
  {
    key: "resources",
    links: [
      { key: "docs", href: "https://docs.occp.ai" },
      { key: "api", href: "https://docs.occp.ai/api" },
      { key: "templates", href: "https://docs.occp.ai/templates" },
      { key: "blog", href: "/blog" },
    ],
  },
  {
    key: "company",
    links: [
      { key: "about", href: "/about" },
      { key: "security", href: "/security" },
      { key: "careers", href: "/careers" },
      { key: "contact", href: "mailto:hello@occp.ai" },
    ],
  },
  {
    key: "legal",
    links: [
      { key: "terms", href: "/legal/terms" },
      { key: "privacy", href: "/legal/privacy" },
      { key: "sla", href: "/legal/sla" },
      { key: "aup", href: "/legal/aup" },
    ],
  },
] as const;

export function Footer() {
  const t = useTranslations("footer");

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
        <p className="text-center text-xs text-fg-muted">{t("trust")}</p>
      </div>

      {/* Main nav grid */}
      <div className="mx-auto max-w-6xl px-4 py-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {NAV.map((col) => (
            <div key={col.key}>
              <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-fg-muted">
                {t(`columns.${col.key}.heading`)}
              </p>
              <ul role="list" className="flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <li key={link.key}>
                    <Link
                      href={link.href}
                      className="text-sm text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                    >
                      {t(`columns.${col.key}.${link.key}`)}
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
            {t("copyright")}&nbsp;·&nbsp;{t("madeIn")}{" "}
            <span aria-label={t("euFlagLabel")}>🇪🇺</span>
          </p>

          <div className="flex items-center gap-4">
            <Link
              href="https://github.com/azar-management-consulting/occp-core"
              className="text-xs text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("githubAria")}
            >
              GitHub
            </Link>
            <Link
              href="https://linkedin.com/company/azar-mc"
              className="text-xs text-fg-muted transition-colors hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("linkedinAria")}
            >
              LinkedIn
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
