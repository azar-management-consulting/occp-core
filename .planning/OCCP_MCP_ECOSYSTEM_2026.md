# OCCP MCP Ecosystem 2026-Q2

**Dátum:** 2026-04-20 · Scope: MCP spec 2025-11-25 → 2026-Q2 + 10 adoptálandó server OCCP-hez

---

## §1 MCP Spec 2026-Q2 releváns újdonságok

**Timeline:**
- `2025-03-26` — OAuth + Streamable HTTP replaces HTTP+SSE
- `2025-06-18` — OAuth 2.1 + PKCE + RFC 8707 Resource Indicators
- **`2025-11-25` — nagy release (1st birthday):** async Tasks, enhanced Sampling, Elicitation (form + URL), server-side agent loops, Client ID Metadata, Extensions
- `2026-Q1/Q2 draft` — transport scalability, governance, enterprise audit

**OCCP-re releváns:**
1. **Tasks (SEP-1686)** — call-now/fetch-later; OCCP `BrainFlow` async párja
2. **Sampling + Tools bidirectional** — szerverek tool def-et küldhetnek → server-side agent loopok
3. **Elicitation URL mode (új)** — OAuth consent, fizetés out-of-band
4. **OAuth 2.1 + PKCE + RFC 8707** — tokenek audience-scoped
5. **Extensions system** — optional capability negotiation fork nélkül
6. **Transport:** stdio lokális; **Streamable HTTP standard remote**; SSE deprecated

---

## §2 OCCP 14-tool mátrix: build vs buy vs adopt

| OCCP tool | MCP alternatíva | Ajánlás |
|---|---|---|
| `filesystem.read/write/list` | `@modelcontextprotocol/server-filesystem` | **ADOPT** |
| `http.get/post` | `@modelcontextprotocol/server-fetch` | **ADOPT** (markdown conversion ingyen) |
| `brain.status/health` | — | **KEEP** (OCCP-specifikus, `brain-mcp`-ként expose-olható) |
| `wordpress.get_*` | `WordPress/mcp-adapter` (WP 6.9+ core) | **MIGRATE** |
| `wordpress.update_post` | `Automattic/mcp-wordpress-remote` vagy WP adapter | **MIGRATE** (OAuth 2.1) |
| `node.exec/list/status` | — | **KEEP** (Tailscale mesh, nincs hivatalos) |

**Verdikt:** 14-ből 7 (50%) lecserélhető → `adapters/mcp_bridge.py` ~220 sor megszűntethető (34% redukció).

---

## §3 10 bevezetendő MCP server (prioritás)

### P0 — azonnal (production-ready)

| # | Server | GitHub | Verzió | Transport | OCCP use |
|---|---|---|---|---|---|
| 1 | **Supabase MCP** | supabase-community/supabase-mcp | v0.7.0 (2026-03-02), 2.6k★ | Streamable HTTP | OM DB schema + queries, RLS, migrations |
| 2 | **GitHub MCP (official)** | modelcontextprotocol/servers/src/github | 2026-04 | stdio/HTTP | Issues, PRs, workflows |
| 3 | **Playwright MCP (Microsoft)** | microsoft/playwright-mcp | 2026-Q1 hivatalos | stdio | Browser automation (replace Puppeteer) |
| 4 | **Cloudflare Code Mode MCP** | cloudflare/mcp | 2026-04 | Streamable HTTP | 2500+ endpoint, 81% token redukció |
| 5 | **WordPress MCP Adapter** | WordPress/mcp-adapter | 2026-02 (WP 6.9+ core) | HTTP REST | 3 site-hoz (azar/felnottkepzes/magyarorszag) |

### P1 — 2026-Q2/Q3

| # | Server | OCCP use |
|---|---|---|
| 6 | Sequential Thinking | Brain reasoning chains |
| 7 | Memory (knowledge graph) | Cross-session persistence |
| 8 | Fetch | HTTP tool replacement |
| 9 | Git | Local git ops |
| 10 | **Exa** (már config-ban) | Semantic web search, csak aktiválni |

**MCP Apps partners (2026-01-26):** Amplitude, Asana, Box, Canva, Clay, Figma, Hex, monday.com, Slack, Salesforce. OCCP-hez: **Slack** (már config-ban), **Asana** vagy **monday.com** megfontolandó ügyfélkezeléshez.

---

## §4 Saját MCP server tervek

### 4.1 `brain-mcp` (új, build)
- Cél: OCCP Brain tool-jait kiajánlani MCP-ként más klienseknek (Claude Desktop, Cursor, VS Code)
- Transport: Streamable HTTP, port 8765
- Auth: OAuth 2.1 + PKCE, audience `urn:occp:brain`
- SDK: Python `mcp` FastMCP
- **~150 sor** kód

