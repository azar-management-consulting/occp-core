import type { MetadataRoute } from 'next';
import { source } from '@/lib/source';
import { i18n } from '@/lib/i18n-config';

const BASE = 'https://docs.occp.ai';

/**
 * Emits one sitemap entry per (page × language) with hreflang alternates.
 *
 * Strategy:
 *   - Root home `/{lang}` → priority 1.
 *   - Each doc page gets its URL mapped across all locales via
 *     `alternates.languages`, plus `x-default` → `en`.
 *
 * FELT: Fumadocs `source.getPages(lang)` returns pages for a specific lang.
 * We union them and key by slug path so missing translations still appear in
 * the alternates map (pointing at EN as a fallback).
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const entries: MetadataRoute.Sitemap = [];

  // Build a slug-keyed index of which (lang → url) variants exist.
  type Variant = { url: string };
  const byPath = new Map<string, Record<string, Variant>>();

  for (const lang of i18n.languages) {
    let pages: ReturnType<typeof source.getPages> = [];
    try {
      pages = source.getPages(lang);
    } catch {
      pages = source.getPages();
    }
    for (const page of pages) {
      // page.url is typically like "/docs/quickstart"; prefix with lang.
      const pathKey = page.url;
      const absolute = `${BASE}/${lang}${page.url}`;
      const bucket = byPath.get(pathKey) ?? {};
      bucket[lang] = { url: absolute };
      byPath.set(pathKey, bucket);
    }
  }

  // Home root per language.
  for (const lang of i18n.languages) {
    const languages: Record<string, string> = Object.fromEntries(
      i18n.languages.map((l) => [l, `${BASE}/${l}`]),
    );
    languages['x-default'] = `${BASE}/en`;
    entries.push({
      url: `${BASE}/${lang}`,
      lastModified: now,
      changeFrequency: 'weekly',
      priority: 1,
      alternates: { languages },
    });
  }

  // One entry per doc page per language that has it.
  for (const [pathKey, variants] of byPath.entries()) {
    const languages: Record<string, string> = {};
    for (const lang of i18n.languages) {
      // Missing translations fall back to EN in the alternates map.
      languages[lang] = variants[lang]?.url ?? `${BASE}/en${pathKey}`;
    }
    languages['x-default'] = `${BASE}/en${pathKey}`;

    for (const lang of Object.keys(variants)) {
      entries.push({
        url: variants[lang].url,
        lastModified: now,
        changeFrequency: 'weekly',
        priority: pathKey === '/docs' ? 0.95 : 0.8,
        alternates: { languages },
      });
    }
  }

  return entries;
}
