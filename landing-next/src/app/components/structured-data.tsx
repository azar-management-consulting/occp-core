/**
 * StructuredData — server component for JSON-LD injection.
 * Sanctioned pattern for Next 15: dangerouslySetInnerHTML with JSON.stringify.
 * The script tag is emitted as-is; no client hydration involved.
 *
 * Locale is carried inside the `data` payload (e.g. `inLanguage` on
 * Organization / WebSite / Article), so this component stays locale-agnostic.
 */
export function StructuredData({ data }: { data: unknown }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
