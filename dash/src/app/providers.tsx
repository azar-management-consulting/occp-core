"use client";

import { usePathname } from "next/navigation";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/lib/auth";
import { I18nProvider } from "@/lib/i18n";
import { AuthGuard } from "@/components/auth-guard";
import { Nav } from "@/components/nav";
import { CommandPalette } from "@/components/command-palette";
import { BrianDrawer } from "@/components/brian-drawer";
import { OnboardingProvider } from "@/components/onboarding/onboarding-provider";
import { TourEngine } from "@/components/onboarding/tour-engine";

const STANDALONE_ROUTES = ["/docs"];

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = STANDALONE_ROUTES.some((r) => pathname.startsWith(r));

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <I18nProvider>
        <AuthProvider>
          <AuthGuard>
            {isStandalone ? (
              <>{children}</>
            ) : (
              <OnboardingProvider>
                <Nav />
                <main className="max-w-7xl mx-auto px-6 py-10">{children}</main>
                <CommandPalette />
                <BrianDrawer />
                <TourEngine />
              </OnboardingProvider>
            )}
          </AuthGuard>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
