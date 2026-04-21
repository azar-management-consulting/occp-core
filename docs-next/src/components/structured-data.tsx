/**
 * StructuredData — server component for JSON-LD injection.
 * Duplicated from landing-next (no cross-package imports between separate Next apps).
 */
export function StructuredData({ data }: { data: unknown }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
