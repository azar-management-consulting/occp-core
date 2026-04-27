"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Lightweight "new task" placeholder dialog. Mounts on any v2 page via
 * `?new=1` query param. Wires to the real task-create API in iter-12; for
 * now it shows a structured stub so the New task / Register agent / Connect
 * server CTAs do something actionable instead of silently navigating.
 *
 * Variants:
 *   - "pipeline": collects a task description, shows what would happen
 *   - "agents":   notes that agent registration uses CLI in v0.10.x
 *   - "mcp":      points to the MCP server connect doc
 */
export type TaskCreateVariant = "pipeline" | "agents" | "mcp";

interface TaskCreateDialogProps {
  variant: TaskCreateVariant;
}

const COPY: Record<
  TaskCreateVariant,
  { title: string; subtitle: string; primary: string; secondary: string; ctaPath: string }
> = {
  pipeline: {
    title: "New Verified Autonomy task",
    subtitle:
      "Tasks are dispatched via the OCCP CLI or REST API. The dashboard form lands in iter-12. Until then, run the CLI command shown below.",
    primary: "Copy CLI command",
    secondary: "Read the docs",
    ctaPath: "https://docs.occp.ai/en/docs/quickstart",
  },
  agents: {
    title: "Register an agent",
    subtitle:
      "Agent registration uses the OCCP CLI in v0.10.x. Run the command, then the agent appears in this list.",
    primary: "Copy CLI command",
    secondary: "Read the agents guide",
    ctaPath: "https://docs.occp.ai/en/docs/concepts/architecture",
  },
  mcp: {
    title: "Connect an MCP server",
    subtitle:
      "MCP servers (Slack, GitHub, Supabase, Cloudflare, Playwright) expose tools to agents. Configure via env vars on the API container, then they appear here.",
    primary: "Copy env var template",
    secondary: "Read the MCP catalog",
    ctaPath: "https://docs.occp.ai/en/docs/mcp-catalog",
  },
};

const CLI_COMMANDS: Record<TaskCreateVariant, string> = {
  pipeline: "occp tasks create --agent eng-core --message 'echo hello'",
  agents: "occp agents register --name my-agent --tools shell,fs --policy default",
  mcp: "OCCP_SLACK_BOT_TOKEN=xoxb-... docker compose restart api",
};

export function TaskCreateDialog({ variant }: TaskCreateDialogProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isOpen = searchParams.get("new") === "1";
  const [copied, setCopied] = useState(false);

  const close = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("new");
    const q = params.toString();
    router.push(q ? `${pathname}?${q}` : pathname);
  };

  // Esc to close.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Reset copied state when dialog opens.
  useEffect(() => {
    if (isOpen) setCopied(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const copy = COPY[variant];
  const cmd = CLI_COMMANDS[variant];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // noop — clipboard may be unavailable in private mode
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="task-dialog-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: "var(--z-bubble)" as unknown as number,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
      }}
    >
      {/* scrim */}
      <button
        type="button"
        aria-label="Close dialog"
        onClick={close}
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--occp-tour-overlay)",
          border: "none",
          padding: 0,
          cursor: "default",
        }}
      />
      <div
        style={{
          position: "relative",
          maxWidth: 520,
          width: "100%",
          background: "var(--occp-bubble-bg)",
          border: "1px solid var(--border-subtle, #52525b)",
          borderRadius: 10,
          padding: 24,
          boxShadow: "var(--occp-bubble-shadow)",
          fontFamily: "var(--font-mono), monospace",
          color: "var(--fg, #fafafa)",
        }}
      >
        <button
          type="button"
          onClick={close}
          aria-label="Close"
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            width: 28,
            height: 28,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            border: "none",
            color: "var(--fg-muted, #a1a1aa)",
            cursor: "pointer",
            borderRadius: 4,
          }}
        >
          <X size={16} aria-hidden />
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <Plus
            size={18}
            aria-hidden
            style={{ color: "var(--occp-bubble-border)", flexShrink: 0 }}
          />
          <h2 id="task-dialog-title" style={{ fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>
            {copy.title}
          </h2>
        </div>

        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--fg-muted, #a1a1aa)",
            lineHeight: 1.5,
            marginBottom: 16,
          }}
        >
          {copy.subtitle}
        </p>

        <pre
          style={{
            background: "var(--bg, #08081e)",
            border: "1px solid var(--border-subtle, #52525b)",
            borderRadius: 6,
            padding: 12,
            fontSize: "0.8125rem",
            overflowX: "auto",
            margin: 0,
            marginBottom: 16,
            color: "var(--fg, #fafafa)",
          }}
        >
          <code>{cmd}</code>
        </pre>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Button variant="ghost" size="sm" asChild>
            <a href={copy.ctaPath} target="_blank" rel="noopener noreferrer">
              {copy.secondary}
            </a>
          </Button>
          <Button size="sm" onClick={handleCopy}>
            {copied ? "Copied!" : copy.primary}
          </Button>
        </div>
      </div>
    </div>
  );
}
