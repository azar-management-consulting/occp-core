"use client";

import { useEffect, useState } from "react";

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface SpotlightOverlayProps {
  /** CSS selector to highlight. null → full dim, no cutout. */
  anchorSelector: string | null;
  /** Padding around the anchor's bounding rect (px). Default 8. */
  padding?: number;
  /** Click-through on overlay (allow user to interact with anchor). Default true. */
  clickThrough?: boolean;
}

const FULL: Rect = { top: -9999, left: -9999, width: 0, height: 0 };

/**
 * Full-screen scrim with a CSS clip-path cutout around the anchor element.
 * Re-positions on resize + scroll. Renders nothing if anchor not found.
 */
export function SpotlightOverlay({
  anchorSelector,
  padding = 8,
  clickThrough = true,
}: SpotlightOverlayProps) {
  const [rect, setRect] = useState<Rect>(FULL);

  useEffect(() => {
    if (!anchorSelector) {
      setRect(FULL);
      return;
    }
    if (typeof window === "undefined") return;

    let raf = 0;
    const measure = () => {
      const el = document.querySelector(anchorSelector) as HTMLElement | null;
      if (!el) {
        setRect(FULL);
        return;
      }
      const r = el.getBoundingClientRect();
      setRect({
        top: r.top + window.scrollY - padding,
        left: r.left + window.scrollX - padding,
        width: r.width + padding * 2,
        height: r.height + padding * 2,
      });
    };

    const scheduleMeasure = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("scroll", scheduleMeasure, true);

    let observer: ResizeObserver | null = null;
    const target = document.querySelector(anchorSelector);
    if (target && "ResizeObserver" in window) {
      observer = new ResizeObserver(scheduleMeasure);
      observer.observe(target);
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, true);
      observer?.disconnect();
    };
  }, [anchorSelector, padding]);

  // CSS clip-path: outside rectangle minus inside cutout (using polygon).
  // Produces a "donut" — full screen dim with a transparent rectangle window.
  const cutoutStyle: React.CSSProperties =
    anchorSelector && rect.width > 0
      ? {
          clipPath: `polygon(
            0 0,
            0 100%,
            ${rect.left}px 100%,
            ${rect.left}px ${rect.top}px,
            ${rect.left + rect.width}px ${rect.top}px,
            ${rect.left + rect.width}px ${rect.top + rect.height}px,
            ${rect.left}px ${rect.top + rect.height}px,
            ${rect.left}px 100%,
            100% 100%,
            100% 0
          )`,
        }
      : {};

  return (
    <>
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--occp-tour-overlay)",
          zIndex: "var(--z-tour-overlay)" as unknown as number,
          pointerEvents: clickThrough ? "none" : "auto",
          transition: "opacity 200ms ease-out",
          ...cutoutStyle,
        }}
      />
      {anchorSelector && rect.width > 0 ? (
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height,
            borderRadius: "var(--occp-tour-spotlight-radius)",
            boxShadow: "var(--occp-tour-spotlight-glow)",
            pointerEvents: "none",
            zIndex: "var(--z-tour-spotlight)" as unknown as number,
          }}
        />
      ) : null}
    </>
  );
}
