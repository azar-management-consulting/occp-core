"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { UserListItem } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { AdminGuard } from "@/components/admin-guard";

export default function AdminUsersPage() {
  const t = useT();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await api.listUsers();
        setUsers(data.users);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load users");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const roleBadge = (role: string) => {
    const colors: Record<string, string> = {
      system_admin: "text-occp-danger border-occp-danger/40",
      org_admin: "text-occp-accent border-occp-accent/40",
      operator: "text-occp-primary border-occp-primary/40",
      viewer: "text-[var(--text-muted)] border-[var(--muted)]",
    };
    return colors[role] || colors.viewer;
  };

  return (
    <AdminGuard>
      <div className="space-y-8">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">{t.admin.usersTitle}</span>
          </h1>
          <p className="text-sm text-[var(--text-muted)] font-mono mt-1">
            {t.admin.usersSubtitle}
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

        {!loading && !error && users.length === 0 && (
          <div className="retro-card p-8 text-center">
            <p className="font-pixel text-[11px] text-[var(--text-muted)]">{t.admin.noUsers}</p>
          </div>
        )}

        {!loading && !error && users.length > 0 && (
          <div className="retro-card overflow-hidden">
            <table className="w-full text-sm font-mono">
              <thead>
                <tr className="border-b border-[var(--muted)] bg-occp-surface/50">
                  <th className="text-left px-4 py-3 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                    {t.admin.username}
                  </th>
                  <th className="text-left px-4 py-3 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                    {t.admin.role}
                  </th>
                  <th className="text-left px-4 py-3 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                    {t.admin.status}
                  </th>
                  <th className="text-left px-4 py-3 font-pixel text-[10px] text-[var(--text-muted)] tracking-wider">
                    {t.admin.joined}
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-[var(--muted)]/30 hover:bg-white/5 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className="text-[var(--text)]">{u.username}</span>
                      {u.display_name && u.display_name !== u.username && (
                        <span className="text-[var(--text-muted)] ml-2 text-xs">
                          ({u.display_name})
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded border text-[10px] font-pixel tracking-wider ${roleBadge(u.role)}`}
                      >
                        {u.role.toUpperCase().replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <span className="text-occp-success">&#9679; {t.admin.active}</span>
                      ) : (
                        <span className="text-occp-danger">&#9679; {t.admin.inactive}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-muted)] text-xs">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminGuard>
  );
}