### 4.2 `wp-mcp` — **NE build**
- `WordPress/mcp-adapter` **WP core** 2026-02 óta
- `Automattic/mcp-wordpress-remote` proxy létezik
- OCCP saját `wordpress.*` **deprekálandó**

### 4.3 `mainwp-mcp` (új, build — niche)
- 139 MainWP site (OM projekt) kezelés
- Nincs hivatalos → saját wrapper MainWP REST API-ra
- ~300 sor, nagy érték

---

## §5 Multi-tenant MCP auth (139 site)

**Pattern:**
1. **Gateway pattern** — OCCP Brain frontja MCP gateway (TrueFoundry / saját). Per-user OAuth cache + refresh + org→credentials mapping
2. **Resource Indicators (RFC 8707)** — per-tenant audience: `urn:occp:wp:site-<id>`
3. **Client Credentials Flow** M2M hívások
4. **Role-based tool annotations** (2026 spec): `@RolesAllowed("admin", "editor")`

**Javaslat:** 1 gateway + per-site OAuth cache Redis-ben TTL-lel. 139 site-hoz egy adapter instance nem skálázódik.

---

## §6 `config/mcp-servers.json` bővítés

**Add be (P0):** `supabase`, `playwright` (replace puppeteer), `wordpress-adapter` × 3 site

**Cserélj:**
- `@cloudflare/mcp-server-cloudflare` **deprecated** → `https://mcp.cloudflare.com/mcp` (remote)
- `puppeteer` → `playwright` (Microsoft official)

**Q2 MCP Apps:** `asana`, `linear`, `notion`, `sentry` (mind remote-mcp.com)

**Schema bővítés:** jelenlegi `command/args/env` (stdio) → + `type: "streamable-http", url, headers, oauth`. Precedens: `exa` entry.

---

## §7 MCP Bridge — mit lehet megszüntetni

**Jelenlegi:** `adapters/mcp_bridge.py` 640 sor, 14 tool

**KEEP (~420 sor):**
- MCPBridge dispatcher, policy chain, audit, semaphore — más célokra reusable
- `brain.status`, `brain.health`
- `node.*` (Tailscale)

**DELETE (~220 sor, 34%):**
- `_filesystem_read/write/list` → `server-filesystem`
- `_http_get/post` → `server-fetch`
- `_wp_*` (4 fn) → `WordPress/mcp-adapter`

---

## §8 MCP teszt pattern

**Hiányok:**
1. **MCP Inspector** (`@modelcontextprotocol/inspector`) — integrálni CI-be
2. **Conformance test suite** — spec draft alatt; addig `modelcontextprotocol/python-sdk/tests`
3. **Load test** — stdio **nem skálázódik >20 connection** (20/22 fail 2025-12 benchmark). 139 site → **kötelező Streamable HTTP + gateway**
4. **Sampling mock** — client-side mock LLM (ctx.sample → canned response)

**Ajánlás:** `/tests/mcp/` mappa, pytest-async, MCP Inspector CI step, 3 test típus: unit/integration/load.

---

## Források (access 2026-04-20)

- [MCP Spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [2026 MCP Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)
- [WorkOS MCP update](https://workos.com/blog/mcp-2025-11-25-spec-update)
- [Subramanya enterprise readiness](https://subramanya.ai/2025/12/01/mcp-enterprise-readiness-how-the-2025-11-25-spec-closes-the-production-gap/)
- [Streamable HTTP vs SSE](https://brightdata.com/blog/ai/sse-vs-streamable-http)
- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- [Supabase MCP](https://github.com/supabase-community/supabase-mcp) 2.6k★
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode-mcp/)
- [WordPress MCP Adapter](https://github.com/WordPress/mcp-adapter)
- [Automattic/mcp-wordpress-remote](https://github.com/Automattic/mcp-wordpress-remote)
- [OAuth 2.1 MCP — Aembit](https://aembit.io/blog/mcp-oauth-2-1-pkce-and-the-future-of-ai-authorization/)
- [Multi-tenant MCP auth — TrueFoundry](https://www.truefoundry.com/blog/mcp-authentication-in-cursor-oauth-api-keys-and-secure-configuration)
- [MCP Apps launch — The Register](https://www.theregister.com/2026/01/26/claude_mcp_apps_arrives/)
- [Memgraph Sampling experiment](https://memgraph.com/blog/memgraph-mcp-elicitation-and-sampling)

---
*v1.0 · 2026-04-20 · deep-research agent output*
