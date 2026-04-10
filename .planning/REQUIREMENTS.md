# REQUIREMENTS.md — OCCP v1.0 "Agent Control Plane"

**Version:** 2.0.0 | **Date:** 2026-02-27 | **Naming:** REQ-{CATEGORY}-{NN}
**Integrates:** Original GSD requirements + OpenClaw gap analysis

---

## Categories

| Code | Domain | Origin |
|------|--------|--------|
| GOV | Governance Core | Original |
| POL | Policy Engine | Original |
| CPC | Cryptographic Provenance | Original |
| TSF | Trusted Skill Fabric | Original |
| VSTA | Verified Scheduler | Original |
| MAO | Multi-Agent Orchestrator | Original |
| CBDB | Controlled Browser | Original |
| MCP | MCP Tool Fabric | Original |
| RT | Red-Team Harness | Original |
| CHAN | Channel Adapters | OpenClaw gap |
| MEM | Memory System | OpenClaw gap |
| A2UI | Agent-to-UI Canvas | OpenClaw gap |
| SEC | Security Enhancement | OpenClaw gap |
| COMP | Compliance Framework | OpenClaw gap |
| SDK | SDK Enhancement | OpenClaw gap |
| MARKET | Marketplace/Ecosystem | OpenClaw gap |
| AUTO | Automation (cron/webhook/trigger) | OpenClaw gap |
| CORE | Core Pipeline Enhancement | OpenClaw gap |
| MULTI | Multi-Tenancy | OpenClaw gap |

---

## GOV — Governance Core (Original)

### REQ-GOV-01: VAP Lifecycle Enforcement
- **Description:** All actions MUST pass through VAP lifecycle (Plan → Gate → Execute → Validate → Ship). No execution path may bypass any stage.
- **Rationale:** Non-bypassable governance is OCCP's core differentiator. OpenClaw has no equivalent.
- **Acceptance Test:** (1) Direct tool invocation without VAP returns 403. (2) Disabled gate stage causes startup failure. (3) Fuzz test: 10,000 random API calls — 0 bypass VAP.
- **Owner Module:** `orchestrator/pipeline.py`

### REQ-GOV-02: Policy-as-Code Engine
- **Description:** Gate decisions MUST be executed by Policy-as-Code engine. Currently Casbin RBAC + YAML guard rules. Evaluate Cedar or OPA for complex policies.
- **Rationale:** Declarative, version-controlled, testable policies are required for audit compliance.
- **Acceptance Test:** (1) Policy change requires git commit. (2) Policy evaluation result includes: input context, rules evaluated, decision, policy version hash. (3) Policy rollback restores previous behavior within 1 cycle.
- **Owner Module:** `policy_engine/engine.py`

### REQ-GOV-03: Non-Bypassable Policy Evaluation
- **Description:** No tool, MCP server, skill, or adapter invocation may bypass policy evaluation. Applies to built-in tools, plugins, and third-party integrations equally.
- **Rationale:** OpenClaw's tool policy has precedence-based overrides. OCCP enforces at a single, non-bypassable gate.
- **Acceptance Test:** (1) Plugin attempting direct tool call without gate → blocked + audit entry. (2) MCP tool call routed through policy gate. (3) No code path from adapter to execution skips `PolicyGate.evaluate()`.
- **Owner Module:** `policy_engine/engine.py`, `adapters/policy_gate.py`

### REQ-GOV-04: Break-Glass Protocol
- **Description:** Emergency bypass requires: (1) Multi-party approval (2 of 3 system_admins), (2) Time-limited token (max 1h), (3) Immutable audit trail entry with `severity=CRITICAL`, (4) Automatic revocation on expiry.
- **Rationale:** Real-world operations need emergency access. Break-glass must be auditable and automatically expiring.
- **Acceptance Test:** (1) Single admin cannot activate break-glass alone. (2) Break-glass token expires after configured duration. (3) All actions during break-glass window tagged `break_glass=true` in audit. (4) Post-expiry, normal gate resumes automatically.
- **Owner Module:** `security/break_glass.py`

