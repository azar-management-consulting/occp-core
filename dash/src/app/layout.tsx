import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OCCP – Mission Control",
  description: "OpenCloud Control Plane Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
