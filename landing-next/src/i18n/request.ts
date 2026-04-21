import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing, defaultLocale, type Locale } from "./routing";

/**
 * Server-side request config. Loads messages/<locale>.json on demand.
 * Falls back to `en` for unknown / missing locales.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale: Locale = hasLocale(routing.locales, requested)
    ? (requested as Locale)
    : defaultLocale;

  const messages = (await import(`../../messages/${locale}.json`)).default;

  return {
    locale,
    messages,
  };
});
