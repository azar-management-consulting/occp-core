import { source } from '@/lib/source';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { baseOptions } from '@/lib/layout.shared';

export default async function Layout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  // With i18n enabled on loader(), source.pageTree is Record<locale, Root>.
  // Narrow via unknown cast to dodge the current Fumadocs 16.8 type surface.
  const trees = source.pageTree as unknown as Record<string, Parameters<typeof DocsLayout>[0]["tree"]>;
  const tree = trees[lang] ?? trees.en;
  return (
    <DocsLayout tree={tree} {...baseOptions(lang)}>
      {children}
    </DocsLayout>
  );
}
