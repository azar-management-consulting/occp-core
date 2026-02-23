"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { AuthGuard } from "@/components/auth-guard";
import { Nav } from "@/components/nav";

const STANDALONE_ROUTES = ["/docs"];

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = STANDALONE_ROUTES.some((r) => pathname.startsWith(r));

  return (
    <I18nProvider>
      <AuthProvider>
        <AuthGuard>
          {isStandalone ? (
            <>{children}</>
          ) : (
            <>
              <Nav />
              <main className="max-w-7xl mx-auto px-6 py-10">{children}</main>
            </>
          )}
        </AuthGuard>
      </AuthProvider>
    </I18nProvider>
  );
}
