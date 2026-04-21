/**
 * Fumadocs 16.8 i18n config — consumed by `loader({ i18n })` in source.ts
 * and by next-intl request handler. Exported separately from source.config.ts
 * because Fumadocs rejects non-collection exports in the config file.
 */
export const LOCALES = ["en", "hu", "de", "fr", "es", "it", "pt"] as const;

export type Locale = (typeof LOCALES)[number];

// Fumadocs I18nConfig expects mutable `languages: string[]` — spread into a new
// array at export time; the `as const` LOCALES above stays for type safety.
export const i18n = {
  defaultLanguage: "en",
  languages: [...LOCALES] as string[],
};
