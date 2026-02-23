"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "CONTROL" },
  { href: "/pipeline", label: "PIPELINE" },
  { href: "/agents", label: "AGENTS" },
  { href: "/policy", label: "POLICY" },
  { href: "/audit", label: "AUDIT" },
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
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded text-xs font-mono tracking-wide transition-all duration-200 ${
                  pathname === href
                    ? "bg-occp-primary/15 text-occp-primary text-glow border border-occp-primary/30"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5"
                }`}
              >
                {pathname === href && (
                  <span className="text-occp-accent mr-1">&gt;</span>
                )}
                {label}
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
