/**
 * Dashboard v2 — Settings hub.
 *
 * Four tiles linking to existing settings sub-routes. Deep pages stay on
 * the legacy tree until a v2 replacement ships.
 */
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Settings,
  Brain,
  KeyRound,
  Wrench,
  UserRound,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Tile = {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

/* Mock data — replace with SSE/fetch */
const TILES: Tile[] = [
  {
    href: "/settings/llm",
    title: "LLM providers",
    description: "OpenAI, Anthropic, Ollama — active provider, fallbacks.",
    icon: Brain,
  },
  {
    href: "/settings/tokens",
    title: "API tokens",
    description: "Personal access tokens for CLI + SDK.",
    icon: KeyRound,
  },
  {
    href: "/settings/tools",
    title: "Tool policies",
    description: "Allowlist per agent: bash, python, fs, web, ui.",
    icon: Wrench,
  },
  {
    href: "/settings/profile",
    title: "Profile",
    description: "Display name, email, preferred language.",
    icon: UserRound,
  },
];

export default function SettingsV2Page() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          <Settings className="inline-block mr-2 -mt-1" /> Settings
        </h1>
        <p className="text-[var(--fg-muted,#999)]">
          Configure providers, tokens, tool policies and your profile.
        </p>
      </div>

      {/* Tile grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {TILES.map((t) => {
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              className="group block transition-colors"
            >
              <Card className="h-full group-hover:border-white/40">
                <CardHeader className="flex flex-row items-start gap-4 space-y-0">
                  <Icon className="mt-1 text-[var(--fg-muted,#999)] group-hover:text-white" />
                  <div>
                    <CardTitle className="text-base font-semibold">
                      {t.title}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {t.description}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <span className="text-xs font-mono text-[var(--fg-muted,#999)]">
                    {t.href}
                  </span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
