"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AdminStatsData } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { AdminGuard } from "@/components/admin-guard";

export default function AdminStatsPage() {
  const t = useT();
  const [stats, setStats] = useState<AdminStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.adminStats();
        setStats(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load stats");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <AdminGuard>
      <div className="space-y-8">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">{t.admin.statsTitle}</span>
          </h1>
          <p className="text-sm text-[var(--text-muted)] font-mono mt-1">
            {t.admin.statsSubtitle}
          </p>
        </div>

        {loading && (
          <div className="text-center py-12">
            <span className="font-pixel text-[11px] text-[var(--text-muted)] animate-pulse">
              LOADING...
            </span>
          </div>
        )}

        {error && (
          <div className="retro-card border-occp-danger/40 bg-occp-danger/5 p-4">
            <span className="font-pixel text-[11px] text-occp-danger mr-2">?ERROR</span>
            <span className="text-sm text-occp-danger font-mono">{error}</span>
          </div>
        )}

        {!loading && !error && stats && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="retro-card p-5 text-center">
                <p className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider mb-2">
                  {t.admin.totalUsers}
                </p>
                <p className="text-3xl font-mono text-occp-primary text-glow">
                  {stats.users_total}
                </p>
              </div>

              <div className="retro-card p-5 text-center">
                <p className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider mb-2">
                  {t.admin.recentSignups}
                </p>
                <p className="text-3xl font-mono text-occp-accent">
                  {stats.registrations_last_7_days}
                </p>
              </div>

              <div className="retro-card p-5 text-center">
                <p className="font-pixel text-[10px] text-[var(--text-muted)] tracking-wider mb-2">
                  {t.admin.onboardingFunnel}
                </p>
                <div className="flex items-center justify-center gap-3 font-mono text-sm">
                  <span className="text-[var(--text-muted)]">{stats.onboarding_funnel.landing}</span>
                  <span className="text-occp-primary/40">&rarr;</span>
                  <span className="text-occp-accent">{stats.onboarding_funnel.running}</span>
                  <span className="text-occp-primary/40">&rarr;</span>
                  <span className="text-occp-success">{stats.onboarding_funnel.done}</span>
                </div>
              </div>
            </div>

            {/* Roles Breakdown */}
            <div className="retro-card p-5">
              <h2 className="font-pixel text-[11px] text-occp-primary tracking-wider mb-4">
                {t.admin.byRole}
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(stats.users_by_role).map(([role, count]) => (
                  <div
                    key={role}
                    className="bg-occp-surface/50 rounded border border-[var(--muted)]/30 p-3 text-center"
                  >
                    <p className="font-pixel text-[9px] text-[var(--text-muted)] tracking-wider mb-1">
                      {role.toUpperCase().replace("_", " ")}
                    </p>
                    <p className="text-xl font-mono text-[var(--text)]">{count}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* User Activity */}
            {stats.user_activity.length > 0 && (
              <div className="retro-card overflow-hidden">
                <div className="px-4 py-3 border-b border-[var(--muted)] bg-occp-surface/50">
                  <h2 className="font-pixel text-[11px] text-occp-primary tracking-wider">
                    {t.admin.userActivity}
                  </h2>
                </div>
                <table className="w-full text-sm font-mono">
                  <thead>
                    <tr className="border-b border-[var(--muted)]">
                      <th className="text-left px-4 py-2 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                        {t.admin.username}
                      </th>
                      <th className="text-left px-4 py-2 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                        {t.admin.role}
                      </th>
                      <th className="text-left px-4 py-2 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                        {t.admin.lastSeen}
                      </th>
                      <th className="text-left px-4 py-2 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                        {t.admin.status}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.user_activity.map((ua) => (
                      <tr
                        key={ua.username}
                        className="border-b border-[var(--muted)]/30 hover:bg-white/5 transition-colors"
                      >
                        <td className="px-4 py-2 text-[var(--text)]">{ua.username}</td>
                        <td className="px-4 py-2 text-[var(--text-muted)]">
                          {ua.role.toUpperCase().replace("_", " ")}
                        </td>
                        <td className="px-4 py-2 text-[var(--text-muted)] text-xs">
                          {new Date(ua.last_seen).toLocaleString()}
                        </td>
                        <td className="px-4 py-2">
                          <span className="font-pixel text-[9px] tracking-wider text-occp-accent">
                            {ua.onboarding_state.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </AdminGuard>
  );
}
