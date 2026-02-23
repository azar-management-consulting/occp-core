"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth-guard";
import { Nav } from "@/components/nav";

const STANDALONE_ROUTES = ["/docs"];

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = STANDALONE_ROUTES.some((r) => pathname.startsWith(r));

  return (
    <AuthProvider>
      <AuthGuard>
        {isStandalone ? (
          <>{children}</>
        ) : (
          <>
            <Nav />
            <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
          </>
        )}
      </AuthGuard>
    </AuthProvider>
  );
}
