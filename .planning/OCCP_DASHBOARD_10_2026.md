# OCCP Dashboard 10/10 — 2026-Q2 Modernization Blueprint

**Dátum:** 2026-04-20 · Scope: `dash.occp.ai` (Next.js 15 + React 19)

---

## §1 Executive — Current vs 10/10 gap

**Verified current state** (`dash/package.json`, `dash/src/app/page.tsx`):
- Next.js `^15.2.0` + React `^19.0.0` + Tailwind v4 + `lucide-react` — **modern base**
- **Mindössze 4 runtime dep** — 0 UI lib, 0 command palette, 0 charts, 0 tables
- 21 page létezik
- Custom "retro C64" esztétika (`retro-card`, `font-pixel`, `crt-glow`) — **signature, de enterprise adoption blocker**
- `useEffect` + raw `fetch` (nincs SWR, nincs cache, nincs revalidation)
- **Hiányzik:** command palette, keyboard shortcuts, real-time, dark-mode toggle, feature flags UI, impersonation

**Top 5 move:**
1. shadcn/ui (own-the-code, Tailwind v4 + React 19 ready) + **Tremor** charts
2. **cmdk** command palette (Linear-parity)
3. **TanStack Table v8** + shadcn data-table minden listán
4. **SSE** live stream Brain-ből (Pipeline/Audit/Agents)
5. Design-token refactor (semantic OKLCH, dark-first)

---

## §2 Component library — shadcn/ui WINS

| Criterion | shadcn/ui | Catalyst | Tremor |
|---|---|---|---|
| License | MIT free | Paid ($299+) | MIT (post-Vercel) |
| Ownership | Copy-code | Copy-code | Copy-code |
| GitHub stars | **80k+** de-facto | N/A | 16k+ |
| React 19 + Tailwind v4 | ✅ | Partial | ✅ |
| Data-table | **Kiváló** (TanStack) | Basic | N/A |
| Charts | No | No | **35 comp, 300 blocks** |

**Verdikt:** `shadcn/ui` primary + `Tremor` charts + meglévő `lucide-react`. Skip Catalyst (paid), skip Aceternity/Magic UI (marketing-heavy).

```bash
npx shadcn@latest init     # Tailwind v4 + React 19 preset
npx shadcn@latest add button card dialog command data-table dropdown-menu sonner sheet tabs
npm i @tremor/react recharts
```

---

## §3 Command palette — `cmdk`

**Pick:** `cmdk` by @pacocoursey — **12,153 stars, 7.38M weekly DL**. Linear UX benchmark.

**Implementáció (4 óra):**
1. `shadcn add command`
2. `<CommandMenu/>` global `app/layout.tsx`-ben
3. `Cmd+K` / `Ctrl+K` hotkey
4. Actions registry `/lib/commands.ts`:
   - **Navigate:** Agents, Pipeline, Audit, MCP, Settings, Admin
   - **Quick:** New Task, Re-run, Create API Key, Toggle Dark Mode, Logout
   - **Search:** tasks, agents, audit (server-side `/api/search?q=`)
5. Fuzzy score: built-in `command-score`
6. Vim bindings: `j/k` nav

---

## §4 7 core views redesign

**Home (`/`)** — C64 hero ki:
- KPI grid (4): Active Agents · Tasks 24h · Token Spend $ · SLO Burn
- `<AreaChart>` (Tremor) 7d task-rate
- Live activity feed (last 20, SSE)
- Quick actions row (New Task, Invite User, View Audit)

**Pipeline (`/pipeline`)** — Gantt + Live:
- Top: real-time running tasks (SSE)
- Middle: VAP stages timeline (horizontal Gantt)
- Bottom: TanStack Table historical runs + faceted filter

**Agents (`/agents`)** — master-detail split:
- List: data-table (name, status-badge, last-seen, tokens, cost)
- Detail tabs: Overview | Sessions | Tools | Logs | Config
- Trace waterfall (Phoenix pattern, 10 span kinds: CHAIN/LLM/TOOL/RETRIEVER)

**Audit (`/audit`)** — searchable timeline:
- Left: filter sidebar (actor, event-type, time-range, risk)
- Right: virtualized timeline (react-virtuoso) expandable rows
- Export: CSV / JSONL

**MCP (`/mcp`)**:
- Server cards grid (status-dot, tool-count, last-ping)
- Click → Sheet: tool list (name, schema, last-call, avg-latency)
- "Test tool" inline form (params → JSON preview)

**Settings (`/settings`)** tabs:
- Profile | Security (**Passkeys**) | Tokens | LLM Providers | Notifications | Danger Zone

**Admin (`/admin`)**:
- Users table + row-action `Impersonate` → banner `Viewing as X [Exit]`
- Stats: org-wide token spend, user growth, top-10 expensive agents
- Feature flags: toggle grid (shadcn `Switch`)

---

## §5 Dark-mode design tokens (Linear-inspired OKLCH)

**Principle (Linear refresh 2026-03):** build **paired OKLCH** scales ground-up, ne adapt light→dark.

```css
/* app/globals.css — Tailwind v4 @theme */
@theme {
  --color-surface-base: oklch(18% 0 0);
  --color-surface-raised: oklch(22% 0 0);
  --color-surface-overlay: oklch(26% 0 0);
  --color-border-subtle: oklch(30% 0 0);
  --color-text-primary: oklch(96% 0 0);
  --color-text-muted: oklch(68% 0 0);
  --color-accent: oklch(65% 0.19 265);      /* Linear indigo */
  --color-success: oklch(70% 0.17 145);
  --color-danger: oklch(65% 0.22 25);
}
```

