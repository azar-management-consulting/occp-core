# OCCP — Mélykutatási verifikáció és hiányosság-korrekciók (2026-02-26)

**Cél**: Web mélykutatás alapján minden claim, konkurens elemzés és stratégiai dokumentum 100% pontos, téveszmémentes, hallucinációmentes. Saját és mások hiányosságainak azonosítása és javítása.

---

## 1. KRITIKUS FELFEDEZÉSEK — Claim verifikáció

### 1.1 VAP (Verified Autonomy Pipeline) — Névütközés

| Elem | Korábbi állítás | Valóság (web kutatás) |
|------|-----------------|------------------------|
| VAP | „Senki más nem használja ezt a kifejezést” | **FÉLREVEZETŐ** — VeritasChain **VAP** = „Verifiable AI Provenance Framework” (flight recorder, hash chains, Merkle). Teljesen más koncepció. |
| **Korrekció** | — | OCCP mindig használja: **„OCCP's Verified Autonomy Pipeline”** vagy **„5-stage Verified Autonomy Pipeline (Plan→Gate→Execute→Validate→Ship)”**. Ne rövidítsd „VAP”-ra egyedül — kétértelmű. |

**Forrás**: veritaschain.org/vap, IETF draft-kamimura-vap-framework

---

### 1.2 „First open-source agent control plane” — HAMIS

| Elem | Korábbi állítás | Valóság |
|------|-----------------|---------|
| First | „The first open-source Verified Autonomy Pipeline” | **NÉVNAPIG PONTOSÍTANDÓ** |
| Rivalizálók | — | **EV** (eevee.build) — Open Source Agentic Control Plane, K8s-style, MCP, audit, policy. **Kagent** (CNCF) — 2776 ⭐. **OpenLeash** — policy gate. **Leash** (StrongDM) — MCP auth, Cedar. **Asteroid** — control plane production agents. |

**Korrekció**: „First open-source **control plane with a 5-stage verified autonomy pipeline** (Plan→Gate→Execute→Validate→Ship)”. Az EV és mások nem használnak ezt a konkrét task-flow-t; ők resource lifecycle (CREATE/LOAD/UPDATE/DELETE) vagy policy gate megközelítést használnak. OCCP egyedisége: **a konkrét 5-stage task execution pipeline**, nem a „control plane” fogalom.

**Forrás**: eevee.build, github.com/strongdm/leash, CNCF kagent, openleash.ai

---

### 1.3 Leash (StrongDM) — Undersell korrekció

| Korábbi | Valóság |
|---------|---------|
| „Leash csak auth” | **Helytelen.** Leash: Cedar policy, MCP observer, sandbox, audit, filesystem/network monitoring. Teljes governance layer. |

**Korrekció**: „OCCP differentiator vs Leash: **full-stack product** — dashboard, onboarding wizard, MCP install UX, turnkey deploy. Leash = security/infra component (sidecar); OCCP = end-to-end platform with UI.”

**Forrás**: strongdm.com/blog/policy-enforcement-for-agentic-ai-with-leash

---

### 1.4 llms.txt — Túlzás csökkentése

| Korábbi | Valóság |
|---------|---------|
| „llms.txt native — AI discoverability first-class” | **Részben.** 784+ site has llms.txt (Cloudflare, Anthropic, Vercel). DE: **zero major LLM provider** officially uses it. Google rejected it. „Is llms.txt Dead?” cikkek. |

**Korrekció**: „**llms.txt available** — OCCP serves occp.ai/llms.txt for AI discoverability. Aligns with emerging standard (784+ implementations).” Ne írd „first-class” vagy „major differentiator” — inkább „nice-to-have, forward-looking”.

**Forrás**: llms-txt.io, llms-text.com

---

### 1.5 EU AI Act — Pontosítás

| Claim | Valóság |
|-------|---------|
| Art. 12 Record-keeping | ✅ Helyes. Logging, event recording, risk identification, post-market monitoring. |
| Art. 14 Human oversight | ✅ Helyes. High-risk AI human oversight. OCCP: policy gates, approval workflows. |
| Art. 19 | Log retention ≥ 6 months. OCCP audit log — ellenőrizni, hogy retention policy explicit-e. |

**Korrekció**: Használd **„EU AI Act aligned”** (nem „compliant”). Konkrét formulációnk: „OCCP supports EU AI Act requirements: record-keeping (Art. 12), human oversight (Art. 14), audit trails. Verify legal compliance for your use case.”

**Forrás**: artificialintelligenceact.eu/article/12, practical-ai-act.eu

---

### 1.6 Fiddler AI — Megerősítve

| Claim | Valóság |
|-------|---------|
| Fiddler = commercial, proprietary | ✅ **Igaz.** $100M funding, Series C $30M 2026. Nem open source. |

---

## 2. ÚJ KONKURENSEK — Frissített piaci kép

