import { getPageImage, getPageMarkdownUrl, source } from '@/lib/source';
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
  MarkdownCopyButton,
  ViewOptionsPopover,
} from 'fumadocs-ui/layouts/docs/page';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/components/mdx';
import type { Metadata } from 'next';
import { createRelativeLink } from 'fumadocs-ui/mdx';
import { gitConfig } from '@/lib/shared';
import { StructuredData } from '@/components/structured-data';
import { i18n } from '@/lib/i18n-config';

const BUILD_DATE = process.env.BUILD_TIME ?? '2026-04-21';
const DOCS_BASE = 'https://docs.occp.ai';

const azarOrg = {
  '@type': 'Organization',
  name: 'Azar Management Consulting',
  url: 'https://occp.ai',
};

function buildArticleSchema(
  title: string,
  slug: string[],
  lang: string,
) {
  const pageUrl = `${DOCS_BASE}/${lang}/docs/${slug.join('/')}`;
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: title,
    inLanguage: lang,
    author: azarOrg,
    publisher: azarOrg,
    datePublished: '2026-04-21',
    dateModified: BUILD_DATE,
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': pageUrl,
    },
    url: pageUrl,
  };
}

function buildBreadcrumbSchema(slug: string[], title: string, lang: string) {
  const segments = slug ?? [];
  const items: Array<Record<string, unknown>> = [
    {
      '@type': 'ListItem',
      position: 1,
      name: 'Home',
      item: `${DOCS_BASE}/${lang}`,
    },
    {
      '@type': 'ListItem',
      position: 2,
      name: 'Docs',
      item: `${DOCS_BASE}/${lang}/docs`,
    },
  ];

  if (segments.length > 1) {
    items.push({
      '@type': 'ListItem',
      position: 3,
      name: segments[0],
      item: `${DOCS_BASE}/${lang}/docs/${segments[0]}`,
    });
  }

  if (segments.length > 0) {
    items.push({
      '@type': 'ListItem',
      position: items.length + 1,
      name: title,
      item: `${DOCS_BASE}/${lang}/docs/${segments.join('/')}`,
    });
  }

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items,
  };
}

export default async function Page(props: {
  params: Promise<{ lang: string; slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage([params.lang, ...(params.slug ?? [])]);
  if (!page) notFound();

  // Fumadocs 16.8: PageData only declares {icon,title,description}; the MDX
  // module is attached as `body` or `default` at runtime — widen the type.
  const pageData = page.data as typeof page.data & {
    body?: React.ComponentType<{ components: unknown }>;
    default?: React.ComponentType<{ components: unknown }>;
    toc?: unknown;
    full?: boolean;
  };
  const MDX = pageData.body ?? pageData.default;
  if (!MDX) notFound();
  const markdownUrl = getPageMarkdownUrl(page).url;
  const slugSegments = params.slug ?? [];

  return (
    <DocsPage toc={pageData.toc as Parameters<typeof DocsPage>[0]["toc"]} full={pageData.full}>
      <StructuredData data={buildArticleSchema(page.data.title ?? "OCCP", slugSegments, params.lang)} />
      <StructuredData data={buildBreadcrumbSchema(slugSegments, page.data.title ?? "OCCP", params.lang)} />
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription className="mb-0">{page.data.description}</DocsDescription>
      <div className="flex flex-row gap-2 items-center border-b pb-6">
        <MarkdownCopyButton markdownUrl={markdownUrl} />
        <ViewOptionsPopover
          markdownUrl={markdownUrl}
          githubUrl={`https://github.com/${gitConfig.user}/${gitConfig.repo}/blob/${gitConfig.branch}/content/docs/${page.path}`}
        />
      </div>
      <DocsBody>
        <MDX
          components={getMDXComponents({
            // this allows you to link to other pages with relative file paths
            a: createRelativeLink(source, page),
          })}
        />
      </DocsBody>
    </DocsPage>
  );
}

export async function generateStaticParams() {
  // Our content lives at content/docs/<lang>/<slug>.mdx — so every page's
  // `slugs[0]` IS the locale and `slugs[1:]` is the real slug. Split here;
  // the page lookup (`source.getPage([lang, ...slug])`) below mirrors it.
  const params: { lang: string; slug: string[] }[] = [];
  for (const page of source.getPages()) {
    const [lang, ...slug] = page.slugs;
    if (i18n.languages.includes(lang)) params.push({ lang, slug });
  }
  return params;
}

export async function generateMetadata(props: {
  params: Promise<{ lang: string; slug?: string[] }>;
}): Promise<Metadata> {
  const params = await props.params;
  const page = source.getPage([params.lang, ...(params.slug ?? [])]);
  if (!page) notFound();

  // hreflang per supported language.
  const slugPath = (params.slug ?? []).join('/');
  const suffix = slugPath ? `/docs/${slugPath}` : '/docs';
  const languages: Record<string, string> = Object.fromEntries(
    i18n.languages.map((l) => [l, `${DOCS_BASE}/${l}${suffix}`]),
  );
  languages['x-default'] = `${DOCS_BASE}/en${suffix}`;

  return {
    title: page.data.title,
    description: page.data.description,
    alternates: {
      canonical: `${DOCS_BASE}/${params.lang}${suffix}`,
      languages,
    },
    openGraph: {
      images: getPageImage(page).url,
      locale: params.lang,
    },
  };
}