### REQ-GOV-05: Agent Boundary Enforcement
- **Description:** Runtime enforcement of agent-scoped resource boundaries. Each agent's declared capabilities (from TOOLS.md or manifest) define its maximum resource envelope. Any tool call, file access, or API request outside declared scope is blocked at policy layer.
- **Rationale:** Multi-agent environments require strict boundaries to prevent privilege escalation (agent A using agent B's tools). CrowdStrike audit of OpenClaw found zero agent boundary enforcement.
- **Acceptance Test:** (1) Agent with `tools: [web_search]` cannot invoke `shell_exec`. (2) Boundary violation produces `DENY` audit entry with `reason=agent_boundary`. (3) Fuzz test: 1,000 cross-boundary calls → 0 bypass. (4) Boundary changes require policy gate re-evaluation.
- **Owner Module:** `policy_engine/agent_boundary.py`

### REQ-GOV-06: Trust Level Declaration & Enforcement
- **Description:** Every agent MUST declare a trust level (L0–L5): L0 Deterministic (no LLM), L1 Tool-restricted (allowlisted tools only), L2 Network-scoped (domain-limited network), L3 Browser-enabled (governed Playwright), L4 Scheduler-autonomous (cron/webhook trigger), L5 Multi-agent orchestrator (spawns sub-agents). Trust level enforced at VAP Gate stage. Agent requesting capability above declared level → blocked.
- **Rationale:** OpenClaw has implicit trust (all agents can do everything). Explicit trust levels enable least-privilege enforcement and graduated autonomy. Maps to EU AI Act Art. 9 risk classification.
- **Acceptance Test:** (1) Agent declared L1 attempting browser navigation → blocked + audit `reason=trust_level_violation`. (2) Trust level declared in AGENT.md `trust_level: L2` field. (3) Trust level downgrade at runtime allowed; upgrade requires policy gate re-evaluation. (4) L5 agent spawn creates child at L5-1=L4 by default. (5) Fuzz test: 5,000 cross-level calls → 0 bypass.
- **Owner Module:** `policy_engine/trust_levels.py`

---

## POL — Policy Engine

### REQ-POL-01: ABAC + RBAC Hybrid Model
- **Description:** Implement Attribute-Based Access Control alongside existing Casbin RBAC. Attributes include: user role, agent type, tool category, data classification, time-of-day, source IP, session type.
- **Rationale:** RBAC alone insufficient for context-dependent decisions (e.g., "allow shell_exec only during business hours for operator role").
- **Acceptance Test:** (1) Policy rule `p, operator, shell_exec, execute, time:09:00-17:00` enforced. (2) Same user blocked outside hours. (3) Attribute values verified from request context, not user-supplied.
- **Owner Module:** `policy_engine/abac.py`

### REQ-POL-02: Policy Decision Audit
- **Description:** All policy decisions emit structured records: input context, evaluated rules, decision result, hash of policy version used.
- **Rationale:** EU AI Act Art. 14 requires explainable automated decisions.
- **Acceptance Test:** (1) Every ALLOW/DENY decision produces audit entry. (2) Entry includes policy file SHA-256. (3) Audit entries queryable by decision type. (4) Decision replay: same input + same policy version = same output.
- **Owner Module:** `policy_engine/engine.py`

### REQ-POL-03: Testable Policies
- **Description:** Policies version-controlled (git) and testable via `occp policy test` CLI. Test fixtures define input → expected decision pairs.
- **Rationale:** Policy changes can break production. Test-before-deploy prevents governance failures.
- **Acceptance Test:** (1) `occp policy test --file=policy.yaml --fixtures=test.yaml` runs test suite. (2) CI pipeline includes policy tests. (3) Policy deploy blocked if tests fail.
- **Owner Module:** `cli/policy_test.py`

---

## CPC — Cryptographic Provenance

### REQ-CPC-01: SLSA Provenance
- **Description:** All skills, MCP servers, and container images include SLSA Build L2+ provenance metadata. Provenance attests: source repo, build system, build inputs.
- **Rationale:** Supply-chain attacks are the #1 risk for plugin ecosystems. OpenClaw's ClawHub has no provenance. OCCP differentiates with verifiable builds.
- **Acceptance Test:** (1) Skill without provenance rejected at install. (2) Provenance metadata verifiable offline. (3) Provenance includes: source commit SHA, builder identity, timestamp.
- **Owner Module:** `security/provenance.py`

### REQ-CPC-02: Artifact Signing
- **Description:** All distributed artifacts signed using Sigstore/cosign or equivalent. Signatures verified at install time and runtime load.
- **Rationale:** Prevents tampered artifact execution. Defense-in-depth with provenance.
- **Acceptance Test:** (1) `cosign verify` passes for all OCCPHub artifacts. (2) Tampered artifact (bit-flip) rejected at load. (3) Signature check adds <100ms to install time.
- **Owner Module:** `security/signing.py`

### REQ-CPC-03: Runtime Signature Verification
- **Description:** Runtime verifies artifact signatures before loading any skill, plugin, or MCP server. Verification occurs at every restart, not just install.
- **Rationale:** Post-install tampering (supply-chain compromise) requires runtime verification.
- **Acceptance Test:** (1) Skill loaded from disk verified against signature. (2) Modified skill file → load failure + alert. (3) Verification cached for 24h to reduce startup latency.
- **Owner Module:** `security/supply_chain.py`

### REQ-CPC-04: Revocation Framework
- **Description:** Centralized revocation list with kill-switch capability. Revoked artifacts blocked at runtime within 1 polling cycle (default: 5 minutes).
- **Rationale:** Zero-day in a popular skill requires immediate revocation across all installations.
- **Acceptance Test:** (1) Revoked skill ID added to revocation list. (2) All OCCP instances block revoked skill within 5 minutes. (3) Kill-switch disables all non-core skills immediately. (4) Revocation survives network partition (local cache).
- **Owner Module:** `security/revocation.py`

---

## TSF — Trusted Skill Fabric

### REQ-TSF-01: Private-First Registry
- **Description:** Default skill registry is private (org-scoped). Public OCCPHub is opt-in. Private registries support self-hosted deployment.
- **Rationale:** Enterprise skill content is proprietary. Default-private prevents accidental exposure.
- **Acceptance Test:** (1) Fresh install has empty skill registry. (2) OCCPHub connection requires explicit `occp hub enable`. (3) Private registry serves skills without external network.
- **Owner Module:** `api/routes/skills.py`

### REQ-TSF-02: Capability Declaration Schema
- **Description:** Every skill declares capabilities via structured manifest: network scope (domains), file scope (paths), system command scope (commands), data domain scope (PII, financial, medical).
- **Rationale:** Policy gate needs declared capabilities to enforce boundaries. OpenClaw skills have no capability declaration.
- **Acceptance Test:** (1) Skill without manifest rejected. (2) Skill declaring `network: [api.example.com]` blocked from other domains. (3) Skill declaring `data: [pii]` triggers enhanced audit logging.
- **Owner Module:** `orchestrator/skill_manifest.py`

### REQ-TSF-03: Mandatory SBOM per Version
- **Description:** Every skill version includes CycloneDX SBOM listing all dependencies with license information.
- **Rationale:** Dependency transparency for compliance. EU Cyber Resilience Act requirement.
- **Acceptance Test:** (1) `occp skill info my-skill --sbom` displays dependency tree. (2) SBOM generated automatically during `occp skill publish`. (3) License policy violations flagged at install.
- **Owner Module:** `security/sbom.py`

### REQ-TSF-04: Version Pinning in Production
- **Description:** No floating version installs in production mode (`OCCP_ENV=production`). All skills pinned to exact version in `skills.lock`.
- **Rationale:** Reproducible deployments prevent supply-chain drift.
- **Acceptance Test:** (1) `occp skill install web-search@latest` in production → error. (2) `occp skill install web-search@1.2.3` succeeds. (3) `skills.lock` tracks exact versions.
- **Owner Module:** `cli/skills.py`

### REQ-TSF-05: Automated Scan Pipeline
- **Description:** Pre-publish pipeline: (1) Static analysis (Semgrep), (2) Dependency audit (Snyk), (3) Secret scan (GitGuardian), (4) Capability declaration validation. All 4 must pass.
- **Rationale:** Quality gate prevents malicious or vulnerable skills from reaching registry.
- **Acceptance Test:** (1) Skill with hardcoded API key rejected. (2) Skill with known-vulnerable dependency rejected. (3) Scan results attached to skill metadata.
- **Owner Module:** `.github/workflows/skill-scan.yml`

---

## VSTA — Verified Scheduler

### REQ-VSTA-01: VAP-Enforced Scheduled Jobs
- **Description:** Every scheduled job triggers a full VAP cycle. No shortcut execution path for cron jobs.
- **Rationale:** Scheduled tasks are highest-risk (unattended execution). Full governance mandatory.
- **Acceptance Test:** (1) Cron job creates Task with `source=cron`. (2) Task passes through all 5 VAP stages. (3) Gate rejection stops cron job and creates alert.
- **Owner Module:** `orchestrator/cron.py`

### REQ-VSTA-02: Policy Template Profiles
- **Description:** Jobs declare policy template profile (e.g., `strict`, `standard`, `permissive`). Profile determines which guards are active and their thresholds.
- **Rationale:** Different jobs need different security postures. Night batch may be stricter than interactive.
- **Acceptance Test:** (1) Job with `profile=strict` activates all guards. (2) Job with `profile=standard` activates core guards only. (3) Profile definitions in version-controlled YAML.
- **Owner Module:** `policy_engine/profiles.py`

### REQ-VSTA-03: Budget Guard (Token/Cost)
- **Description:** Per-job token and cost budget. Job terminated if budget exceeded. Budget tracked across VAP stages.
- **Rationale:** Runaway agent loops can consume unlimited tokens. Budget guard prevents cost explosions.
- **Acceptance Test:** (1) Job with `max_tokens=10000` terminated at 10,001. (2) Cost calculated per provider pricing. (3) Budget warning at 80% threshold. (4) Budget enforcement cannot be overridden by agent.
- **Owner Module:** `policy_engine/budget_guard.py`

### REQ-VSTA-04: Time-Bound Execution with Auto-Kill
- **Description:** Maximum execution time per job (default: 5 minutes). Auto-kill with graceful shutdown (SIGTERM → 10s → SIGKILL). Sandbox resources released.
- **Rationale:** Stuck jobs block resources. Deterministic timeout prevents resource exhaustion.
- **Acceptance Test:** (1) Job exceeding timeout killed. (2) Graceful shutdown attempted first. (3) Sandbox container cleaned up within 30s. (4) Timeout event in audit trail.
- **Owner Module:** `orchestrator/scheduler.py`

---

## MAO — Multi-Agent Orchestrator

### REQ-MAO-01: Worker Sandbox Isolation
- **Description:** Worker agents spawned by parent agent run in isolated sandbox containers with: separate filesystem, configurable network, resource quotas, no access to parent state.
- **Rationale:** OpenClaw's subagent spawning lacks isolation. OCCP enforces sandbox-by-default.
- **Acceptance Test:** (1) Worker cannot read parent's session state. (2) Worker container destroyed on completion. (3) Worker resource usage tracked separately. (4) Worker failure does not crash parent.
- **Owner Module:** `orchestrator/session_tools.py`

### REQ-MAO-02: Configurable Recursion Depth
- **Description:** Maximum agent recursion depth (agent spawning agent) configurable per agent type. Default: 3 levels. Hard maximum: 10.
- **Rationale:** Prevents recursive agent loops consuming unlimited resources.
- **Acceptance Test:** (1) Agent at depth 3 attempting spawn → blocked. (2) Depth tracked in session context. (3) Depth violation logged as `severity=HIGH`.
- **Owner Module:** `orchestrator/session_tools.py`

### REQ-MAO-03: Cascade Stop on Parent Failure
- **Description:** If parent agent fails or is cancelled, all child agents receive stop signal and are terminated within 30 seconds.
- **Rationale:** Orphaned agents waste resources and may continue unauthorized work.
- **Acceptance Test:** (1) Parent failure triggers child stop within 5s. (2) Graceful shutdown attempted before kill. (3) All child audit entries linked to parent task ID.
- **Owner Module:** `orchestrator/session_tools.py`

### REQ-MAO-04: Deterministic Merge Contract
- **Description:** Multi-agent results merged via configurable strategy: (1) First-wins, (2) Consensus (majority), (3) Custom merge function. Merge contract declared at spawn time.
- **Rationale:** Non-deterministic merging creates unpredictable results. Declared contracts enable verification.
- **Acceptance Test:** (1) Consensus merge with 3 agents requires 2 agreeing. (2) Merge result includes source attribution per agent. (3) Merge conflict logged with all agent outputs.
- **Owner Module:** `orchestrator/merge.py`

### REQ-MAO-05: Proof-Carrying Outputs
- **Description:** Every agent output carries proof chain: policy trace (which rules evaluated), provenance hash (input → output hash), validation summary (which validators passed).
- **Rationale:** Tamper-evident outputs enable downstream verification. Critical for agent-to-agent trust.
- **Acceptance Test:** (1) Output without proof chain rejected by receiving agent. (2) Proof chain independently verifiable. (3) Proof chain stored in audit trail.
- **Owner Module:** `orchestrator/proof.py`

---

## CBDB — Controlled Browser

### REQ-CBDB-01: Isolated Browser Profile per Session
- **Description:** Each browser automation session gets isolated Playwright BrowserContext: separate cookies, storage, credentials. Destroyed on session end.
- **Rationale:** Prevent cross-session data leakage through browser state.
- **Acceptance Test:** (1) Session A cookies invisible to Session B. (2) Browser profile destroyed within 10s of session end. (3) No persistent browser data after session.
- **Owner Module:** `adapters/browser_adapter.py`

### REQ-CBDB-02: Domain Allow/Deny List at Gate
- **Description:** Navigation to URLs policy-gated against domain allow/deny list. Default-deny with explicit allowlist.
- **Rationale:** Prevent agent from accessing unauthorized websites (data exfiltration, malicious content).
- **Acceptance Test:** (1) Navigation to non-allowlisted domain → blocked + audit entry. (2) Allowlist configurable per agent. (3) Wildcard patterns supported (`*.example.com`).
- **Owner Module:** `policy_engine/browser_policy.py`

### REQ-CBDB-03: Form Submission Approval
- **Description:** Form submission (POST actions) require explicit approval flag in policy. Default: blocked.
- **Rationale:** Prevent unintended data submission to external sites.
- **Acceptance Test:** (1) Form submit without approval flag → blocked. (2) Approval flag per-domain configurable. (3) Submitted form data logged in audit (PII redacted).
- **Owner Module:** `policy_engine/browser_policy.py`

### REQ-CBDB-04: Download Restrictions
- **Description:** File downloads policy-gated: configurable by file type, size, domain. Downloads stored in sandbox, not host filesystem.
- **Rationale:** Prevent malware download and data exfiltration via file download.
- **Acceptance Test:** (1) Download of .exe blocked by default. (2) Download exceeding 50MB blocked. (3) Downloaded files scanned before access.
- **Owner Module:** `adapters/browser_adapter.py`

### REQ-CBDB-05: Browser Interaction Audit Chain
- **Description:** All browser interactions (navigation, clicks, form fills, downloads) hash-chained into audit log with screenshots at key actions.
- **Rationale:** Full browser action replay for compliance and forensics.
- **Acceptance Test:** (1) Every page navigation creates audit entry. (2) Form submission includes screenshot. (3) Audit chain verifiable with `verify_audit_chain()`.
- **Owner Module:** `adapters/browser_adapter.py`

---

## MCP — MCP Tool Fabric

### REQ-MCP-01: Enterprise MCP Registry
- **Description:** Internal MCP server registry with mirror capability. Org can maintain private MCP server catalog with curated, scanned servers.
- **Rationale:** Public MCP servers are untrusted. Enterprise needs curated, scanned registry.
- **Acceptance Test:** (1) Private registry serves MCP server catalog. (2) Mirror syncs from public catalog with scan gate. (3) Unapproved MCP servers blocked.
- **Owner Module:** `config/mcp_registry.py`

### REQ-MCP-02: Scope-Based Consent Model
- **Description:** Each MCP server connection requires explicit scope consent: (1) Which tools exposed, (2) What data accessible, (3) What actions permitted. Consent stored per-org.
- **Rationale:** MCP servers can expose powerful tools. Consent model prevents unauthorized access.
- **Acceptance Test:** (1) MCP server connection without consent → blocked. (2) Consent UI shows tool list and data scope. (3) Consent revocable per-org.
- **Owner Module:** `api/routes/mcp.py`

### REQ-MCP-03: Governed MCP Dependency
- **Description:** Each MCP server treated as governed dependency: supply-chain scanned, version-pinned, health-monitored, audit-logged.
- **Rationale:** MCP servers execute code. Same governance as any other dependency.
- **Acceptance Test:** (1) MCP server install triggers supply-chain scan. (2) Version pinned in `mcp.lock`. (3) Health check every 60s. (4) MCP tool calls in audit trail.
- **Owner Module:** `security/supply_chain.py`

### REQ-MCP-04: Runtime Scope Enforcement
- **Description:** MCP tool calls enforced against declared scope at runtime. Tool call requesting undeclared scope → blocked.
- **Rationale:** Prevent scope creep where MCP server attempts actions beyond consent.
- **Acceptance Test:** (1) MCP tool call within scope → allowed. (2) Tool call outside scope → blocked + audit entry. (3) Scope violation alert to org_admin.
- **Owner Module:** `adapters/mcp_client.py`

---

## RT — Red-Team Harness

### REQ-RT-01: Automated Injection Test Suite
- **Description:** Comprehensive prompt injection test suite: direct injection, indirect injection (via tool results), multi-turn injection, encoding attacks (base64, unicode), nested injection.
- **Rationale:** CrowdStrike found 8 critical vulnerabilities in OpenClaw. OCCP must proactively test.
- **Acceptance Test:** (1) Test suite includes ≥100 injection payloads. (2) All payloads blocked by guards. (3) New bypass → added to suite within 24h.
- **Owner Module:** `tests/red_team/injection.py`

### REQ-RT-02: Tool Poisoning Simulation
- **Description:** Simulate malicious MCP server/skill returning poisoned results: injected instructions, exfiltration URLs, privilege escalation payloads.
- **Rationale:** Second-order attacks via tool results are harder to detect. Proactive testing required.
- **Acceptance Test:** (1) Poisoned tool result stripped of injection payload. (2) Exfiltration URL blocked by output guard. (3) Privilege escalation payload logged as attack.
- **Owner Module:** `tests/red_team/tool_poisoning.py`

### REQ-RT-03: Data Exfiltration Test Scenarios
- **Description:** Test scenarios where agent attempts to exfiltrate data: via tool calls, browser navigation, message sending, file upload.
- **Rationale:** Data exfiltration is the highest-impact attack. All exit paths must be monitored.
- **Acceptance Test:** (1) Agent attempting to send PII to external URL → blocked. (2) Browser navigation to paste-bin with data → blocked. (3) All exfiltration attempts in audit trail.
- **Owner Module:** `tests/red_team/exfiltration.py`

### REQ-RT-04: Excessive Agency Detection
- **Description:** Detect and prevent agents exceeding intended autonomy: unexpected tool sequences, unusual token consumption, abnormal session duration, scope violations.
- **Rationale:** Agents may drift beyond intended behavior through adversarial prompting.
- **Acceptance Test:** (1) Agent calling 10+ tools in 1 turn → flagged. (2) Agent consuming 3x average tokens → throttled. (3) Anomaly detection model trained on baseline behavior.
- **Owner Module:** `policy_engine/anomaly_detector.py`

### REQ-RT-05: Regression Scoreboard
- **Description:** Mandatory regression scoreboard tracking injection detection rate, false positive rate, bypass count. Updated on every CI run. Release blocked if detection rate drops.
- **Rationale:** Security regressions must be caught before release. Scoreboard provides continuous visibility.
- **Acceptance Test:** (1) Scoreboard visible in CI output. (2) Detection rate <95% → CI failure. (3) Historical trend tracked per release.
- **Owner Module:** `.github/workflows/red-team.yml`

---

## CHAN — Channel Adapters (OpenClaw Gap)

### REQ-CHAN-01: Channel Adapter Protocol
- **Description:** Define `ChannelAdapter` Protocol: `connect()`, `disconnect()`, `send(message)`, `on_message(callback)`, `health_check()`. All adapters implement this protocol. Messages normalized to `InboundMessage` dataclass.
- **Rationale:** OpenClaw's 12+ adapters use ad-hoc normalization. OCCP formalizes with Protocol + governance.
- **Acceptance Test:** (1) New adapter implemented in <200 LOC. (2) Adapter failure triggers reconnect. (3) All adapter events in audit trail.
- **Owner Module:** `adapters/channels/base.py`

### REQ-CHAN-02: WhatsApp Adapter
- **Description:** WhatsApp Web adapter via Baileys with QR pairing, message normalization, media handling.
- **Rationale:** Highest-demand messaging integration.
- **Acceptance Test:** (1) QR code pairing completes. (2) Text/image/doc messages normalized. (3) Session persisted across restarts.
- **Owner Module:** `adapters/channels/whatsapp.py`

### REQ-CHAN-03: Telegram Adapter
- **Description:** Telegram Bot API adapter via grammY with webhook/polling modes.
- **Rationale:** Best official bot API. Lowest integration risk.
- **Acceptance Test:** (1) Webhook mode operational. (2) Inline keyboards for approvals. (3) Files forwarded to sandbox.
- **Owner Module:** `adapters/channels/telegram.py`

### REQ-CHAN-04: Slack Adapter
- **Description:** Slack Bolt adapter with Socket Mode, slash commands, thread conversations.
- **Rationale:** Primary enterprise team messaging.
- **Acceptance Test:** (1) `/occp run <workflow>` triggers VAP. (2) Thread replies maintain session. (3) App Home shows status.
- **Owner Module:** `adapters/channels/slack.py`

### REQ-CHAN-05: Discord Adapter
- **Description:** Discord.js adapter with slash commands, role mapping to OCCP RBAC.
- **Rationale:** Developer community engagement channel.
- **Acceptance Test:** (1) Discord roles mapped to OCCP roles. (2) DM sessions isolated. (3) Rate limits respected.
- **Owner Module:** `adapters/channels/discord.py`

---

## MEM — Memory System (OpenClaw Gap)

### REQ-MEM-01: Hybrid Memory Retrieval
- **Description:** Vector similarity (ChromaDB/Qdrant) + BM25 keyword + structured SQL. Fusion ranking with configurable weights.
- **Rationale:** OpenClaw's hybrid outperforms single-strategy. Enterprise agents need precise recall.
- **Acceptance Test:** (1) Semantic query returns similar results. (2) Exact keyword query returns exact matches. (3) Fusion ranking p95 <200ms.
- **Owner Module:** `store/memory/hybrid.py`

### REQ-MEM-02: Memory Compaction
- **Description:** Auto-summarize conversations >24h old. Weekly digest creation. Originals accessible via link.
- **Rationale:** Unbounded context grows costs. OpenClaw compacts efficiently.
- **Acceptance Test:** (1) 24h+ conversations compacted. (2) Summaries searchable. (3) Storage reduced ≥60%.
- **Owner Module:** `store/memory/compactor.py`

### REQ-MEM-03: Cross-Session Knowledge
- **Description:** Shared knowledge base across sessions. Agents read/write with RBAC controls.
- **Rationale:** Persistent learning enables continuous improvement.
- **Acceptance Test:** (1) Agent A writes fact, Agent B retrieves in different session. (2) Writes require `operator` role. (3) Entries versioned.
- **Owner Module:** `store/memory/knowledge.py`

---

## A2UI — Agent-to-UI Canvas (OpenClaw Gap)

### REQ-A2UI-01: Agent Canvas Workspace
- **Description:** Agent-generated interactive HTML workspace in sandboxed iframe. WebSocket push updates.
- **Rationale:** Rich agent output beyond text. OpenClaw Canvas equivalent with governance.
- **Acceptance Test:** (1) HTML pushed via WebSocket renders. (2) Iframe sandbox prevents parent DOM access. (3) Canvas disabled by default (policy-gated).
- **Owner Module:** `dash/src/app/canvas/`, `api/routes/canvas.py`

---

## SEC — Security Enhancement (OpenClaw Gap)

### REQ-SEC-01: ML-Based Injection Detection
- **Description:** Augment regex guards with ML classifier (distilbert). Dual-mode: regex fast path + ML slow path.
- **Rationale:** CrowdStrike proved regex-only insufficient for OpenClaw.
- **Acceptance Test:** (1) Zero regression on existing patterns. (2) ML catches ≥3 novel attacks. (3) Classification <50ms p95.
- **Owner Module:** `policy_engine/ml_classifier.py`

### REQ-SEC-02: Security Audit CLI
- **Description:** `occp security audit [--deep] [--fix]` checking 15+ items.
- **Rationale:** OpenClaw has `openclaw security audit`. OCCP needs equivalent with deeper checks.
- **Acceptance Test:** (1) Checks JWT secret, CORS, admin password, TLS, sandbox, policies. (2) `--deep` probes endpoints. (3) `--fix` auto-remediates safe issues. (4) Exit code 1 if critical found.
- **Owner Module:** `cli/security_audit.py`

### REQ-SEC-03: Credential Vault
- **Description:** Full vault: per-org key isolation, auto-rotation, access audit, optional HashiCorp Vault backend.
- **Rationale:** OpenClaw's file-based credentials insufficient for enterprise.
- **Acceptance Test:** (1) Rotation without downtime. (2) Org A keys can't decrypt Org B. (3) Every decrypt audited.
- **Owner Module:** `security/vault.py`

### REQ-SEC-04: Adaptive Rate Throttling
- **Description:** Per-agent, per-tool, per-session rate limits with adaptive throttling. Baseline established from historical usage. Deviation >3σ triggers throttle (exponential backoff) + alert. Rate limits configurable per trust level (L0–L5).
- **Rationale:** Prevents runaway agent loops, resource exhaustion attacks, and LLM cost explosions. OpenClaw has no rate limiting. Standard token budget (REQ-VSTA-03) is per-job; this is per-agent continuous.
- **Acceptance Test:** (1) Agent exceeding 3σ tool call rate → throttled within 500ms. (2) Throttle produces audit entry `severity=WARNING, reason=rate_throttle`. (3) Rate limits configurable in policy YAML. (4) L0 agents exempt (deterministic). (5) Manual override requires `operator` role.
- **Owner Module:** `policy_engine/rate_limiter.py`

### REQ-SEC-05: Cost Anomaly Detection
- **Description:** Real-time cost tracking per agent/session/org with anomaly detection. Rolling window (1h/24h/7d) baselines. Alert thresholds: warning at 2x baseline, critical at 5x, auto-kill at 10x. Covers: LLM tokens, tool invocations, browser sessions, file operations.
- **Rationale:** Economic denial-of-wallet attacks can bankrupt operators. Per-job budget (REQ-VSTA-03) is static; this detects anomalous spending patterns across all sessions.
- **Acceptance Test:** (1) Agent spending 5x 24h baseline → CRITICAL alert within 60s. (2) Agent spending 10x → auto-killed + audit `severity=CRITICAL, reason=cost_anomaly`. (3) Cost dashboard shows real-time per-agent breakdown. (4) Historical cost data retained 90 days. (5) Cost anomaly cannot be silenced by agent.
- **Owner Module:** `policy_engine/cost_anomaly.py`

### REQ-SEC-06: Merkle Root Audit Verification
- **Description:** Audit trail entries hash-chained using SHA-256 Merkle tree. Periodic Merkle root published to immutable store (append-only DB table or external timestamping service). Any tampering with historical audit entries detectable by root mismatch.
- **Rationale:** Current SHA-256 chain (v0.8.2) is sequential — tampering at entry N requires recomputing all subsequent entries but is undetectable if attacker controls the DB. Merkle tree + published roots make tampering provably detectable.
- **Acceptance Test:** (1) `occp audit verify --from=2026-01-01 --to=2026-02-01` validates chain integrity. (2) Tampered entry detected: `INTEGRITY_VIOLATION` + affected entry range. (3) Merkle root published every 1,000 entries or 1 hour (whichever first). (4) Verification completes in <5s for 100K entries. (5) Root publication survives network partition (local queue + retry).
- **Owner Module:** `store/audit_merkle.py`

---

## COMP — Compliance Framework (OpenClaw Gap)

### REQ-COMP-01: Framework Mapping Dashboard
- **Description:** Map OCCP controls to SOC2, HIPAA, GDPR, EU AI Act. Visual dashboard with evidence links.
- **Rationale:** No open-source AI platform offers built-in compliance mapping. Category-defining differentiator.
- **Acceptance Test:** (1) SOC2 CC6.1-CC9.9 mapped. (2) Controls link to audit entries. (3) PDF report export.
- **Owner Module:** `dash/src/app/compliance/`

### REQ-COMP-02: SIEM/SOAR Integration
- **Description:** Export audit events in CEF/LEEF/JSON via syslog, webhook, file. Structured event format.
- **Rationale:** Enterprise SOCs require real-time event feeds. OpenClaw has none.
- **Acceptance Test:** (1) Syslog receives CEF within 1s. (2) Events pass Splunk CIM validation. (3) Webhook retry on failure.
- **Owner Module:** `security/siem_export.py`

---

## SDK — SDK Enhancement (OpenClaw Gap)

### REQ-SDK-01: SSE Streaming
- **Description:** Server-Sent Events for real-time pipeline progress in both SDKs.
- **Acceptance Test:** (1) Python `stream_pipeline()` yields typed events. (2) TypeScript `streamPipeline()` returns AsyncIterator. (3) Auto-reconnect on drop.
- **Owner Module:** `sdk/python/client.py`, `sdk/typescript/src/client.ts`

### REQ-SDK-02: OCCP as MCP Server
- **Description:** SDK exposing OCCP as MCP server for Claude Desktop, Cursor, etc.
- **Acceptance Test:** (1) Claude Desktop discovers OCCP agents. (2) Tool calls pass through VAP. (3) Auth via MCP session tokens.
- **Owner Module:** `sdk/mcp_server/`

---

## MARKET — Marketplace (OpenClaw Gap)

### REQ-MARKET-01: OCCPHub Registry
- **Description:** Hosted skill registry with metadata, supply-chain verification, search API, version management.
- **Rationale:** OpenClaw's ClawHub has 5700+ skills. OCCP needs governed equivalent.
- **Acceptance Test:** (1) `occp skill publish` uploads. (2) Auto security scan. (3) Search returns ranked results. (4) Version pinning with lockfile.
- **Owner Module:** `cli/skills.py`, `api/routes/hub.py`

### REQ-MARKET-02: Plugin System
- **Description:** TS/Python plugin host with sandboxed execution, hot-loading, API versioning.
- **Acceptance Test:** (1) Plugin in `extensions/` auto-discovered. (2) Plugin crash doesn't crash host. (3) Plugin API version-pinned.
- **Owner Module:** `orchestrator/plugins.py`

---

## AUTO — Automation (OpenClaw Gap)

### REQ-AUTO-01: Cron Scheduler
- **Description:** Built-in cron with timezone support, retry, VAP enforcement.
- **Acceptance Test:** (1) `occp cron add "*/5 * * * *" --agent=reporter` works. (2) Tasks pass through VAP. (3) All executions audited.
- **Owner Module:** `orchestrator/cron.py`

### REQ-AUTO-02: Webhook Receiver
- **Description:** Inbound webhooks with HMAC-SHA256 verification, schema validation, routing.
- **Acceptance Test:** (1) Valid HMAC accepted. (2) Invalid returns 403. (3) Failed deliveries retried 3x.
- **Owner Module:** `api/routes/webhooks.py`

### REQ-AUTO-03: Event Triggers
- **Description:** Configurable triggers firing on audit events, health thresholds, webhook receipts.
- **Acceptance Test:** (1) Trigger fires within 500ms. (2) Definitions in version-controlled YAML. (3) Evaluation non-blocking.
- **Owner Module:** `orchestrator/triggers.py`

### REQ-AUTO-04: Workflow Templates
- **Description:** Pre-built deterministic workflow templates (YAML) for common automation patterns: approval chains, scheduled reports, data sync, alert escalation. Templates are parameterized, version-controlled, and signed.
- **Rationale:** Reduces agent creation barrier. Deterministic workflows (Lobster pattern) provide predictable execution outside LLM control loop.
- **Acceptance Test:** (1) ≥5 templates available at v1.0. (2) `occp workflow init --template=approval-chain` creates configured workflow. (3) Template execution enters full VAP pipeline. (4) Template signature verified before execution.
- **Owner Module:** `orchestrator/workflows.py`

---

## CORE — Core Pipeline Enhancement (OpenClaw Gap)

### REQ-CORE-01: Message Pipeline
- **Description:** 6-phase message pipeline normalizing all channel adapter messages into unified format before VAP.
- **Acceptance Test:** (1) Messages from 4 channels produce identical `InboundMessage`. (2) Full audit trail per message.
- **Owner Module:** `orchestrator/message_pipeline.py`

### REQ-CORE-02: Session Management
- **Description:** Session-scoped contexts: main/DM/group with isolated state, tools, resources.
- **Acceptance Test:** (1) Group session can't invoke main-only tools. (2) DM state invisible to other DMs.
- **Owner Module:** `orchestrator/sessions.py`

### REQ-CORE-03: Config-First Agent Definition
- **Description:** Markdown-based agent config (AGENT.md/SOUL.md/TOOLS.md) with hot-reload.
- **Acceptance Test:** (1) Placing AGENT.md auto-registers. (2) Edit updates within 5s. (3) Validated against schema.
- **Owner Module:** `orchestrator/config_loader.py`

### REQ-CORE-04: Local Model Support (Ollama)
- **Description:** OllamaPlanner adapter with circuit breaker and cloud fallback.
- **Acceptance Test:** (1) Connects to localhost:11434. (2) Falls back on failure. (3) Responses pass guards.
- **Owner Module:** `adapters/ollama_planner.py`

---

## MULTI — Multi-Tenancy (OpenClaw Gap)

### REQ-MULTI-01: Org-Scoped Data Isolation
- **Description:** Tenant-aware ORM, org-scoped encryption, org-scoped RBAC, cross-org query prevention.
- **Rationale:** OpenClaw explicitly doesn't support multi-tenant. OCCP targets enterprise.
- **Acceptance Test:** (1) Org A user gets 403 on Org B resources. (2) Direct DB query returns zero cross-org rows. (3) Pen test: zero leaks.
- **Owner Module:** `store/tenant.py`, `api/middleware.py`

### REQ-MULTI-02: Data Residency Controls
- **Description:** Per-org LLM routing (EU-only endpoints), database shard selection, audit log pinning.
- **Acceptance Test:** (1) EU org routes to EU endpoints only. (2) Residency immutable after creation.
- **Owner Module:** `config/residency.py`

---

## Requirement Count Summary

| Category | Count |
|----------|-------|
| GOV | 6 |
| POL | 3 |
| CPC | 4 |
| TSF | 5 |
| VSTA | 4 |
| MAO | 5 |
| CBDB | 5 |
| MCP | 4 |
| RT | 5 |
| CHAN | 5 |
| MEM | 3 |
| A2UI | 1 |
| SEC | 6 |
| COMP | 2 |
| SDK | 2 |
| MARKET | 2 |
| AUTO | 4 |
| CORE | 4 |
| MULTI | 2 |
| **TOTAL** | **72** |
