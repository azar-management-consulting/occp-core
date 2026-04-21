import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://dash.occp.ai"),
  title: "OCCP – Mission Control",
  description: "OpenCloud Control Plane Dashboard",
  icons: {
    icon: [
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "OCCP – Agent Control Plane",
    description: "Verified Autonomy Pipeline for AI agents",
    images: [{ url: "/logo.png", width: 1000, height: 1000, alt: "OCCP Logo" }],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${GeistSans.variable} ${GeistMono.variable} min-h-screen antialiased bg-[var(--bg)] text-[var(--text)] font-mono scanlines retro-grid`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
