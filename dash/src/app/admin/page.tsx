"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";
import { AdminGuard } from "@/components/admin-guard";

export default function AdminPage() {
  const t = useT();

  const cards = [
    {
      href: "/admin/users",
      title: t.admin.usersTitle,
      desc: t.admin.usersSubtitle,
      icon: "👤",
    },
    {
      href: "/admin/stats",
      title: t.admin.statsTitle,
      desc: t.admin.statsSubtitle,
      icon: "📊",
    },
  ];

  return (
    <AdminGuard>
      <div className="space-y-8">
        <div>
          <h1 className="font-pixel text-sm tracking-wide">
            <span className="text-occp-primary text-glow">{t.admin.title}</span>
          </h1>
          <p className="text-sm text-[var(--text-muted)] font-mono mt-1">
            {t.admin.subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {cards.map((card) => (
            <Link
              key={card.href}
              href={card.href}
              className="retro-card p-6 hover:border-occp-primary/40 transition-colors group"
            >
              <div className="flex items-start gap-4">
                <span className="text-2xl">{card.icon}</span>
                <div>
                  <h2 className="font-pixel text-[11px] text-occp-primary tracking-wider group-hover:text-glow">
                    {card.title}
                  </h2>
                  <p className="text-sm text-[var(--text-muted)] font-mono mt-1">
                    {card.desc}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </AdminGuard>
  );
}
