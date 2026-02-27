"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { LanguageSelector } from "@/components/language-selector";

export function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();
  const t = useT();

  const links = [
    { href: "/", label: t.nav.control, desc: t.nav.controlDesc },
    { href: "/pipeline", label: t.nav.pipeline, desc: t.nav.pipelineDesc },
    { href: "/agents", label: t.nav.agents, desc: t.nav.agentsDesc },
    { href: "/policy", label: t.nav.policy, desc: t.nav.policyDesc },
    { href: "/audit", label: t.nav.audit, desc: t.nav.auditDesc },
    { href: "/mcp", label: t.nav.mcp, desc: t.nav.mcpDesc },
    { href: "/skills", label: t.nav.skills, desc: t.nav.skillsDesc },
    { href: "/settings", label: t.nav.settings, desc: t.nav.settingsDesc },
  ];

  if (pathname === "/login") return null;

  return (
    <nav className="border-b border-occp-muted/40 bg-occp-surface/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center h-16 gap-6">
        <Link href="/" className="flex items-center gap-2.5 group">
          <Image src="/logo.png" alt="OCCP" width={28} height={28} className="rounded" />
          <span className="font-pixel text-[13px] text-occp-primary text-glow tracking-wider">
            OCCP
          </span>
        </Link>

        {isAuthenticated && (
          <div className="flex gap-1">
            {links.map(({ href, label, desc }) => (
              <Link
                key={href}
                href={href}
                title={desc}
                className={`group relative px-3.5 py-2 rounded text-sm font-mono tracking-wide transition-all duration-200 ${
                  pathname === href
                    ? "bg-occp-primary/15 text-occp-primary text-glow border border-occp-primary/30"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5"
                }`}
              >
                {pathname === href && (
                  <span className="text-occp-accent mr-1">&gt;</span>
                )}
                {label}
                <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 px-2.5 py-1.5 rounded bg-occp-dark border border-[var(--muted)] text-[11px] text-[var(--text-muted)] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  {desc}
                </span>
              </Link>
            ))}
          </div>
        )}

        <div className="ml-auto flex items-center gap-4 text-sm font-mono">
          <LanguageSelector />
          <span className="text-occp-accent/60">[v0.8.2]</span>
          {isAuthenticated && (
            <div className="flex items-center gap-3">
              <span className="text-[var(--text-muted)]">
                <span className="text-occp-success">&#9679;</span> {user}
              </span>
              <button
                onClick={logout}
                className="text-[var(--text-muted)] hover:text-occp-danger transition-colors"
              >
                {t.nav.logout}
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
