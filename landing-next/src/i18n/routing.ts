import { defineRouting } from "next-intl/routing";

/**
 * next-intl routing config for occp.ai landing page.
 *
 * Strategy: explicit `localePrefix: "always"` — every URL is prefixed with
 * the locale (`/en`, `/hu`, `/de`, ...). Cleanest for SEO + hreflang.
 * Bare `/` is redirected by the middleware based on Accept-Language.
 */
export const locales = ["en", "hu", "de", "fr", "es", "it", "pt"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export const localeLabels: Record<Locale, { label: string; native: string }> = {
  en: { label: "English", native: "English" },
  hu: { label: "Hungarian", native: "Magyar" },
  de: { label: "German", native: "Deutsch" },
  fr: { label: "French", native: "Français" },
  es: { label: "Spanish", native: "Español" },
  it: { label: "Italian", native: "Italiano" },
  pt: { label: "Portuguese", native: "Português" },
};

export const routing = defineRouting({
  locales: locales as unknown as string[],
  defaultLocale,
  localePrefix: "always",
});
