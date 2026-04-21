/**
 * StructuredData — server component for JSON-LD injection.
 * Sanctioned pattern for Next 15: dangerouslySetInnerHTML with JSON.stringify.
 * The script tag is emitted as-is; no client hydration involved.
 */
export function StructuredData({ data }: { data: unknown }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
