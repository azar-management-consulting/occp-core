"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import type { ReactNode } from "react";

/**
 * Wraps admin-only pages. Redirects non-admin users to "/".
 * Admin = system_admin or org_admin (matches RBAC hierarchy).
 */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!isAuthenticated || !isAdmin)) {
      router.replace("/");
    }
  }, [loading, isAuthenticated, isAdmin, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <span className="font-pixel text-[11px] text-[var(--text-muted)] animate-pulse">
          CHECKING ACCESS...
        </span>
      </div>
    );
  }

  if (!isAuthenticated || !isAdmin) return null;

  return <>{children}</>;
}
