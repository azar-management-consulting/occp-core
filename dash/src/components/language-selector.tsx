"use client";

import { useState, useRef, useEffect } from "react";
import { useI18n, LOCALES } from "@/lib/i18n";

export function LanguageSelector() {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const current = LOCALES.find((l) => l.code === locale) || LOCALES[0];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-mono text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5 transition-all duration-200"
        title="Language"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="opacity-70"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        <span className="uppercase tracking-wider">{locale}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-44 py-1.5 rounded-lg bg-[var(--surface)] border border-[var(--muted)] shadow-xl shadow-black/30 z-[60]">
          {LOCALES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                setLocale(l.code);
                setOpen(false);
              }}
              className={`w-full text-left px-4 py-2 text-sm font-mono flex items-center justify-between transition-colors ${
                locale === l.code
                  ? "text-occp-primary bg-occp-primary/10"
                  : "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-white/5"
              }`}
            >
              <span>{l.native}</span>
              <span className="text-[11px] uppercase tracking-wider opacity-50">{l.code}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
