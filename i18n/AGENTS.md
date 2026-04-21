# OCCP i18n — Shared Conventions

Scope: `landing-next/`, `docs-next/`, `dash/`. All three ship with the same
locale set and the same canonical locale codes.

## Supported locales (canonical order)

`en` · `hu` · `de` · `fr` · `es` · `it` · `pt`

Default: `en` (USA English, primary market). `en` is also the `x-default`
target for hreflang.

## Adding a new locale

1. Pick the ISO 639-1 code (e.g. `nl`, `pl`, `ja`, `zh`).
2. **landing-next**
   - Append to `locales` in `src/i18n/routing.ts` and `localeLabels`.
   - Update the `matcher` regex in `src/middleware.ts`.
   - Copy `messages/en.json` → `messages/<code>.json` and translate.
3. **docs-next**
   - Append to `i18n.languages` in `source.config.ts`.
   - Create `content/docs/<code>/index.mdx` (placeholder OK).
   - Extend the `TITLES` / `DESCRIPTIONS` / `HOME_COPY` maps in
     `src/app/[lang]/layout.tsx` and `src/app/[lang]/(home)/page.tsx`.
4. **dash** — append to `LOCALES` and `translations` in `src/lib/i18n.tsx`.
5. Run build in all three apps; verify sitemap emits new hreflang entries.

## Translation-file conventions (landing-next + docs-next)

- One JSON file per locale, under `<app>/messages/<locale>.json`.
- Namespaces map 1-to-1 to components: `hero`, `codeTabs`, `pipeline`,
  `metadata`. Create a new namespace when adding a new component.
- Keys are camelCase. Never nest more than 3 levels.
- No interpolation unless absolutely required; if needed use ICU message
  format (next-intl native support).
- For Hungarian B2B SaaS tone: match the style in `dash/src/lib/i18n.tsx`
  (formal "Ön"-style where needed; uppercase technical terms kept in English
  like `PIPELINE`, `AUDIT`).

## MDX content (docs-next only)

MDX bodies are NOT translated via `messages/*.json`. They live in
`content/docs/<locale>/...`. Translating the full English tree is a
separate translation-memory workflow (out of scope for ad-hoc agents).
Until a locale is fully translated, its `content/docs/<locale>/index.mdx`
placeholder redirects readers to `/en`.

## Keeping landing + dash + docs in sync

- Canonical locale list lives in **three** files (no central source yet):
  - `landing-next/src/i18n/routing.ts` (`locales`)
  - `docs-next/source.config.ts` (`i18n.languages`)
  - `dash/src/lib/i18n.tsx` (`LOCALES`)
- When adding a locale, grep the repo for one of the existing codes
  (e.g. `"hu"`) to find every call site.
- `dash` uses **client-side** i18n (localStorage-backed). Landing + docs use
  **path-prefix** i18n (`/hu/...`). Do not conflate.

## hreflang strategy

- `landing-next`: canonical = `https://occp.ai/<locale>`.
- `docs-next`:    canonical = `https://docs.occp.ai/<locale>/docs/...`.
- Every page emits `alternates.languages` with all 7 locales + `x-default`
  pointing at the English variant.
- Middleware on landing-next redirects bare `/` to `/<locale>` based on
  `Accept-Language`, falling back to `/en` on anything unsupported.

## Subdomain split

- `occp.ai`      → landing-next
- `docs.occp.ai` → docs-next
- `dash.occp.ai` → dash (client-side i18n, no path prefix)

Each app owns its own `sitemap.xml` and `robots.txt`. There is **no** unified
sitemap; Google follows the hreflang links cross-subdomain.
