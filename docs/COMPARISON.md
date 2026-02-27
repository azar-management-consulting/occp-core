# Competitor Comparison

How OCCP compares to other agent control plane and orchestration frameworks.

## Feature Matrix

| Feature | OCCP | OpenClaw | Cordum | EV (eevee.build) | Kagent (CNCF) | OpenLeash | Leash (StrongDM) |
|---------|------|----------|--------|-------------------|---------------|-----------|------------------|
| **Core Model** | 5-stage Verified Autonomy Pipeline | Gateway hub-and-spoke | Safety Kernel | K8s resource model | K8s-native agent CRDs | Policy gate sidecar | Infra component (auth, Cedar, MCP observer) |
| **Governance** | Built-in (Casbin RBAC, 4 roles) | Third-party plugin (GatewayStack) | Built-in (policy-as-code) | Declarative YAML | K8s RBAC | Policy-as-code | Cedar policy engine |
| **License** | MIT | MIT | BUSL-1.1 | MIT | Apache 2.0 | MIT | Proprietary |
| **Audit Trail** | SHA-256 hash chain (tamper-evident) | None (default) | Full trail | N/A | K8s events | Local logs | Full trail |
| **Sandbox** | nsjail / bwrap / process (auto-fallback) | None | N/A | N/A | Container isolation | N/A | N/A |
| **Auth** | JWT + 4-role hierarchical RBAC | None (default, disabled) | Role-based | N/A | K8s ServiceAccount | N/A | MCP auth layer |
| **Policy Guards** | PII, prompt injection, resource limits | None built-in | Policy-as-code | N/A | N/A | Policy gate | Cedar policies |
| **API** | FastAPI REST + WebSocket | REST gateway | gRPC | K8s CRD | K8s CRD | N/A | REST |
| **Database** | SQLAlchemy 2.0 (SQLite/PostgreSQL) | File-based YAML | PostgreSQL | etcd | etcd | N/A | N/A |
| **CLI** | Full CLI (`occp start/demo/run/status`) | CLI available | CLI available | kubectl-based | kubectl-based | N/A | CLI available |
| **Dashboard** | Next.js real-time pipeline visualization | Web UI | Web UI | K8s dashboard | K8s dashboard | N/A | Web UI |
| **Pricing** | Free (open source) | Free (open source) | Free / Team / Enterprise | Free / Cloud (waitlist) | Free (open source) | Free (open source) | Commercial |

## Positioning

### OCCP vs OpenClaw

OpenClaw operates as a gateway hub-and-spoke model where agents connect to a central gateway. Governance is available only through the third-party GatewayStack plugin.

**OCCP advantage**: Governance is built into the protocol, not bolted on as a plugin. Every task passes through the Verified Autonomy Pipeline with mandatory policy gates, PII detection, and prompt injection blocking. The audit trail uses SHA-256 hash chaining for tamper evidence — something OpenClaw lacks entirely by default.

### OCCP vs Cordum

Cordum offers strong built-in governance with its Safety Kernel and policy-as-code approach. However, it uses the Business Source License 1.1 (BUSL-1.1), which restricts commercial use without a license.

**OCCP advantage**: MIT licensed — no usage restrictions for any purpose, commercial or otherwise. OCCP additionally provides sandboxed code execution (nsjail/bwrap/process auto-fallback) which Cordum does not offer.

### OCCP vs EV (eevee.build)

EV takes a Kubernetes-native approach using Custom Resource Definitions (CRDs) and declarative YAML for agent management. It targets teams already invested in the Kubernetes ecosystem.

**OCCP advantage**: Runtime enforcement, not just declarative resources. OCCP actively blocks policy violations in real-time during pipeline execution rather than relying on static configuration. Works anywhere Python runs — no Kubernetes dependency required.

### OCCP vs Kagent (CNCF)

Kagent is a CNCF sandbox project that provides Kubernetes-native agent management through Custom Resource Definitions. It targets DevOps teams already running Kubernetes clusters.

**OCCP advantage**: No Kubernetes dependency — runs anywhere Python runs with a 5-minute quickstart. OCCP provides a full-stack developer experience (dashboard, onboarding, CLI) rather than requiring kubectl expertise. Built-in policy guards (PII, prompt injection) operate at runtime, not just at the resource definition level.

### OCCP vs OpenLeash

OpenLeash provides a lightweight policy gate sidecar pattern for local-first agent control. It focuses on policy enforcement as a standalone component.

**OCCP advantage**: Full-stack platform vs. single component. OCCP includes dashboard, onboarding wizard, MCP integration, audit trail, and turnkey deployment. OpenLeash requires assembling additional components for a complete control plane.

### OCCP vs Leash (StrongDM)

Leash operates as an infrastructure component providing auth, Cedar policy engine, MCP observer, and audit capabilities. It focuses on the security and compliance layer.

**OCCP advantage**: End-to-end developer experience vs. infrastructure component. OCCP provides dashboard UX, one-click MCP installation, CLI tooling, and Docker Compose deployment out of the box. Leash requires integration into an existing platform. OCCP is MIT-licensed; Leash is proprietary.

## When to Choose OCCP

- You need **verified governance** built into the pipeline, not as an add-on
- You want **MIT-licensed** software with no commercial restrictions
- You need **tamper-evident audit trails** with cryptographic hash chains
- You want **sandboxed execution** for agent-generated code
- You need a solution that runs on **any Linux/macOS system** without Kubernetes
- You want a **single-binary deployment** path (Docker Compose or bare metal)
