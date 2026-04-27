"use client";

/**
 * Top navigation — Linear/Vercel-grade modernization.
 *
 * Layout: sticky 56px bar with logo + wordmark left, link row centre,
 *         language selector + user menu right.
 *
 * Active link: pathname === href OR pathname.startsWith(href + "/").
 *              Highlighted with brand-green underline (oklch(0.72 0.18 145)).
 *
 * Mobile: link row gets overflow-x-auto, no horizontal page scroll.
 *
 * a11y: <nav aria-label="Primary">; active link has aria-current="page".
 *
 * Hidden on /login and /register (returns null).
 */

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { LanguageSelector } from "@/components/language-selector";
import { UserMenu } from "@/components/user-menu";
import { cn } from "@/lib/utils";

interface NavLink {
  href: string;
  label: string;
  desc: string;
}

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, isAdmin } = useAuth();
  const t = useT();

  if (pathname === "/login" || pathname === "/register") return null;

  const links: NavLink[] = [
    { href: "/", label: t.nav.control, desc: t.nav.controlDesc },
    { href: "/pipeline", label: t.nav.pipeline, desc: t.nav.pipelineDesc },
    { href: "/agents", label: t.nav.agents, desc: t.nav.agentsDesc },
    { href: "/policy", label: t.nav.policy, desc: t.nav.policyDesc },
    { href: "/audit", label: t.nav.audit, desc: t.nav.auditDesc },
    { href: "/mcp", label: t.nav.mcp, desc: t.nav.mcpDesc },
    { href: "/skills", label: t.nav.skills, desc: t.nav.skillsDesc },
    { href: "/settings", label: t.nav.settings, desc: t.nav.settingsDesc },
    ...(isAdmin
      ? [{ href: "/admin", label: t.nav.admin, desc: t.nav.adminDesc }]
      : []),
  ];

  return (
    <header
      className={cn(
        "sticky top-0 z-30 w-full",
        "bg-[var(--bg)]/85 backdrop-blur-md",
        "border-b border-[var(--border-subtle,#52525b)]/40",
      )}
    >
      <div className="max-w-7xl mx-auto h-14 px-6 flex items-center gap-6">
        {/* Logo + wordmark */}
        <Link
          href="/"
          className="flex items-center gap-2 shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)] rounded-md"
        >
          <Image
            src="/logo.png"
            alt="OCCP"
            width={28}
            height={28}
            className="rounded"
            priority
          />
          <span className="text-base font-semibold tracking-tight text-[var(--fg,#fafafa)]">
            OCCP
          </span>
        </Link>

        {/* Primary nav links */}
        {isAuthenticated && (
          <nav
            aria-label="Primary"
            className={cn(
              "flex items-center gap-5 min-w-0 flex-1",
              // mobile: allow horizontal scroll without bleeding into page
              "overflow-x-auto md:overflow-visible",
              "[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
            )}
          >
            {links.map(({ href, label, desc }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  title={desc}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative shrink-0 py-4 text-sm font-medium tracking-tight transition-colors outline-none",
                    "focus-visible:text-[var(--fg,#fafafa)]",
                    active
                      ? "text-[var(--fg,#fafafa)]"
                      : "text-[var(--fg-muted,#a1a1aa)] hover:text-[var(--fg,#fafafa)]",
                  )}
                >
                  {label}
                  {active && (
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute left-0 right-0 -bottom-px h-px"
                      style={{ background: "oklch(0.72 0.18 145)" }}
                    />
                  )}
                </Link>
              );
            })}
          </nav>
        )}

        {/* Right slot */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <LanguageSelector />
          {isAuthenticated && <UserMenu />}
        </div>
      </div>
    </header>
  );
}
