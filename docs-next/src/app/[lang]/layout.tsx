import type { Metadata } from 'next';
import { RootProvider } from 'fumadocs-ui/provider/next';
import { Inter } from 'next/font/google';
import { notFound } from 'next/navigation';
import { i18n } from '@/lib/i18n-config';
import '../global.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
});

const SITE_URL = 'https://docs.occp.ai';
const OG_IMAGE = '/og/docs';

const TITLES: Record<string, string> = {
  en: 'OCCP Docs — Verified Autonomy for AI Agents',
  hu: 'OCCP Dokumentáció — Verified Autonomy AI ügynökökhöz',
  de: 'OCCP Docs — Verified Autonomy für KI-Agenten',
  fr: 'OCCP Docs — Verified Autonomy pour agents IA',
  es: 'OCCP Docs — Verified Autonomy para agentes de IA',
  it: 'OCCP Docs — Verified Autonomy per agenti IA',
  pt: 'OCCP Docs — Verified Autonomy para agentes de IA',
};

const DESCRIPTIONS: Record<string, string> = {
  en: 'Build, deploy, and audit AI agents with policy-as-code, a kill switch, and full OpenTelemetry observability.',
  hu: 'Építs, telepíts és auditálj AI ügynököket policy-as-code, kill switch és teljes OpenTelemetry megfigyelhetőség mellett.',
  de: 'Erstellen, bereitstellen und auditieren Sie KI-Agenten mit Policy-as-Code, Kill-Switch und vollständiger OpenTelemetry-Observability.',
  fr: 'Construisez, déployez et auditez des agents IA avec policy-as-code, kill switch et observabilité OpenTelemetry complète.',
  es: 'Construye, despliega y audita agentes de IA con policy-as-code, kill switch y observabilidad OpenTelemetry completa.',
  it: 'Crea, distribuisci e audita agenti IA con policy-as-code, kill switch e osservabilità OpenTelemetry completa.',
  pt: 'Crie, implemente e audite agentes de IA com policy-as-code, kill switch e observabilidade OpenTelemetry completa.',
};

export function generateStaticParams() {
  return i18n.languages.map((lang) => ({ lang }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!(i18n.languages as readonly string[]).includes(lang)) notFound();

  const title = TITLES[lang] ?? TITLES.en;
  const description = DESCRIPTIONS[lang] ?? DESCRIPTIONS.en;

  const languages: Record<string, string> = Object.fromEntries(
    i18n.languages.map((l) => [l, `${SITE_URL}/${l}`]),
  );
  languages['x-default'] = `${SITE_URL}/en`;

  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: title,
      template: '%s · OCCP',
    },
    description,
    applicationName: 'OCCP Docs',
    keywords: [
      'OCCP',
      'OpenCloud Control Plane',
      'AI agents',
      'Verified Autonomy',
      'policy as code',
      'kill switch',
      'OpenTelemetry',
      'EU AI Act',
      'MCP',
    ],
    authors: [{ name: 'Azar Management Consulting' }],
    creator: 'Azar Management Consulting',
    publisher: 'Azar Management Consulting',
    alternates: {
      canonical: `${SITE_URL}/${lang}`,
      languages,
    },
    openGraph: {
      type: 'website',
      siteName: 'OCCP Docs',
      url: `${SITE_URL}/${lang}`,
      locale: lang,
      title,
      description,
      images: [
        {
          url: OG_IMAGE,
          width: 1200,
          height: 630,
          alt: title,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [OG_IMAGE],
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        'max-image-preview': 'large',
        'max-snippet': -1,
      },
    },
  };
}

export default async function LangLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!(i18n.languages as readonly string[]).includes(lang)) notFound();

  return (
    <html lang={lang} className={inter.className} suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <RootProvider
          i18n={{
            locale: lang,
            locales: i18n.languages.map((l) => ({ name: l, locale: l })),
          }}
          theme={{
            defaultTheme: 'dark',
            enableSystem: true,
          }}
        >
          {children}
        </RootProvider>
      </body>
    </html>
  );
}
