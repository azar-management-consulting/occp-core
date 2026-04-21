import Link from 'next/link';

const HOME_COPY: Record<string, { title: string; openDocs: string; andSee: string }> = {
  en: { title: 'OCCP Documentation', openDocs: 'open', andSee: 'and see the documentation.' },
  hu: { title: 'OCCP Dokumentáció', openDocs: 'nyisd meg', andSee: 'és tekintsd meg a dokumentációt.' },
  de: { title: 'OCCP Dokumentation', openDocs: 'öffnen', andSee: 'und die Dokumentation ansehen.' },
  fr: { title: 'Documentation OCCP', openDocs: 'ouvrir', andSee: 'et consulter la documentation.' },
  es: { title: 'Documentación OCCP', openDocs: 'abrir', andSee: 'y ver la documentación.' },
  it: { title: 'Documentazione OCCP', openDocs: 'apri', andSee: 'e vedere la documentazione.' },
  pt: { title: 'Documentação OCCP', openDocs: 'abrir', andSee: 'e ver a documentação.' },
};

export default async function HomePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const copy = HOME_COPY[lang] ?? HOME_COPY.en;

  return (
    <div className="flex flex-col justify-center text-center flex-1">
      <h1 className="text-2xl font-bold mb-4">{copy.title}</h1>
      <p>
        {copy.openDocs}{' '}
        <Link href={`/${lang}/docs`} className="font-medium underline">
          /{lang}/docs
        </Link>{' '}
        {copy.andSee}
      </p>
    </div>
  );
}
