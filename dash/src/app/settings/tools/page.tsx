"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";

type Role = "viewer" | "operator" | "admin";
type AccessLevel = "allowed" | "blocked" | "elevated";

interface ToolGroup {
  id: string;
  icon: string;
  tools: string[];
  access: Record<Role, { host: AccessLevel; sandbox: AccessLevel }>;
}

const TOOL_GROUPS: ToolGroup[] = [
  {
    id: "runtime",
    icon: "⚙",
    tools: ["bash", "python", "node"],
    access: {
      viewer: { host: "blocked", sandbox: "blocked" },
      operator: { host: "blocked", sandbox: "allowed" },
      admin: { host: "elevated", sandbox: "allowed" },
    },
  },
  {
    id: "filesystem",
    icon: "📁",
    tools: ["read", "write", "glob", "grep"],
    access: {
      viewer: { host: "allowed", sandbox: "allowed" },
      operator: { host: "allowed", sandbox: "allowed" },
      admin: { host: "allowed", sandbox: "allowed" },
    },
  },
  {
    id: "web",
    icon: "🌐",
    tools: ["fetch", "search", "scrape"],
    access: {
      viewer: { host: "allowed", sandbox: "allowed" },
      operator: { host: "allowed", sandbox: "allowed" },
      admin: { host: "allowed", sandbox: "allowed" },
    },
  },
  {
    id: "ui",
    icon: "🖥",
    tools: ["browser", "screenshot", "click"],
    access: {
      viewer: { host: "blocked", sandbox: "blocked" },
      operator: { host: "blocked", sandbox: "allowed" },
      admin: { host: "elevated", sandbox: "allowed" },
    },
  },
];

const ROLES: Role[] = ["viewer", "operator", "admin"];

function AccessBadge({ level, label }: { level: AccessLevel; label: string }) {
  const styles: Record<AccessLevel, string> = {
    allowed: "bg-occp-success/10 text-occp-success border-occp-success/20",
    blocked: "bg-occp-danger/10 text-occp-danger border-occp-danger/20",
    elevated: "bg-occp-warning/10 text-occp-warning border-occp-warning/20",
  };

  return (
    <span className={`font-pixel text-[8px] px-1.5 py-0.5 rounded border ${styles[level]}`}>
      {label}
    </span>
  );
}

export default function ToolPoliciesPage() {
  const t = useT();

  const accessLabel = (level: AccessLevel): string => {
    switch (level) {
      case "allowed": return t.settings.allowed;
      case "blocked": return t.settings.blocked;
      case "elevated": return t.settings.elevated;
    }
  };

  const roleLabel = (role: Role): string => {
    switch (role) {
      case "viewer": return t.settings.roleViewer;
      case "operator": return t.settings.roleOperator;
      case "admin": return t.settings.roleAdmin;
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <Link
          href="/settings"
          className="text-xs font-mono text-[var(--text-muted)] hover:text-occp-primary transition-colors"
        >
          ← Settings
        </Link>
      </div>

      <div>
        <h1 className="font-pixel text-sm tracking-wide">
          <span className="text-occp-primary text-glow">{t.settings.toolsPageTitle}</span>
        </h1>
        <p className="section-desc mt-2">{t.settings.toolsPageDesc}</p>
      </div>

      {/* Policy Matrix */}
      <div className="space-y-6">
        {TOOL_GROUPS.map((group) => (
          <div key={group.id} className="retro-card p-6 space-y-4 crt-glow">
            {/* Group Header */}
            <div className="flex items-center justify-between">
              <h2 className="font-mono font-bold text-sm">
                <span className="mr-2">{group.icon}</span>
                {group.id.toUpperCase()}
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {group.tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[11px] px-2 py-0.5 rounded font-mono bg-occp-primary/10 text-occp-primary border border-occp-primary/20"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>

            {/* Access Matrix */}
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-occp-muted/20">
                    <th className="text-left py-2 text-[var(--text-muted)] font-normal w-1/4">Role</th>
                    <th className="text-center py-2 text-[var(--text-muted)] font-normal w-1/4">
                      {t.settings.modeHost}
                    </th>
                    <th className="text-center py-2 text-[var(--text-muted)] font-normal w-1/4">
                      {t.settings.modeSandbox}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ROLES.map((role) => (
                    <tr key={role} className="border-b border-occp-muted/10">
                      <td className="py-2.5 font-bold">{roleLabel(role)}</td>
                      <td className="py-2.5 text-center">
                        <AccessBadge level={group.access[role].host} label={accessLabel(group.access[role].host)} />
                      </td>
                      <td className="py-2.5 text-center">
                        <AccessBadge level={group.access[role].sandbox} label={accessLabel(group.access[role].sandbox)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="retro-card p-4">
        <div className="flex flex-wrap gap-4 text-xs font-mono">
          <div className="flex items-center gap-2">
            <AccessBadge level="allowed" label={t.settings.allowed} />
            <span className="text-[var(--text-muted)]">Full access</span>
          </div>
          <div className="flex items-center gap-2">
            <AccessBadge level="elevated" label={t.settings.elevated} />
            <span className="text-[var(--text-muted)]">Requires approval</span>
          </div>
          <div className="flex items-center gap-2">
            <AccessBadge level="blocked" label={t.settings.blocked} />
            <span className="text-[var(--text-muted)]">No access</span>
          </div>
        </div>
      </div>
    </div>
  );
}
