"use client";

/**
 * UserMenu — compact avatar-circle dropdown for the top nav.
 *
 * Avatar: 32x32 circle showing 2 uppercase initials derived from `user`
 * (username string from useAuth — see lib/auth.tsx). Falls back to "?".
 *
 * Dropdown contains:
 *   - email/username label (muted, top)
 *   - separator
 *   - theme radio group: Light / Dark / System (next-themes)
 *   - separator
 *   - logout item (calls useAuth().logout())
 *
 * a11y: trigger has aria-label="Open user menu".
 */

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { ChevronDown, LogOut, Monitor, Moon, Sun } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function getInitials(name: string | null): string {
  if (!name) return "?";
  const trimmed = name.trim();
  if (!trimmed) return "?";
  // If it looks like an email, use the local part.
  const local = trimmed.includes("@") ? trimmed.split("@")[0] : trimmed;
  // Try splitting on common separators for "first.last" / "first_last".
  const parts = local.split(/[._\-\s]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

export function UserMenu(): React.ReactElement | null {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const t = useT();
  const [mounted, setMounted] = useState(false);

  // next-themes is client-only; avoid hydration mismatch on icon swap.
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!user) return null;

  const initials = getInitials(user);
  const currentTheme = mounted ? (theme ?? "system") : "system";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Open user menu"
        className={cn(
          "group inline-flex items-center gap-1.5 rounded-full p-0.5 pr-1.5 outline-none",
          "text-[var(--fg-muted,#a1a1aa)] hover:text-[var(--fg,#fafafa)]",
          "focus-visible:ring-2 focus-visible:ring-[var(--accent,#6366f1)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg,#08081e)]",
          "transition-colors",
        )}
      >
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-full",
            "bg-[var(--bg-elev,#18181b)] border border-[var(--border-subtle,#52525b)]",
            "text-[11px] font-semibold tracking-wide text-[var(--fg,#fafafa)]",
            "group-hover:border-[var(--accent,#6366f1)]/60 transition-colors",
          )}
        >
          {initials}
        </span>
        <ChevronDown
          className="h-3.5 w-3.5 opacity-60 group-hover:opacity-100 transition-opacity"
          aria-hidden="true"
        />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="flex flex-col gap-0.5 py-2">
          <span className="text-[10px] uppercase tracking-wider text-[var(--fg-muted,#a1a1aa)]/80">
            {t.nav.logout ? "Account" : "Account"}
          </span>
          <span className="truncate text-sm font-medium text-[var(--fg,#fafafa)] normal-case">
            {user}
          </span>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuLabel className="text-[10px] uppercase tracking-wider">
          Theme
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={currentTheme}
          onValueChange={(v) => setTheme(v)}
        >
          <DropdownMenuRadioItem value="light" className="gap-2">
            <Sun className="h-4 w-4 opacity-70" aria-hidden="true" />
            <span>Light</span>
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark" className="gap-2">
            <Moon className="h-4 w-4 opacity-70" aria-hidden="true" />
            <span>Dark</span>
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system" className="gap-2">
            <Monitor className="h-4 w-4 opacity-70" aria-hidden="true" />
            <span>System</span>
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            logout();
          }}
          className="gap-2 text-[var(--fg,#fafafa)] focus:bg-[var(--danger,#dc2626)]/15 focus:text-[var(--danger,#dc2626)]"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span>{t.nav.logout}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
