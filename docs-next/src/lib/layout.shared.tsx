import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { i18n } from '@/lib/i18n-config';

/**
 * Shared navigation + framing used by both the docs layout
 * and the (home) marketing layout.
 *
 * i18n-aware: every URL is prefixed with the active language. `/` → `/<lang>`.
 * Tagline remains English for brand consistency; translate here if desired.
 *
 * FELT: Fumadocs 16 BaseLayoutProps supports `nav.url` / `links[].url` with
 * arbitrary paths — we use locale-prefixed relative paths to stay compatible
 * with both the i18n-aware router and the default one.
 */
export function baseOptions(lang: string = i18n.defaultLanguage): BaseLayoutProps {
  return {
    nav: {
      url: `/${lang}`,
      title: (
        <span className="flex items-baseline gap-2 font-semibold tracking-tight">
          <span className="text-fd-primary">OCCP</span>
          <span className="hidden text-xs font-normal text-fd-muted-foreground md:inline">
            Verified Autonomy for AI Agents
          </span>
        </span>
      ),
    },
    links: [
      { text: 'Docs', url: `/${lang}/docs` },
      { text: 'API', url: `/${lang}/api-reference` },
      { text: 'Changelog', url: `/${lang}/docs/changelog` },
      { text: '→ occp.ai', url: 'https://occp.ai', external: true },
    ],
    githubUrl: 'https://github.com/azar-management-consulting/occp-core',
  };
}
