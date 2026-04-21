"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/-/g, " ");
}

/**
 * Breadcrumb — parses the current pathname into navigable segments.
 * Skips the "v2" route prefix so breadcrumbs read naturally.
 *
 * Design: text-sm, fg-muted, ChevronRight separator 14×14.
 * a11y: <nav aria-label="Breadcrumb"> + <ol> / <li>.
 */
export function Breadcrumb() {
  const pathname = usePathname();

  const raw = pathname.split("/").filter(Boolean);
  // Strip the "v2" prefix so the breadcrumb is route-agnostic
  const segments = raw[0] === "v2" ? raw.slice(1) : raw;

  // Build [{label, href}] pairs for every segment
  const crumbs = segments.map((seg, i) => {
    const href =
      "/" +
      raw.slice(0, raw[0] === "v2" ? i + 2 : i + 1).join("/");
    return { label: capitalize(seg), href };
  });

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1 text-sm text-[var(--fg-muted,#a1a1aa)]">
        {/* Home */}
        <li>
          {crumbs.length === 0 ? (
            <span
              className="font-medium text-[var(--fg,#fafafa)]"
              aria-current="page"
            >
              <Home size={14} aria-hidden="true" className="inline -mt-0.5" />
              <span className="sr-only">Home</span>
            </span>
          ) : (
            <Link
              href="/v2"
              className="transition-colors hover:text-[var(--fg,#fafafa)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] rounded-sm"
            >
              <Home size={14} aria-hidden="true" className="inline -mt-0.5" />
              <span className="sr-only">Home</span>
            </Link>
          )}
        </li>

        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex items-center gap-1">
              <ChevronRight
                size={14}
                aria-hidden="true"
                className="shrink-0 text-[var(--fg-muted,#a1a1aa)]"
              />
              {isLast ? (
                <span
                  className="font-medium text-[var(--fg,#fafafa)]"
                  aria-current="page"
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="transition-colors hover:text-[var(--fg,#fafafa)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] rounded-sm"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
