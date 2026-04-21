import type { Viewport } from "next";
import "./globals.css";

/**
 * Root layout — intentionally minimal.
 *
 * The real <html> / <body> and NextIntlClientProvider live in
 * `src/app/[locale]/layout.tsx`. This root layout just defines viewport
 * defaults and re-exports children so Next 15's App Router has a root node.
 *
 * Note: per Next 15 docs, this root layout is still REQUIRED even when all
 * real content lives under a `[locale]` segment.
 */
export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
