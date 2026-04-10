# OCCP — Formabontó egyediség & piaci elsőség stratégia

**Dátum**: 2026-02-26  
**Cél**: Mindenkitől formabontóbb, egyedibb, vonzóbb OCCP. Elsők a piacon. Minimális de 100 legjobb integráció. Promó + marketing mindenkit megelőz.

---

## 1. Egyedi „elsők” pozícionálás — piaci rések

### 1.1 Amit a kutatás mutat

| Piaci tény | Rések / lehetőségek |
|------------|----------------------|
| 68% rossz platformot választ → költséges migráció | **„Right choice first”** — OCCP = migráció-mentes, long-term fit |
| Csak 4/13 frontier agent publikál safety eval | **„Verified by design”** — Verified Autonomy Pipeline = minden action verified |
| MCP: stateful, serverless unfriendly | **„MCP that works everywhere”** — OCCP MCP layer stateless-friendly |
| Integration sprawl (1000+ connection) | **„Curated catalog, zero noise”** — kuration over quantity |
| Enterprise: SOC2, audit, compliance | **„EU AI Act aligned”** — Record-keeping, Human Oversight, Audit built-in |

### 1.2 OCCP egyedi claim-ek (amit senki más nem mond)

| # | Claim | Indoklás |
|---|-------|----------|
| 1 | **„First open-source control plane with a 5-stage Verified Autonomy Pipeline”** | OCCP's pipeline: Plan → Gate → Execute → Validate → Ship — minden lépés auditált, hash-chained. (VAP: VeritasChain is használja más jelentéssel — mindig „OCCP's Verified Autonomy Pipeline" vagy teljes név.) |
| 2 | **„Curated catalog (15+ certified, roadmap to 100), zero sprawl”** | Kuration over sprawl. Kézzel válogatott, auditált MCP + Skills, nem 1000+ connection. a16z: curated > comprehensive. |
| 3 | **„5-minute quickstart”** | occp demo → 30 mp. First pipeline run → 5 perc. Riválisok: 3–6 hónap (framework) vagy 2–4 hét (no-code). |
| 4 | **„llms.txt available”** | OCCP az occp.ai/llms.txt-t szolgálja. AI discoverability — 784+ site használja. (Ne „native" — nincs major LLM provider hivatalos támogatás.) |
| 5 | **„EU-ready (Art. 12, 14 aligned)”** | Record-keeping (Art. 12), Human Oversight (Art. 14), Audit log — beépítve. *Not legal advice; verify compliance for your deployment.* |
| 6 | **„Runs on your machine, your data stays”** | Self-hosted, zero egress. Adatszuverenitás. |
| 7 | **„MCP + Governance in one”** | MCP install + RBAC + audit + policy — egy platform. Leash = infra component (auth, Cedar, MCP observer); OCCP = end-to-end UX, turnkey deploy. |

---

## 2. „Curated catalog” stratégia

### 2.1 A16z tanulság: Curated > Comprehensive

- **Comprehensive**: mindenki mindent (Shopify: 6000+ app) → noise, trust probléma  
- **Exclusive**: egyedüli partnerek → scaling nehéz  
- **Curated**: szelektív, minőségi → OCCP választása  

### 2.2 Roadmap: 10 kategória × 10 integráció

| Kategória | Példa integrációk (max 10/kategória) |
|-----------|--------------------------------------|
| **Core MCP** | GitHub, Filesystem, Memory, Postgres, SQLite |
| **Search** | Brave Search, Tavily |
| **Dev** | GitLab, Sentry, Linear |
| **Comms** | Slack, Discord (ha MCP) |
| **Storage** | Google Drive, S3-compatible |
| **LLM** | Anthropic, OpenAI, OpenRouter, Ollama, Groq |
| **Observability** | (built-in audit) |
| **Skills** | Code review, Security scan, Doc gen |
| **Browser** | Puppeteer, Playwright (ha MCP) |
| **Enterprise** | Okta, LDAP (future) |

**Szabály**: Csak olyan integráció kerül be, ami production-ready, auditált, és dokumentált. Nincs „kitchen sink”.

### 2.3 Trust signal minden integrációnál

- ✅ OCCP Certified badge  
- ✅ Security review státusz  
- ✅ Token impact / cost transparency  
- ✅ „What data is shared” szekció  

---

## 3. Promo & marketing — mindenkit megelőzve

### 3.1 Viral loop beépítése (Reimer, Corbado)

| Mechanizmus | OCCP implementáció |
|-------------|---------------------|
| **Shareable output** | Audit log export → „Verified by OCCP” watermark / link |
| **README badge** | `[![OCCP Verified](https://occp.ai/badge.svg)](https://occp.ai)` — mint Snyk, CodeCov |
| **One-click MCP install** | Copy mcp.json → Cursor/Claude → „Powered by OCCP” |
| **Invite loop** | Team onboarding → invite 3 → unlock feature |

### 3.2 Developer GTM (Ngrok, Corbado)

| Taktika | OCCP |
|---------|------|
| **PLG first** | Ingyenes self-hosted, pay for managed / enterprise |
| **Content** | 5-min quickstart, „How we built OCCP” tech blog |
| **DevRel** | Conference talk: „Verified Autonomy Pipeline” |
| **Directory** | Product Hunt, Hacker News, 100+ dev directory (launchdirectories.com) |

### 3.3 Product Hunt launch (2 hónap prep)

| Lépés | Időzítés |
|-------|----------|
| Beta users, feedback | -8 week |
| Hunter (optional) | -4 week |
| Assets: 2–8 screenshot, 240×240 thumb | -2 week |
| Tagline (60 char): „Open-source control plane for AI agents. Verified. Auditable. Self-hosted.” | |
| Launch day network | Day 0 |

### 3.4 Egyedi szövegek (tagline-ok)

| Kontextus | Szöveg |
|-----------|--------|
| **Hero** | „The first open-source control plane with a 5-stage Verified Autonomy Pipeline for AI agents.” |
| **1-liner** | „Every action verified. Every decision audited. Your infrastructure.” |
| **SEO** | „OCCP — Open-source AI agent control plane with Verified Autonomy Pipeline, MCP, RBAC, EU-ready” |
| **Developer** | „5-minute quickstart. Curated catalog (15+ certified). Zero lock-in.” |

---

## 4. Formabontó elemek — konkurens elemzés

| Konkurens | Gyengeség | OCCP formabontó válasz |
|-----------|-----------|-------------------------|
| **Fiddler** | Commercial, SaaS, $ | Open-source, self-hosted, free |
| **Leash** | Infra component (auth, Cedar, MCP observer) — nincs full UX | Full-stack platform: dashboard, onboarding wizard, MCP install UX, turnkey deploy |
| **EV** (eevee.build) | K8s-style, resource lifecycle (CREATE/Load/Update/Delete) | OCCP: 5-stage task pipeline (Plan→Gate→Execute→Validate→Ship), könnyebb indulás |
| **Kagent** (CNCF) | K8s-native, DevOps fókusz | OCCP: nem K8s-kötelező, 5-min quickstart |
| **OpenLeash** | Policy gate, sidecar, local-first | OCCP: full platform, dashboard |
| **OpenClaw** | Nincs governance layer | OCCP: RBAC, audit, policy engine |
| **LangGraph** | Framework, nincs deploy | OCCP: turnkey deploy, Docker Compose |
| **MCP ecosystem** | Tool sprawl, no curation | OCCP: Curated catalog (15+ certified, roadmap to 100) |
| **Enterprise vendors** | 3–6 hónap implementation | OCCP: 5-min quickstart |

---

## 5. Következő lépések (prioritás)

| # | Akció | Hatás |
|---|-------|-------|
| 1 | **„First open-source control plane with a 5-stage Verified Autonomy Pipeline”** claim → landing, README | Egyedi positioning |
| 2 | **Curated Catalog** roadmap → 15+ certified, target 100 | Kuration narrative |
| 3 | **README badge** (`occp.ai/badge.svg`) | Viral loop |
| 4 | **llms.txt** → landing, docs hangsúly | AI discoverability |
| 5 | **EU AI Act Ready** szekció | EU / enterprise vonzerő |
| 6 | **Product Hunt** launch prep (2 hónap) | Distribution |
| 7 | **5-min quickstart** video + doc | Conversion |

---

## 6. Összefoglaló — mi leszünk egyediek

1. **OCCP's Verified Autonomy Pipeline** — első nyílt forrású control plane ezzel a 5-stage pipeline-dzsal (Plan→Gate→Execute→Validate→Ship)  
2. **Curated catalog, zero sprawl** — kuration over quantity
3. **5-minute quickstart** — leggyorsabb time-to-value  
4. **llms.txt available** — AI discoverability (occp.ai/llms.txt)  
5. **EU-ready (Art. 12, 14 aligned)** — beépített compliance *(not legal advice)*  
6. **Self-hosted, your data** — adatszuverenitás  
7. **MCP + Governance in one** — egy platform, teljes stack  

**Marketing üzenet**: *„OCCP — the first open-source control plane with a 5-stage Verified Autonomy Pipeline. Every agent action verified, audited, EU-ready. 5-minute quickstart. Curated catalog. Your infrastructure.”*

---

*Források: a16z, Reimer devtools growth, Corbado PH, EU AI Act, MCP survey, Swfte buyer guide, Bain agentic AI 2025.*