**Migráció:** alias-ekkel párhuzamosan (`occp-primary` stb.), majd `retro-card/crt-glow` → `/legacy`.

---

## §6 Keyboard shortcut matrix

| Key | Action |
|---|---|
| `Cmd+K` | Command palette |
| `G H` | Go Home |
| `G P` | Go Pipeline |
| `G A` | Go Agents |
| `G U` | Go Admin Users |
| `C` | Create new task (context) |
| `/` | Focus search |
| `?` | Help overlay |
| `Esc` | Close dialog |
| `.` | Quick menu |
| `Cmd+Shift+D` | Toggle dark mode |
| `j/k` | Next/prev lists |
| `Cmd+Enter` | Submit form |

Impl: `react-hotkeys-hook` (3.5k stars, React 19).

---

## §7 Real-time subscriptions to Brain

**Pick:** **SSE over WebSocket** — unidirectional server→client, native `EventSource`, no WS auth-token pain.

**Brain FastAPI új endpointok:**
- `GET /api/stream/tasks` — task state changes
- `GET /api/stream/audit` — új audit events
- `GET /api/stream/agents` — agent heartbeats
- `GET /api/stream/logs?task_id=...` — per-task log tail

**Client:**
```ts
// lib/hooks/use-sse.ts
const events = useSSE('/api/stream/tasks');
// SWR initial snapshot + SSE live delta
```

**Szabály:** ne rerender minden event-re — throttle 100ms, refs high-frequency, leaf komponensek.

**SWR:** `revalidateOnFocus: true` admin view-knak, `false` streaming view-knak (SSE = truth).

---

## §8 Mobile stratégia

**Stance:** "mobile is read-only" (Linear/Vercel/Stripe minta).
- Breakpoint: `md:` (768px) = desktop feature
- <768px: hide command palette gomb (shortcut marad), bottom-nav sidebar, tables → card-list
- No impersonation, no task creation (role flag)
- Mobile filters: shadcn `Sheet` drawer

---

## §9 Empty state + onboarding tour

**Empty state minden lista view:**
1. Icon (lucide)
2. H3 "No {entity} yet"
3. One-sentence why + CTA button
4. Opt. doc link

**Tour pick:** **Shepherd.js** (22k+ stars, React integration). Reject: Driver.js (no React), React-Joyride (inaktív).
Alternatíva: custom shadcn `Popover` + `HoverCard` — 200 LoC, teljes control.

**Flow (7 step, first login):** Welcome → Sidebar → `Cmd+K` demo → Create task → Agent panel → Audit → Settings.
Gate: `user.has_completed_tour`.

---

## §10 Migration plan — 10 lépés, no big-bang

1. **Branch** `feat/dash-10of10-2026` + flag `NEXT_PUBLIC_DASH_V2=true`
2. **Install** shadcn init + Tremor + cmdk (1d)
3. **Design tokens** OKLCH `@theme` + aliasok (2d)
4. **Home page** rewrite pilot (`app/(v2)/page.tsx` parallel route) (3d)
5. **Command palette** global (always-on, low risk) (1d)
6. **Data-table** generic wrapper, Admin/Users first (3d)
7. **SSE hook + Brain endpoints** Pipeline retrofit (4d)
8. **Dark-mode toggle** + settings persist (1d)
9. **Page-by-page:** Agents → Audit → MCP → Settings → Admin (3 hét, 2d/oldal)
10. **Legacy retire** — `retro-*` styles delete, flag default-on, parallel routes remove (1d)

**Total:** ~5 hét 1 eng, ~3 hét 2 eng. **Zero downtime, zero regression** (flag-gated).

**Risk:**
- R1: Tailwind v4 + shadcn preset collision → test branch, docs CONFIRMED
- R2: SSE nginx buffering → `X-Accel-Buffering: no` + `text/event-stream`
- R3: React 19 breaking deps → pin + `overrides`

---

## Források (2026-04-20)

- [shadcn/ui React 19](https://ui.shadcn.com/docs/react-19) · [Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4)
- [shadcn visual builder InfoQ](https://www.infoq.com/news/2026/02/shadcn-ui-builder/)
- [Vercel acquires Tremor](https://vercel.com/blog/vercel-acquires-tremor) · [Tremor](https://www.tremor.so/)
- [cmdk GitHub](https://github.com/pacocoursey/cmdk)
- [cmdk vs kbar npmtrends](https://npmtrends.com/cmdk-vs-kbar-vs-scoutbar)
- [Linear Docs](https://linear.app/docs) · [Linear refresh 2026-03](https://linear.app/now/behind-the-latest-design-refresh)
- [OKLCH dark-mode fix](https://chyshkala.com/blog/why-linear-design-systems-break-in-dark-mode-and-how-to-fix-them)
- [TanStack Table](https://tanstack.com/table/v8/docs/guide/pagination)
- [shadcn data-table example](https://data-table.openstatus.dev/)
- [Supabase Realtime](https://supabase.com/docs/guides/realtime)
- [Arize Phoenix](https://github.com/Arize-ai/phoenix)
- [SSE vs WS Next.js](https://hackernoon.com/streaming-in-nextjs-15-websockets-vs-server-sent-events)
- [SWR Next.js](https://swr.vercel.app/docs/with-nextjs)
- [Clerk passkeys](https://clerk.com/articles/react-authentication-from-protected-routes-to-passkeys)
- [Best React onboarding 2026](https://onboardjs.com/blog/5-best-react-onboarding-libraries-in-2025-compared)

---
*v1.0 · 2026-04-20 · deep-research agent output*
