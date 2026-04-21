"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Send, Sparkles } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Role = "user" | "assistant";

interface Message {
  id: string;
  role: Role;
  content: string;
  streaming?: boolean;
}

const BRIAN_OPEN_EVENT = "brian:open";
const API_BASE =
  process.env.NEXT_PUBLIC_OCCP_API_URL ?? "https://api.occp.ai";
const API_KEY_STORAGE = "occp_api_key";

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createSessionId(): string {
  return `sess_${createId()}`;
}

/**
 * Parse a raw SSE buffer into discrete event payloads.
 * Returns [events, remainder] so partial trailing events stay buffered.
 */
function parseSseBuffer(buffer: string): [string[], string] {
  const events: string[] = [];
  let remainder = buffer;

  while (true) {
    const boundary = remainder.indexOf("\n\n");
    if (boundary === -1) break;
    const rawEvent = remainder.slice(0, boundary);
    remainder = remainder.slice(boundary + 2);

    const dataLines = rawEvent
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^\s/, ""));
    if (dataLines.length === 0) continue;
    events.push(dataLines.join("\n"));
  }

  return [events, remainder];
}

export function BrianDrawer() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [online, setOnline] = React.useState(true);

  const sessionIdRef = React.useRef<string>(createSessionId());
  const abortRef = React.useRef<AbortController | null>(null);
  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

  // Open via custom window event
  React.useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener(BRIAN_OPEN_EVENT, handler);
    return () => window.removeEventListener(BRIAN_OPEN_EVENT, handler);
  }, []);

  // Track browser online state
  React.useEffect(() => {
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    setOnline(typeof navigator !== "undefined" ? navigator.onLine : true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  // Abort any in-flight request when drawer closes or unmounts
  React.useEffect(() => {
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setSending(false);
    }
  }, [open]);

  React.useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Auto-scroll on new chunk
  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Focus textarea on open
  React.useEffect(() => {
    if (open) {
      const t = window.setTimeout(() => textareaRef.current?.focus(), 120);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  const appendAssistantToken = React.useCallback(
    (assistantId: string, token: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: m.content + token } : m,
        ),
      );
    },
    [],
  );

  const finalizeAssistant = React.useCallback((assistantId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === assistantId ? { ...m, streaming: false } : m,
      ),
    );
  }, []);

  const sendMessage = React.useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || sending) return;

      const apiKey =
        typeof window !== "undefined"
          ? window.localStorage.getItem(API_KEY_STORAGE)
          : null;
      if (!apiKey) {
        router.push("/login");
        return;
      }

      const userMsg: Message = {
        id: createId(),
        role: "user",
        content: text,
      };
      const assistantMsg: Message = {
        id: createId(),
        role: "assistant",
        content: "",
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInput("");
      setSending(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_BASE}/api/v1/brain/message`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            message: text,
            session_id: sessionIdRef.current,
          }),
          signal: controller.signal,
        });

        if (res.status === 401) {
          router.push("/login");
          return;
        }
        if (!res.ok || !res.body) {
          throw new Error(`Brain API error: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const [events, remainder] = parseSseBuffer(buffer);
          buffer = remainder;

          for (const evt of events) {
            if (evt === "[DONE]") {
              finalizeAssistant(assistantMsg.id);
              return;
            }
            let token = evt;
            try {
              const parsed: unknown = JSON.parse(evt);
              if (typeof parsed === "string") {
                token = parsed;
              } else if (
                parsed &&
                typeof parsed === "object" &&
                "token" in parsed &&
                typeof (parsed as { token: unknown }).token === "string"
              ) {
                token = (parsed as { token: string }).token;
              } else if (
                parsed &&
                typeof parsed === "object" &&
                "delta" in parsed &&
                typeof (parsed as { delta: unknown }).delta === "string"
              ) {
                token = (parsed as { delta: string }).delta;
              } else if (
                parsed &&
                typeof parsed === "object" &&
                "content" in parsed &&
                typeof (parsed as { content: unknown }).content === "string"
              ) {
                token = (parsed as { content: string }).content;
              }
            } catch {
              // Raw text token, keep as-is
            }
            if (token) {
              appendAssistantToken(assistantMsg.id, token);
            }
          }
        }

        finalizeAssistant(assistantMsg.id);
      } catch (err) {
        if ((err as { name?: string }).name === "AbortError") {
          return;
        }
        console.error("[BrianDrawer] stream error", err);
        toast.error("Brian is unreachable. Check your connection and try again.");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, streaming: false, content: m.content || "(no response)" }
              : m,
          ),
        );
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setSending(false);
      }
    },
    [appendAssistantToken, finalizeAssistant, router, sending],
  );

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void sendMessage(input);
      }
    },
    [input, sendMessage],
  );

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent
        side="right"
        className="flex flex-col p-0 sm:max-w-md lg:max-w-[420px]"
        hideCloseButton
      >
        <SheetHeader className="flex flex-row items-center justify-between space-y-0 border-b border-[var(--border-subtle,#27272a)] px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--accent,#6366f1)]/10">
              <Sparkles className="h-4 w-4 text-[var(--accent,#6366f1)]" />
            </div>
            <div className="flex flex-col items-start">
              <SheetTitle className="text-base">Brian the Brain</SheetTitle>
              <SheetDescription className="flex items-center gap-1.5 text-xs">
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5 rounded-full",
                    online ? "bg-emerald-500" : "bg-zinc-500",
                  )}
                  aria-hidden
                />
                {online ? "Online" : "Offline"}
              </SheetDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setOpen(false)}
            aria-label="Close Brian drawer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </Button>
        </SheetHeader>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-5 py-4"
          role="log"
          aria-live="polite"
        >
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent,#6366f1)]/10">
                <Sparkles className="h-5 w-5 text-[var(--accent,#6366f1)]" />
              </div>
              <p className="max-w-[260px] text-sm text-[var(--fg-muted,#a1a1aa)]">
                Ask Brian anything — it&apos;s the OCCP control plane brain.
              </p>
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {messages.map((m) => (
                <li
                  key={m.id}
                  className={cn(
                    "flex flex-col gap-1",
                    m.role === "user" ? "items-end" : "items-start",
                  )}
                >
                  <span className="px-1 text-[10px] uppercase tracking-wider text-[var(--fg-muted,#a1a1aa)]">
                    {m.role === "user" ? "You" : "Brian"}
                  </span>
                  <div
                    className={cn(
                      "max-w-[90%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm",
                      m.role === "user"
                        ? "bg-[var(--accent,#6366f1)] text-white"
                        : "bg-[var(--bg-elev-2,#27272a)] text-[var(--fg,#fafafa)]",
                    )}
                  >
                    {m.content}
                    {m.streaming && (
                      <span className="ml-1 inline-block h-3 w-1.5 animate-pulse bg-current align-middle" />
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <form
          className="border-t border-[var(--border-subtle,#27272a)] p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void sendMessage(input);
          }}
        >
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Brian..."
              rows={2}
              className="flex-1 resize-none rounded-md border border-[var(--border-subtle,#27272a)] bg-[var(--bg,#09090b)] px-3 py-2 text-sm text-[var(--fg,#fafafa)] placeholder:text-[var(--fg-muted,#a1a1aa)] focus:outline-none focus:ring-2 focus:ring-[var(--accent,#6366f1)]"
              disabled={sending}
            />
            <Button
              type="submit"
              size="icon"
              disabled={sending || input.trim().length === 0}
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-[var(--fg-muted,#a1a1aa)]">
            Enter to send, Shift+Enter for newline
          </p>
        </form>
      </SheetContent>
    </Sheet>
  );
}
