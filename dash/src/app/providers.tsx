"use client";

import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth-guard";
import { Nav } from "@/components/nav";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGuard>
        <Nav />
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </AuthGuard>
    </AuthProvider>
  );
}
