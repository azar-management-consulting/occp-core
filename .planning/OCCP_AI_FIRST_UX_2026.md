# OCCP AI-First UX 2026

**Dátum:** 2026-04-20 · Scope: automation-first, "Brian megcsinálja" UX

---

## §1 Executive — 5 AI-First pillar

1. **Chat-as-primary, forms-as-fallback** (ChatGPT/Claude.ai normalized)
2. **Streaming everywhere** ("response that waits feels broken")
3. **Propose → Commit (HITL)** — AI soha nem executál direktben high-risk action-t
4. **Keyboard-first + Cmd+K** (Linear/Raycast/Vercel)
5. **Generative UI on-demand** (v0 production-ready 2026-Q1)

---

## §2 "Chat with Brian" — OCCP egyedi advantage

**State:** Brian orchestrator már létezik + Telegram bot él.

**Dashboard integráció:**
- **Right-side slide-in drawer** (Claude.ai artifact) — `Cmd+J` mindig elérhető
- **Shared conversation state** Telegram ↔ Dashboard (thread ID sync)
- **Streaming tokens** Vercel AI SDK 3.0+ `useChat` hook
- **Tool-call cards** inline (Anthropic pattern) — approve/reject inline
- **Citation badges** (Perplexity) — EU AI Act Art.14 audit-ready

**Unique advantage:** Brian már működik — a dashboard **vizuális control plane**, nem replacement. Cross-channel surface (Telegram + web).

---

## §3 Command palette — 32 action

**Library:** `cmdk` (Paco) — Linear/Raycast standard. Fuzzy search + a11y built-in.

**Trigger:** `Cmd+K` (global).

**Groups:**
- **Nav (7):** Dashboard / Jobs / Logs / Agents / Policies / Audit / Settings
- **Brian/AI (6):** Ask Brian... / Generate widget / Summarize 24h / Explain error / Regenerate / Switch model
- **Job/Pipeline (5):** Run VAP / Cancel job / Retry / View logs / Export report
- **HITL (4):** Approval queue / Approve pending / Reject / Auto-approve threshold
- **Safety (3):** KILL SWITCH 2-op / Degraded mode / Rollback
- **Search (3):** Logs / Audit / Policy rules
- **System (4):** Theme / Language / Shortcuts / Logout

**Total: 32.** Nested nav (Raycast): `→` deeper, `←` back.

---

## §4 Streaming UI — VAP stage élőben

1. **Token-level streaming** Brian response SSE/WebSocket (Vercel AI SDK `useChat` + `streamText`)
2. **Stage progress bar** VAP (ingest→normalize→classify→act→audit) — checkpoint card timestamp + status
3. **Skeleton loaders** — "-40% perceived load time vs spinner"
4. **Optimistic UI** job submit → azonnal "pending"
5. **Markdown buffering** — defer code block render until closing fence

**OCCP specific:** pipeline.py stages → WebSocket events (`stage_started/completed/failed`). Confidence indicator per stage.

---

## §5 HITL — Propose → Commit + Approval Queue

**Core:** "AI proposes, human commits" (LangChain/MSFT/Oracle 2026).

**Confidence routing:**
- Threshold 0.85: alatta → queue, felette → auto
- Capacity: 100 review/day / 1000 gen/day → max 10% routing rate

**Approval Queue UI:**
- **Left:** pending items sorted by risk
- **Center:** detail card — action, params, reasoning, confidence %, policy triggered
- **Right:** audit context — similar past decisions, predicted impact
- **Hotkeys:** Approve `⌘↩` / Reject `⌘⌫` / Modify+approve `⌘E` / Escalate `⌘⇧E`
- **2-op kill switch:** delete, prod deploy require 2 independent approvals (Figma/Linear presence)

**EU AI Act Art.14 compliance:** HITL decision audit log (spec in EU_AI_ACT_ART14_COMPLIANCE_MAPPING.md).

---

## §6 Generative UI pilot — "Write a widget for X"

**Stack:** Vercel v0 API production-ready 2026-Q1 (shadcn/ui + Tailwind output).

**OCCP rollout (3 level):**
- **V1 (safe):** gallery — pre-built widgets (VAP runs today, failed jobs heatmap, agent latency)
- **V2 (gen, sandboxed):** "Create widget showing last 7 days kill-switch by hour" → Brian generates React+Recharts → **sandbox iframe preview** → approve → save
- **V3 (full compose-mode):** multiple widgets at once

**Risk mitigation:** sandboxed iframe CSP strict, read-only API access. Start V1+V2 — "10/10 wow" without V3 risk.

---

## §7 Keyboard shortcuts — 42 hotkeys

**Global:**
| Key | Action |
|---|---|
| `Cmd+K` | Command palette |
| `Cmd+J` | Open Brian chat drawer |
| `Cmd+/` | Shortcuts help |
| `Cmd+Shift+P` | Command palette (alt) |
| `Esc` | Close modal/drawer |
| `?` | Quick help |
| `G D` | Dashboard | `G J` | Jobs | `G A` | Agents | `G L` | Logs | `G P` | Policies | `G U` | Audit | `G S` | Settings |
| `N` | New job |
| `A` | Approvals queue |
| `R` | Refresh |
| `/` | Focus search |

**Brian chat:** `Cmd+Enter` Send · `Cmd+↑` Edit last · `Cmd+R` Regenerate · `Cmd+Shift+C` Copy · `Cmd+Shift+N` New conv · `Cmd+Shift+M` Switch model

**Approval queue:** `J/K` next/prev · `Cmd+↵` Approve · `Cmd+⌫` Reject · `Cmd+E` Modify+approve · `Cmd+Shift+E` Escalate

