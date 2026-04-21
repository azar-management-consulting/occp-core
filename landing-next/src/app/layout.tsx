import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { StructuredData } from "./components/structured-data";

const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Azar Management Consulting",
  url: "https://occp.ai",
  logo: "https://occp.ai/logo.png",
  sameAs: [
    "https://github.com/azar-management-consulting",
    "https://linkedin.com/company/azar-mc",
  ],
};

const softwareApplicationSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "OCCP — OpenCloud Control Plane",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Any",
  offers: {
    "@type": "Offer",
    price: 0,
    priceCurrency: "USD",
    availability: "https://schema.org/InStock",
  },
  aggregateRating: {
    "@type": "AggregateRating",
    ratingValue: 4.9,
    reviewCount: 1,
  },
};

const webSiteSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  url: "https://occp.ai",
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: "https://docs.occp.ai/?q={search_term_string}",
    },
    "query-input": "required name=search_term_string",
  },
};

export const metadata: Metadata = {
  metadataBase: new URL("https://occp.ai"),
  title: "OCCP — OpenCloud Control Plane | Agent Governance Platform",
  description:
    "OCCP is the Verified Autonomy Pipeline for AI agents. Every autonomous action verified before execution. Policy-enforced, audit-logged, enterprise-ready governance for LLM-powered systems.",
  keywords: [
    "AI agent governance",
    "control plane",
    "LLM policy engine",
    "verified autonomy pipeline",
    "enterprise AI",
    "OCCP",
  ],
  authors: [{ name: "Azar Management Consulting" }],
  alternates: { canonical: "https://occp.ai/" },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  applicationName: "OCCP",
  category: "technology",
  openGraph: {
    type: "website",
    url: "https://occp.ai/",
    siteName: "OCCP",
    title: "OCCP — OpenCloud Control Plane | Agent Governance Platform",
    description:
      "Every autonomous action verified before execution. Policy-enforced, audit-logged, enterprise-ready. The control plane that governs AI agents.",
    images: [{ url: "https://occp.ai/og-image.png", width: 1200, height: 630, alt: "OCCP" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "OCCP — OpenCloud Control Plane",
    description:
      "Every autonomous action verified before execution. Policy-enforced, audit-logged, enterprise-ready.",
    images: ["https://occp.ai/og-image.png"],
  },
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%230a0a0a'/><text x='2' y='24' font-family='monospace' font-size='20' fill='%2333ff33'>&#62;_</text></svg>",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <head>
        <link rel="preconnect" href="https://api.occp.ai" />
        <StructuredData data={organizationSchema} />
        <StructuredData data={softwareApplicationSchema} />
        <StructuredData data={webSiteSchema} />
      </head>
      <body>{children}</body>
    </html>
  );
}
