"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "CONTROL", desc: "Mission overview" },
  { href: "/pipeline", label: "PIPELINE", desc: "Run VAP tasks" },
  { href: "/agents", label: "AGENTS", desc: "Agent registry" },
  { href: "/policy", label: "POLICY", desc: "Guard evaluation" },
  { href: "/audit", label: "AUDIT", desc: "Immutable log" },
];

export function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();

  if (pathname === "/login") return null;

  return (
    <nav className="border-b border-occp-muted/40 bg-occp-surface/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center h-14 gap-6">
        <Link href="/" className="flex items-center gap-2.5 group">
          <Image src="/logo.png" alt="OCCP" width={26} height={26} className="rounded" />
          <span className="font-pixel text-[10px] text-occp-primary text-glow tracking-wider">
            OCCP
          </span>
        </Link>

        {isAuthenticated && (
          <div className="flex gap-0.5">
            {links.map(({ href, label, desc }) => (
              <Link
                key={href}
                href={href}
                title={desc}
                className={`group relative px-3 py-1.5 rounded text-xs font-mono tracking-wide transition-all duration-200 ${
                  pathname === href
                    ? "bg-occp-primary/15 text-occp-primary text-glow border border-occp-primary/30"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5"
                }`}
              >
                {pathname === href && (
                  <span className="text-occp-accent mr-1">&gt;</span>
                )}
                {label}
                <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 px-2 py-1 rounded bg-occp-dark border border-[var(--muted)] text-[9px] text-[var(--text-muted)] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  {desc}
                </span>
              </Link>
            ))}
          </div>
        )}

        <div className="ml-auto flex items-center gap-4 text-xs font-mono">
          <span className="text-occp-accent/60">[v0.6.0]</span>
          {isAuthenticated && (
            <div className="flex items-center gap-3">
              <span className="text-[var(--text-muted)]">
                <span className="text-occp-success">&#9679;</span> {user}
              </span>
              <button
                onClick={logout}
                className="text-[var(--text-muted)] hover:text-occp-danger transition-colors"
              >
                LOGOUT
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
