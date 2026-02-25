"use client";

import { useState } from "react";
import { useT } from "@/lib/i18n";

type SessionScope = "single_user" | "per_user" | "per_channel";

interface SessionPolicyPanelProps {
  initialScope?: SessionScope;
  showSecureBanner?: boolean;
  onScopeChange?: (scope: SessionScope) => void;
}

const SCOPE_ICONS: Record<SessionScope, string> = {
  single_user: "👤",
  per_user: "👥",
  per_channel: "📡",
};

export function SessionPolicyPanel({
  initialScope = "single_user",
  showSecureBanner = false,
  onScopeChange,
}: SessionPolicyPanelProps) {
  const [scope, setScope] = useState<SessionScope>(initialScope);
  const t = useT();

  const handleSelect = (newScope: SessionScope) => {
    setScope(newScope);
    onScopeChange?.(newScope);
  };

  const scopes: { id: SessionScope; label: string; desc: string }[] = [
    { id: "single_user", label: t.onboarding.singleUser, desc: t.onboarding.singleUserDesc },
    { id: "per_user", label: t.onboarding.perUser, desc: t.onboarding.perUserDesc },
    { id: "per_channel", label: t.onboarding.perChannel, desc: t.onboarding.perChannelDesc },
  ];

  return (
    <div className="space-y-4">
      {/* Secure Mode Banner */}
      {showSecureBanner && (
        <div className="retro-card border-occp-warning/40 bg-occp-warning/5 p-4">
          <div className="flex items-start gap-3">
            <span className="text-lg">🛡</span>
            <div>
              <h3 className="font-pixel text-[11px] text-occp-warning tracking-wider uppercase">
                {t.onboarding.secureModeTitle}
              </h3>
              <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                {t.onboarding.secureModeDesc}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Session Scope Selector */}
      <div className="space-y-3">
        <h3 className="font-pixel text-[11px] text-occp-accent tracking-wider uppercase">
          {t.onboarding.sessionScope}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {scopes.map((s) => (
            <button
              key={s.id}
              onClick={() => handleSelect(s.id)}
              className={`p-4 rounded text-left transition-all border ${
                scope === s.id
                  ? "bg-occp-primary/10 border-occp-primary/40 shadow-[0_0_8px_rgba(110,196,229,0.1)]"
                  : "bg-occp-dark/30 border-occp-muted/20 hover:border-occp-primary/20"
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{SCOPE_ICONS[s.id]}</span>
                <span
                  className={`font-mono text-xs font-bold ${
                    scope === s.id ? "text-occp-primary" : "text-[var(--text)]"
                  }`}
                >
                  {s.label}
                </span>
              </div>
              <p className="text-[11px] text-[var(--text-muted)] font-mono leading-relaxed">
                {s.desc}
              </p>
              {scope === s.id && (
                <div className="mt-2 flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-occp-primary animate-pulse" />
                  <span className="font-pixel text-[9px] text-occp-primary">SELECTED</span>
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