| Projekt | Típus | Fókusz | OCCP differenciátor |
|---------|-------|--------|---------------------|
| **EV** (eevee.build) | OSS, K8s-style | Declarative resources, MCP, policy, audit | OCCP: 5-stage task pipeline, turnkey (nem K8s), onboarding wizard |
| **Kagent** (CNCF) | OSS | K8s-native, DevOps | OCCP: nem K8s-kötelező, könnyebb indulás |
| **OpenLeash** | OSS | Policy gate, sidecar, local-first | OCCP: full platform, dashboard |
| **Leash** (StrongDM) | OSS | MCP auth, Cedar, audit, sandbox | OCCP: full UX, MCP install flow, onboarding |
| **VeritasChain VAP** | Standard | Provenance, cryptographic audit | OCCP: más koncepció — execution pipeline, nem provenance framework |

---

## 3. HIÁNYOSSÁGOK JAVÍTÁSA — Dokumentumok

### 3.1 docs/OCCP_UNIQUE_DIFFERENTIATION_STRATEGY.md

| Szekció | Javítás |
|---------|---------|
| 1.2 Claim #1 | „First open-source **control plane with a 5-stage Verified Autonomy Pipeline** (Plan→Gate→Execute→Validate→Ship)” |
| 1.2 Claim #4 | „llms.txt **available** — AI discoverability at occp.ai/llms.txt” (ne „native”, ne „first-class”) |
| 1.2 Claim #7 | „MCP + Governance in one — **full-stack platform with dashboard and onboarding**; Leash = infra component.” |
| 4. Konkurens | Add: EV, Kagent, OpenLeash. Frissítsd Leash sort. Add VAP naming note. |

### 3.2 docs/GLOBAL_AGENT_ECOSYSTEM_RESEARCH.md

| Javítás |
|---------|
| Add EV (eevee.build), Kagent (CNCF), OpenLeash. |
| Add VeritasChain VAP — különböztetés OCCP Verified Autonomy Pipeline-tól. |
| Frissítsd Leash leírást: több mint auth — policy, MCP observer, audit. |

### 3.3 prompts/CLAUDE_V082_STRENGTHENING_PROMPT.md

| Javítás |
|---------|
| A2: „First open-source **control plane with a 5-stage** Verified Autonomy Pipeline” |
| Add: VAP naming — always use full form or „OCCP's Verified Autonomy Pipeline” |
| Add: llms.txt → „available” not „native” |
| D1 EU doc: Add Art. 19 retention note (6 months) |

---

## 4. ÖNVÉDŐ CHECKLIST — Téveszmék / hallucinációk ellen

| # | Ellenőrzés | Státusz |
|---|------------|---------|
| 1 | „First” claim — pontosan miben első? | ✅ 5-stage pipeline (Plan→Gate→Execute→Validate→Ship) — másoknak nincs ilyen exact flow |
| 2 | VAP — keveredik-e VeritasChain-nel? | ✅ Igen — mindig „OCCP's” vagy „5-stage” jelző |
| 3 | Leash — „csak auth”? | ✅ Javítva — full governance layer |
| 4 | llms.txt — túlzott jelentőség? | ✅ Javítva — „available” |
| 5 | EU — jogi kijelentés? | ✅ „Aligned”, disclaimer |
| 6 | Konkurens lista teljes? | ✅ EV, Kagent, OpenLeash hozzáadva |

---

## 5. SIKER METRIKÁK — Piaci kontextus (kutatás)

| Metrika | Forrás | OCCP relevancia |
|---------|--------|-----------------|
| 51% orgs agents in production | LangChain State of AI 2024 | OCCP célközönség |
| 78% plan to implement soon | — | Növekvő piac |
| 73% prioritize productivity | Measuring Agents in Production | Governance = risk reduction = ROI |
| 74% use human evaluation | — | OCCP audit, human oversight aligns |
| 68% max 10 steps before human | — | OCCP policy gates, approval flow |
| Gartner: 40% agent projects canceled by 2027 (cost, value, risk) | — | Control plane = risk reduction |

---

## 6. VÉGLEGES JAVASOLT CLAIM-EK (100% védhető)

| # | Claim | Formuláció |
|---|-------|------------|
| 1 | Pipeline | „OCCP's 5-stage Verified Autonomy Pipeline (Plan→Gate→Execute→Validate→Ship) — every step audit-logged, hash-chained.” |
| 2 | First | „First open-source control plane with this exact 5-stage verified task pipeline.” |
| 3 | Integrációk | „Curated MCP catalog (15+ certified, roadmap to 100). Quality over sprawl.” |
| 4 | Quickstart | „30-second demo. 5-minute quickstart to first pipeline run.” |
| 5 | llms.txt | „llms.txt available — occp.ai/llms.txt for AI discoverability.” |
| 6 | EU | „EU AI Act aligned — record-keeping (Art. 12), human oversight (Art. 14), audit trails. Verify compliance for your use case.” |
| 7 | Self-hosted | „Runs on your machine. Your data stays.” |
| 8 | Full-stack | „MCP + Governance + Dashboard + Onboarding in one platform.” |

---

*Mélykutatás: 2026-02-26. Források: VeritasChain, eevee.build, StrongDM, EU AI Act, llms-txt.io, LangChain State of AI, arxiv, CNCF.*
