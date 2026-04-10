# MCP Panel — Kutatási Összefoglaló & Értékelés

> **Dátum**: 2026-02-24

---

## 1. RÖVID ÉRTÉKELÉS

**Ötlet**: OCCP dashboard-ba beépíteni MCP telepítési lehetőséget — top 100 MCP, gyors leírás, install link, hogy az agentek használhassák.

| Szempont | Értékelés |
|----------|-----------|
| **Érték** | ✅ Magas — MCP a 2026-os AI tooling standard; Cursor/Claude mind használja |
| **Relevancia** | ✅ OCCP agent control plane + MCP = természetes illesztés |
| **Komplexitás** | ⚠️ Közepes — két réteg: 1) UI listing, 2) agent→MCP client integráció |
| **Adatforrás** | ✅ Hivatalos MCP Registry API (Anthropic) + mcpserverslist.com |
| **Kockázat** | Alacsony — listing önmagában nem breaking; agent integráció külön phase |

**Két fázis javaslat**:
- **Phase A**: Dashboard MCP katalógus — top 100 listázás, Copy config, linkek (UI only)
- **Phase B**: OCCP agentek MCP client-ként — pipeline adapter, hogy a Verified Autonomy Pipeline használhassa az MCP toolokat

---

## 2. KUTATÁSI EREDMÉNYEK

### Hivatalos források

| Forrás | URL | Tartalom |
|--------|-----|----------|
| **MCP Registry (Anthropic)** | https://registry.modelcontextprotocol.io/v0/servers | REST API, paginált JSON, ~30/oldal |
| **MCP Registry schema** | https://static.modelcontextprotocol.io/schemas/ | server.schema.json |
| **MCP docs** | https://modelcontextprotocol.io | Spec, client/server guide |

### Közösségi listák

| Forrás | Tartalom |
|--------|----------|
| **mcpserverslist.com** | 500+ MCP, kategóriák, star count, rövid leírás |
| **mcpserverdirectory.org** | 2500+ resource, featured (PostgreSQL, Google Drive, Puppeteer, Slack, Fetch, Git, GitHub) |
| **wong2/awesome-mcp-servers** | GitHub, 976 star, reference + production servers |
| **cline/mcp-marketplace** | Cline official, 554 star |
| **serpvault/awesome-mcp-servers** | Serp.ai, "Biggest Database" |

### Top MCP-k (star / népszerűség alapján)

| MCP | Leírás | Stars | Install |
|-----|--------|-------|---------|
| Context7 | Code docs access | 29,388 | npm |
| Firecrawl | Web scraping, crawl | 4,452 | npm |
| Cloudflare | Cloudflare API | 2,925 | npm |
| Browserbase | Cloud browser control | 2,564 | npm |
| Exa | Web search API | 2,216 | streamable-http |
| Perplexity Ask | Sonar API research | 1,563 | npm |
| Grafana | Monitoring | 1,542 | npm |
| Bright Data | Web data platform | 1,248 | npm |
| ElevenLabs | TTS, voice | 966 | npm |
| Stripe Agent Toolkit | Stripe API | 948 | npm |
| Qdrant | Vector DB | 912 | npm |
| PostgreSQL | DB read/query | Official | npx |
| Google Drive | File access | Official | npx |
| Puppeteer | Browser automation | Official | npx |
| Brave Search | Search | Official | npx |
| Slack | Workspace messaging | Official | npx |
| Fetch | Web fetch | Official | npx |
| Git | Repo control | Official | npx |
| GitHub | Issue tracking | Official | npx |

### Cursor/Claude MCP config formátum

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "..." }
    },
    "exa": {
      "url": "https://mcp.exa.ai/mcp",
      "headers": { "x-api-key": "..." }
    }
  }
}
```

- **stdio (npx)**: `command` + `args` + `env`
- **streamable-http**: `url` + opcionális `headers`
- **Project**: `.cursor/mcp.json`
- **Global**: `~/.cursor/mcp.json`

---

## 3. IMPLEMENTÁCIÓS MEGJEGYZÉSEK

### Phase A — Dashboard MCP katalógus

1. **Adatforrás**:
   - Előny: MCP Registry API (`GET /v0/servers`) — friss, hivatalos
   - Hátrány: paginált, nincs star count
   - Kompromisszum: Statikus curated top 100 JSON (kombinálva mcpserverslist + registry), heti/havi frissítés

2. **UI elemek**:
   - Kártya lista: név, leírás (1–2 mondat), kategória, install parancs
   - "Copy Cursor config" gomb → JSON snippet vágólapra
   - "Docs" / "GitHub" link
   - Kategóriák: Developer, Search, Database, Communication, AI, Infra, stb.

3. **Technikai**:
   - Új dashboard oldal: `/mcp` vagy `/tools/mcp`
   - Adat: `dash/src/data/mcp-servers.json` (curated) VAGY API route → proxy to registry
   - Nincs backend módosítás (csak dash)

### Phase B — Agent MCP client

1. OCCP orchestrator adapter: MCP client, tool invoke a pipeline-ból
2. Konfig: mely MCP-k aktív mely agent/workspace-hez
3. RBAC: ki konfigurálhatja az MCP-ket
4. Érinti: `orchestrator/`, `api/`, `store/`, `config/`

---

## 4. AJÁNLOTT SORREND

1. **Phase A** (1–2 nap): Dashboard MCP katalógus, top 100 curated list
2. **Validálás**: User feedback, használati statisztika
3. **Phase B** (külön prompt): OCCP agent → MCP integráció