**Safety:** `Cmd+Shift+K` Kill switch · `Cmd+Shift+D` Degraded · `Cmd+Shift+R` Rollback

**Table nav:** `↑/↓` or `j/k` · `x` select · `Shift+x` range · `Enter` open

**Total 42**, all documented `Cmd+/` help overlay (Radix Dialog + `<kbd>`).

---

## §8 Empty state + first-run tour

**Zero-state pattern (2026):** blank canvas → AI suggests first action.

**OCCP flow:**
1. **Welcome card:** "Mit szeretnél automatizálni ma?" + 3 Brian-generated prompts (NODE_REGISTRY context). HU default, `next-intl` switch.
2. **Template gallery:** 6-8 one-click scaffolds — "Email to task", "Slack alert on failure", "Daily VAP summary", "WP content publish" (azar.hu context)
3. **Guided tour (Shepherd.js alt: custom):** max 5 step, skippable. Steps: Cmd+K, Chat drawer, Approval queue, Kill switch, Settings
4. **"Detect from context":** Brian reads 7-day logs → proposes 3 automations user adopt (ambient intelligence)
5. **Progressive disclosure:** advanced features (HITL policies, custom agents) only after 5+ jobs run

**Per-page empty:**
- Jobs empty → "Brian hasn't run anything. [Run first pipeline] or [Ask Brian what to do]"
- Logs empty → "No events. Your system is healthy." (don't apologize)

---

## §9 Mobile strategy — Read-only + Approvals

**Recommendation: READ-ONLY + APPROVALS.**

**Rationale:**
- Full admin mobile = risk (kill switch, policy edit, agent config → keyboard-heavy)
- **Approvals mobile = killer use case:** oncall push → 2 tap → approve/reject
- Industry: Linear iOS = read+triage, PagerDuty mobile = approve/ack only

**Scope:**
- **PWA** service worker — offline last-synced, install as native, Web Push API
- **Mobile views:** Dashboard (read), Jobs list/detail, Approval queue (no modify), Chat with Brian (full), Logs (search+read)
- **Disabled:** Policy editor, agent config, kill switch, generative UI compose, settings beyond profile/theme
- **Push:** approval pending, job failed, kill switch activated by other operator

---

## §10 A11y + I18n targets

**A11y: WCAG 2.2 AA** (AAA ahol lehet)
- **Stack:** Radix Primitives (WAI-ARIA built-in)
- **Contrast:** 4.5:1 normal, 3:1 large — Tailwind palette audit
- **CI:** axe-core fail build on violation, manual VoiceOver+NVDA before release
- **Focus management:** Radix default traps + returns
- **Reduced motion:** `prefers-reduced-motion` — disable streaming cursor, skeleton shimmer
- **AI-specific:** `aria-live="polite"` streaming tokens · textual alt confidence ("High confidence 92%" not green dot) · semantic `<article>` tool-call cards

**I18n: 6 locale (HU primary, NODE_REGISTRY match)**
- **Stack:** `next-intl` v4+ (2KB bundle, Server Component native, Next.js 16 compat, SWC plugin)
- **ICU message syntax** — plurals, gender, rich text (critical for HU complex pluralization)
- **Routing:** `/hu/...`, `/en/...` middleware
- **Runtime switch:** `Cmd+K → "Change language"` → `router.replace` new locale (no reload)
- **Brian responses:** LLM system prompt `"Respond in {locale}"` — Telegram bot already does, dashboard parity

---

## Confidence

| Claim | Level |
|---|---|
| cmdk powers Linear/Raycast | CONFIRMED |
| Sonner 31.2M weekly vs react-hot-toast 3.5M | CONFIRMED |
| v0 production-ready 2026-Q1 | CONFIRMED |
| HITL propose→commit pattern | CONFIRMED |
| Streaming baseline expectation | CONFIRMED |
| next-intl v4 + Next.js 16 compat | CONFIRMED |
| Radix WCAG 2.2 AAA | LIKELY |
| Skeleton -40% perceived load | LIKELY (study unverified) |
| Linear Copilot 2026-Q1 features | UNVERIFIED |

---

## Források (2026-04-20)

- [patterns.dev AI UI](https://www.patterns.dev/react/ai-ui-patterns/)
- [thefrontkit AI Chat Best Practices](https://thefrontkit.com/blogs/ai-chat-ui-best-practices)
- [uxpatterns.dev AI Chat](https://uxpatterns.dev/patterns/ai-intelligence/ai-chat)
- [groovyweb 12 UI/UX Trends AI Apps 2026](https://www.groovyweb.co/blog/ui-ux-design-trends-ai-apps-2026)
- [Vercel v0 Generative UI](https://vercel.com/blog/announcing-v0-generative-ui) · [AI SDK 3.0 Gen UI](https://vercel.com/blog/ai-sdk-3-generative-ui)
- [v0 Complete Guide 2026 — NxCode](https://www.nxcode.io/resources/news/v0-by-vercel-complete-guide-2026)
- [cmdk](https://cmdk.paco.me/) · [shadcn Command](https://www.shadcn.io/ui/command)
- [Liveblocks Multiplayer](https://liveblocks.io/multiplayer-editing)
- [MyEngineeringPath HITL 2026](https://myengineeringpath.dev/genai-engineer/human-in-the-loop/)
- [LangChain HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Temporal HITL Python](https://docs.temporal.io/ai-cookbook/human-in-the-loop-python)
- [Radix a11y](https://www.radix-ui.com/primitives/docs/overview/accessibility)
- [next-intl v4](https://v4.next-intl.dev/) · [next-intl Guide 2026](https://intlpull.com/blog/next-intl-complete-guide-2026)

---
*v1.0 · 2026-04-20 · deep-research agent output*
