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

const BUILD_DATE = process.env.BUILD_TIME ?? '2026-04-21';
const DOCS_BASE = 'https://docs.occp.ai';

const azarOrg = {
  '@type': 'Organization',
  name: 'Azar Management Consulting',
  url: 'https://occp.ai',
};

function buildArticleSchema(title: string, slug: string[]) {
  const pageUrl = `${DOCS_BASE}/docs/${slug.join('/')}`;
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: title,
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

function buildBreadcrumbSchema(slug: string[], title: string) {
  const segments = slug ?? [];
  const items = [
    {
      '@type': 'ListItem',
      position: 1,
      name: 'Home',
      item: DOCS_BASE,
    },
    {
      '@type': 'ListItem',
      position: 2,
      name: 'Docs',
      item: `${DOCS_BASE}/docs`,
    },
  ];

  if (segments.length > 1) {
    items.push({
      '@type': 'ListItem',
      position: 3,
      name: segments[0],
      item: `${DOCS_BASE}/docs/${segments[0]}`,
    });
  }

  if (segments.length > 0) {
    items.push({
      '@type': 'ListItem',
      position: items.length + 1,
      name: title,
      item: `${DOCS_BASE}/docs/${segments.join('/')}`,
    });
  }

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items,
  };
}

export default async function Page(props: PageProps<'/docs/[[...slug]]'>) {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  const MDX = page.data.body;
  const markdownUrl = getPageMarkdownUrl(page).url;
  const slugSegments = params.slug ?? [];

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      <StructuredData data={buildArticleSchema(page.data.title, slugSegments)} />
      <StructuredData data={buildBreadcrumbSchema(slugSegments, page.data.title)} />
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
  return source.generateParams();
}

export async function generateMetadata(props: PageProps<'/docs/[[...slug]]'>): Promise<Metadata> {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
    openGraph: {
      images: getPageImage(page).url,
    },
  };
}
