import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing, locales, type Locale } from "@/i18n/routing";
import "../globals.css";
import { StructuredData } from "../components/structured-data";

const SITE_URL = "https://occp.ai";

function orgSchema(locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Azar Management Consulting",
    url: SITE_URL,
    logo: `${SITE_URL}/logo.png`,
    inLanguage: locale,
    sameAs: [
      "https://github.com/azar-management-consulting",
      "https://linkedin.com/company/azar-mc",
    ],
  };
}

function softwareSchema(locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "OCCP — OpenCloud Control Plane",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Any",
    inLanguage: locale,
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
}

function webSiteSchema(locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    url: SITE_URL,
    inLanguage: locale,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://docs.occp.ai/?q={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  const t = await getTranslations({ locale, namespace: "metadata" });

  // hreflang alternates: one per supported locale, plus x-default → en.
  const languages: Record<string, string> = Object.fromEntries(
    locales.map((l) => [l, `${SITE_URL}/${l}`]),
  );
  languages["x-default"] = `${SITE_URL}/en`;

  return {
    metadataBase: new URL(SITE_URL),
    title: t("title"),
    description: t("description"),
    keywords: [
      t("keywords.k1"),
      t("keywords.k2"),
      t("keywords.k3"),
      t("keywords.k4"),
      t("keywords.k5"),
      t("keywords.k6"),
    ],
    authors: [{ name: "Azar Management Consulting" }],
    alternates: {
      canonical: `${SITE_URL}/${locale}`,
      languages,
    },
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
      url: `${SITE_URL}/${locale}`,
      siteName: "OCCP",
      locale,
      title: t("ogTitle"),
      description: t("ogDescription"),
      images: [
        { url: `${SITE_URL}/og-image.png`, width: 1200, height: 630, alt: "OCCP" },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: t("twitterTitle"),
      description: t("twitterDescription"),
      images: [`${SITE_URL}/og-image.png`],
    },
    icons: {
      icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%230a0a0a'/><text x='2' y='24' font-family='monospace' font-size='20' fill='%2333ff33'>&#62;_</text></svg>",
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();

  // Enable static rendering.
  setRequestLocale(locale);

  const typedLocale = locale as Locale;

  return (
    <html
      lang={typedLocale}
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <head>
        <link rel="preconnect" href="https://api.occp.ai" />
        <StructuredData data={orgSchema(typedLocale)} />
        <StructuredData data={softwareSchema(typedLocale)} />
        <StructuredData data={webSiteSchema(typedLocale)} />
      </head>
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
