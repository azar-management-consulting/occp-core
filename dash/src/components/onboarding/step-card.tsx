"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export type BubbleVariant = "info" | "pro-tip" | "warning";

const VARIANT_BORDER: Record<BubbleVariant, string> = {
  info: "var(--occp-bubble-border-info)",
  "pro-tip": "var(--occp-bubble-border)",
  warning: "var(--occp-bubble-border-warning)",
};

interface StepCardProps {
  /** CSS selector to anchor near. null → centered modal. */
  anchorSelector: string | null;
  variant?: BubbleVariant;
  title: string;
  subtitle?: string;
  /** Inline custom content (e.g. API key reveal, run button). */
  content?: ReactNode;
  primaryCta: string;
  onPrimary: () => void;
  /** Disabled until content interaction completes (e.g. task ran). */
  primaryDisabled?: boolean;
  secondaryCta?: string;
  onSecondary?: () => void;
  skipCta?: string;
  onSkip?: () => void;
  /** "1 of 5", "2 of 5"... rendered as dots + sr-only text. */
  stepNumber?: number;
  totalSteps?: number;
}

/**
 * Floating card with copy + CTAs. When anchorSelector is null, renders a
 * centered modal. Otherwise floats below the anchor with a CSS pointer.
 */
export function StepCard({
  anchorSelector,
  variant = "pro-tip",
  title,
  subtitle,
  content,
  primaryCta,
  onPrimary,
  primaryDisabled,
  secondaryCta,
  onSecondary,
  skipCta,
  onSkip,
  stepNumber,
  totalSteps,
}: StepCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [pos, setPos] = useState<React.CSSProperties>({});

  // Position relative to anchor (or center).
  useEffect(() => {
    if (typeof window === "undefined") return;

    const update = () => {
      if (!anchorSelector) {
        setPos({
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        });
        return;
      }
      const el = document.querySelector(anchorSelector) as HTMLElement | null;
      if (!el || !cardRef.current) {
        setPos({
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        });
        return;
      }
      const r = el.getBoundingClientRect();
      const cardH = cardRef.current.offsetHeight;
      const cardW = cardRef.current.offsetWidth;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const padding = 16;

      // Default: below anchor, horizontally centered to anchor.
      let top = r.bottom + padding;
      let left = r.left + r.width / 2 - cardW / 2;

      // Flip above if not enough room below.
      if (top + cardH > vh - padding) top = r.top - cardH - padding;
      // Clamp horizontal.
      if (left < padding) left = padding;
      if (left + cardW > vw - padding) left = vw - cardW - padding;

      setPos({
        position: "absolute",
        top: top + window.scrollY,
        left: left + window.scrollX,
      });
    };

    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [anchorSelector]);

  // Focus the title on mount for screen reader announcement.
  useEffect(() => {
    titleRef.current?.focus();
  }, [title]);

  // Escape closes via skip if available, otherwise primary.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (onSkip) onSkip();
        else onPrimary();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSkip, onPrimary]);

  const dots =
    stepNumber && totalSteps
      ? Array.from({ length: totalSteps }, (_, i) =>
          i + 1 === stepNumber ? "●" : "○",
        ).join(" ")
      : "";

  return (
    <div
      ref={cardRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-step-title"
      style={{
        ...pos,
        zIndex: "var(--z-bubble)" as unknown as number,
        maxWidth: 420,
        background: "var(--occp-bubble-bg)",
        borderLeft: `3px solid ${VARIANT_BORDER[variant]}`,
        borderRadius: 8,
        boxShadow: "var(--occp-bubble-shadow)",
        padding: 20,
        color: "var(--fg, #fafafa)",
        fontFamily: "var(--font-mono), monospace",
      }}
    >
      <h2
        id="onboarding-step-title"
        ref={titleRef}
        tabIndex={-1}
        style={{
          fontSize: "1.25rem",
          fontWeight: 600,
          marginBottom: subtitle ? 8 : 16,
          letterSpacing: "-0.01em",
          outline: "none",
        }}
      >
        {title}
      </h2>
      {subtitle ? (
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--fg-muted, #a1a1aa)",
            lineHeight: 1.5,
            marginBottom: content || dots ? 16 : 24,
          }}
        >
          {subtitle}
        </p>
      ) : null}
      {content ? <div style={{ marginBottom: 16 }}>{content}</div> : null}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginTop: 12,
        }}
      >
        {dots ? (
          <span
            aria-label={
              stepNumber && totalSteps
                ? `Step ${stepNumber} of ${totalSteps}`
                : undefined
            }
            style={{
              fontFamily: "var(--font-mono), monospace",
              fontSize: "0.75rem",
              color: "var(--fg-muted, #a1a1aa)",
              letterSpacing: "0.2em",
            }}
          >
            {dots}
          </span>
        ) : (
          <span />
        )}

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {skipCta && onSkip ? (
            <button
              type="button"
              onClick={onSkip}
              style={{
                fontSize: "0.75rem",
                color: "var(--fg-muted, #a1a1aa)",
                textDecoration: "underline",
                cursor: "pointer",
                background: "transparent",
                border: "none",
                padding: "4px 8px",
              }}
            >
              {skipCta}
            </button>
          ) : null}
          {secondaryCta && onSecondary ? (
            <Button variant="ghost" size="sm" onClick={onSecondary}>
              {secondaryCta}
            </Button>
          ) : null}
          <Button onClick={onPrimary} disabled={primaryDisabled} size="sm">
            {primaryCta}
          </Button>
        </div>
      </div>
    </div>
  );
}
