"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "Mission Control" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/agents", label: "Agents" },
  { href: "/policy", label: "Policy" },
  { href: "/audit", label: "Audit" },
];

export function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();

  // Hide nav on login page
  if (pathname === "/login") return null;

  return (
    <nav className="border-b border-occp-muted/50 bg-occp-surface/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center h-14 gap-8">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight">
          <Image src="/logo.png" alt="OCCP" width={28} height={28} className="rounded-md" />
          <span className="text-occp-primary">OCCP</span>
        </Link>

        {isAuthenticated && (
          <div className="flex gap-1">
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  pathname === href
                    ? "bg-occp-primary/15 text-occp-primary font-medium"
                    : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5"
                }`}
              >
                {label}
              </Link>
            ))}
          </div>
        )}

        <div className="ml-auto flex items-center gap-4">
          <span className="text-xs text-[var(--text-muted)]">v0.5.0</span>
          {isAuthenticated && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-[var(--text-muted)]">{user}</span>
              <button
                onClick={logout}
                className="text-xs text-[var(--text-muted)] hover:text-occp-danger transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
