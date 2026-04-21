"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useHotkeys } from "react-hotkeys-hook";
import {
  LayoutDashboard,
  Activity,
  Users,
  FileText,
  Settings,
  Shield,
  MessageSquare,
  Zap,
  Sun,
  Moon,
  Globe,
  LogOut,
  Play,
  AlertOctagon,
} from "lucide-react";
import { useTheme } from "next-themes";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";

/**
 * OCCP Global Command Palette
 *
 * Trigger: Cmd+K / Ctrl+K
 * 32 actions organized in 7 groups per .planning/OCCP_AI_FIRST_UX_2026.md §3
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const { theme, setTheme } = useTheme();

  useHotkeys("mod+k", (e) => {
    e.preventDefault();
    setOpen((v) => !v);
  });

  useHotkeys("mod+j", (e) => {
    e.preventDefault();
    window.dispatchEvent(new CustomEvent("brian:open"));
  });

  const openBrian = React.useCallback(() => {
    window.dispatchEvent(new CustomEvent("brian:open"));
  }, []);

  const runCommand = React.useCallback((fn: () => void) => {
    setOpen(false);
    fn();
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="OCCP Command Palette" description="Search for a command or navigate">
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigate">
          <CommandItem onSelect={() => runCommand(() => router.push("/"))}>
            <LayoutDashboard /> Dashboard <CommandShortcut>G D</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/pipeline"))}>
            <Activity /> Pipeline <CommandShortcut>G P</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/agents"))}>
            <Users /> Agents <CommandShortcut>G A</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/audit"))}>
            <FileText /> Audit <CommandShortcut>G U</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/mcp"))}>
            <Zap /> MCP <CommandShortcut>G M</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/settings"))}>
            <Settings /> Settings <CommandShortcut>G S</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/admin"))}>
            <Shield /> Admin <CommandShortcut>G X</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Brian / AI">
          <CommandItem onSelect={() => runCommand(openBrian)}>
            <MessageSquare /> Ask Brian... <CommandShortcut>⌘J</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Generate widget — stub"))}>
            <Zap /> Generate widget from text
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Summarize 24h — stub"))}>
            <FileText /> Summarize last 24h
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Explain error — stub"))}>
            <AlertOctagon /> Explain this error
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Regenerate — stub"))}>
            <Play /> Regenerate last response
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Switch model — stub"))}>
            <Zap /> Switch model (Opus / Sonnet / Haiku)
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Job / Pipeline">
          <CommandItem onSelect={() => runCommand(() => alert("Run VAP — stub"))}>
            <Play /> Run VAP pipeline...
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Cancel job — stub"))}>
            Cancel job
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Retry — stub"))}>
            Retry failed job
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("View logs — stub"))}>
            <FileText /> View job logs
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Export report — stub"))}>
            Export job report
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="HITL / Approvals">
          <CommandItem onSelect={() => runCommand(() => alert("Approval queue — stub"))}>
            Open approval queue <CommandShortcut>A</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Approve — stub"))}>
            Approve pending
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Reject — stub"))}>
            Reject with reason
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Auto-approve — stub"))}>
            Set auto-approve threshold
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Safety">
          <CommandItem onSelect={() => runCommand(() => alert("KILL SWITCH 2-op — stub"))} className="text-red-500">
            <AlertOctagon /> KILL SWITCH (2-op) <CommandShortcut>⌘⇧K</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Degraded mode — stub"))}>
            Degraded mode ON/OFF <CommandShortcut>⌘⇧D</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Rollback — stub"))}>
            Rollback to snapshot
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="System">
          <CommandItem onSelect={() => runCommand(() => setTheme(theme === "dark" ? "light" : "dark"))}>
            {theme === "dark" ? <Sun /> : <Moon />} Toggle theme <CommandShortcut>⌘⇧T</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Language — stub"))}>
            <Globe /> Change language (6 locales)
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => alert("Shortcuts help — stub"))}>
            Keyboard shortcuts <CommandShortcut>⌘/</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/login"))}>
            <LogOut /> Logout
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
