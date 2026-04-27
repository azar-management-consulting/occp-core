"use client";

import { useEffect, useRef, useState } from "react";
import { Info, Zap, AlertTriangle, X } from "lucide-react";
import { tOnboarding, type OnboardingLocale } from "@/lib/onboarding-i18n";
import { readHintsGloballyEnabled } from "./onboarding-provider";

export type HintVariant = "info" | "pro-tip" | "warning";

interface HelpBubbleProps {
  /** Versioned key. Storage: occp_hint_<key>_v1. */
  hintKey: string;
  /** CSS selector or ref to the element being explained. */
  anchor: string | React.RefObject<Element | null>;
  variant?: HintVariant;
  title?: string;
  body: string;
  /** "top" | "bottom" | "left" | "right" — default "bottom" (below anchor). */
  placement?: "top" | "bottom" | "left" | "right";
  /** Override version key (default 1). Bump when copy changes meaningfully. */
  version?: number;
  /** Override the i18n-fed labels. Default uses hint.common.*. */
  labels?: { gotIt?: string; dismissAll?: string; dismissAria?: string };
}

const VARIANT_BORDER: Record<HintVariant, string> = {
  info: "var(--occp-bubble-border-info)",
  "pro-tip": "var(--occp-bubble-border)",
  warning: "var(--occp-bubble-border-warning)",
};

const VARIANT_ICON: Record<HintVariant, typeof Info> = {
  info: Info,
  "pro-tip": Zap,
  warning: AlertTriangle,
};

function readLocale(): OnboardingLocale {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem("occp_lang");
    if (v === "en" || v === "hu" || v === "de" || v === "fr" || v === "es" || v === "it" || v === "pt") return v;
    return "en";
  } catch {
    return "en";
  }
}

export function HelpBubble({
  hintKey,
  anchor,
  variant = "info",
  title,
  body,
  placement = "bottom",
  version = 1,
  labels,
}: HelpBubbleProps) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState<React.CSSProperties>({});
  const [locale, setLocale] = useState<OnboardingLocale>("en");
  const bubbleRef = useRef<HTMLDivElement>(null);
  const lsKey = `occp_hint_${hintKey}_v${version}`;

  // Mount-time visibility check.
  useEffect(() => {
    if (typeof window === "undefined") return;
    setLocale(readLocale());
    if (!readHintsGloballyEnabled()) return;
    let dismissed = false;
    try {
      dismissed =
        window.localStorage.getItem(lsKey) === "dismissed" ||
        window.localStorage.getItem("occp_all_hints_dismissed") === "true";
    } catch {
      // ignore
    }
    if (!dismissed) setVisible(true);
  }, [lsKey]);

  // Position relative to anchor.
  useEffect(() => {
    if (!visible || typeof window === "undefined") return;

    const update = () => {
      let target: Element | null = null;
      if (typeof anchor === "string") target = document.querySelector(anchor);
      else target = anchor?.current ?? null;
      if (!target || !bubbleRef.current) return;

      const r = target.getBoundingClientRect();
      const bw = bubbleRef.current.offsetWidth;
      const bh = bubbleRef.current.offsetHeight;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const gap = 12;
      const PADDING = 12;

      let top = 0,
        left = 0;
      if (placement === "bottom") {
        top = r.bottom + gap;
        left = r.left + r.width / 2 - bw / 2;
      } else if (placement === "top") {
        top = r.top - bh - gap;
        left = r.left + r.width / 2 - bw / 2;
      } else if (placement === "left") {
        top = r.top + r.height / 2 - bh / 2;
        left = r.left - bw - gap;
      } else if (placement === "right") {
        top = r.top + r.height / 2 - bh / 2;
        left = r.right + gap;
      }
      // Clamp to viewport
      if (left < PADDING) left = PADDING;
      if (left + bw > vw - PADDING) left = vw - bw - PADDING;
      if (top < PADDING) top = PADDING;
      if (top + bh > vh - PADDING) top = vh - bh - PADDING;

      setPos({
        position: "fixed",
        top,
        left,
      });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [visible, anchor, placement]);

  // Esc dismiss.
  useEffect(() => {
    if (!visible) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const dismiss = () => {
    setVisible(false);
    try {
      window.localStorage.setItem(lsKey, "dismissed");
    } catch {
      // ignore
    }
    // Restore focus to anchor element.
    let target: Element | null = null;
    if (typeof anchor === "string") target = document.querySelector(anchor);
    else target = anchor?.current ?? null;
    (target as HTMLElement | null)?.focus?.();
  };

  const dismissAll = () => {
    try {
      window.localStorage.setItem("occp_all_hints_dismissed", "true");
    } catch {
      // ignore
    }
    setVisible(false);
  };

  if (!visible) return null;

  const Icon = VARIANT_ICON[variant];
  const t = (k: string, fb?: string) => tOnboarding(locale, k, fb);
  const gotIt = labels?.gotIt ?? t("hint.common.got_it");
  const dismissAllLabel = labels?.dismissAll ?? t("hint.common.dismiss_all");
  const dismissAria = labels?.dismissAria ?? t("hint.common.dismiss_label");

  return (
    <div
      ref={bubbleRef}
      role="status"
      aria-live="polite"
      style={{
        ...pos,
        zIndex: "var(--z-bubble)" as unknown as number,
        maxWidth: 320,
        background: "var(--occp-bubble-bg)",
        borderLeft: `3px solid ${VARIANT_BORDER[variant]}`,
        borderRadius: 8,
        boxShadow: "var(--occp-bubble-shadow)",
        padding: "12px 14px",
        fontFamily: "var(--font-mono), monospace",
        color: "var(--fg, #fafafa)",
        animation: "occp-bubble-in 200ms ease-out",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <Icon size={16} aria-hidden style={{ color: VARIANT_BORDER[variant], flexShrink: 0, marginTop: 1 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          {title ? (
            <p style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: 4 }}>
              {title}
            </p>
          ) : null}
          <p
            style={{
              fontSize: "0.8125rem",
              color: "var(--fg-muted, #a1a1aa)",
              lineHeight: 1.5,
              margin: 0,
            }}
          >
            {body}
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label={dismissAria}
          style={{
            width: 24,
            height: 24,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            color: "var(--fg-muted, #a1a1aa)",
            borderRadius: 4,
            padding: 0,
            flexShrink: 0,
          }}
        >
          <X size={14} aria-hidden />
        </button>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginTop: 10,
          paddingLeft: 24,
        }}
      >
        <button
          type="button"
          onClick={dismiss}
          style={{
            fontSize: "0.8125rem",
            color: VARIANT_BORDER[variant],
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 0,
            fontWeight: 600,
          }}
        >
          {gotIt}
        </button>
        <button
          type="button"
          onClick={dismissAll}
          style={{
            fontSize: "0.6875rem",
            color: "var(--fg-muted, #a1a1aa)",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            padding: 0,
            textDecoration: "underline",
          }}
        >
          {dismissAllLabel}
        </button>
      </div>
    </div>
  );
}
