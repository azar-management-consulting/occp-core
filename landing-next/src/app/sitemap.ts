import type { MetadataRoute } from "next";
import { locales } from "@/i18n/routing";

const BASE = "https://occp.ai";

/**
 * Routes relative to the locale root. `""` means the locale home page.
 */
const ROUTES: ReadonlyArray<{
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
}> = [
  { path: "", changeFrequency: "weekly", priority: 1 },
  { path: "pricing", changeFrequency: "monthly", priority: 0.9 },
  { path: "security", changeFrequency: "monthly", priority: 0.9 },
  { path: "docs", changeFrequency: "weekly", priority: 0.8 },
];

function buildUrl(locale: string, path: string): string {
  return path ? `${BASE}/${locale}/${path}` : `${BASE}/${locale}`;
}

/**
 * Emits one entry per (locale × route) with hreflang `alternates.languages`
 * linking to every peer locale and `x-default` → English.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  return ROUTES.flatMap((route) =>
    locales.map((locale) => {
      const languages: Record<string, string> = Object.fromEntries(
        locales.map((l) => [l, buildUrl(l, route.path)]),
      );
      languages["x-default"] = buildUrl("en", route.path);

      return {
        url: buildUrl(locale, route.path),
        lastModified: now,
        changeFrequency: route.changeFrequency,
        priority: route.priority,
        alternates: { languages },
      };
    }),
  );
}
