# Competitor Comparison

How OCCP compares to other agent control plane and orchestration frameworks.

## Feature Matrix

| Feature | OCCP | OpenClaw | Cordum | EV (eevee.build) |
|---------|------|----------|--------|-------------------|
| **Core Model** | VAP pipeline (5-stage verified autonomy) | Gateway hub-and-spoke | Safety Kernel | K8s resource model |
| **Governance** | Built-in (Casbin RBAC, 4 roles) | Third-party plugin (GatewayStack) | Built-in (policy-as-code) | Declarative YAML |
| **License** | MIT | MIT | BUSL-1.1 | MIT |
| **Audit Trail** | SHA-256 hash chain (tamper-evident) | None (default) | Full trail | N/A |
| **Sandbox** | nsjail / bwrap / process (auto-fallback) | None | N/A | N/A |
| **Auth** | JWT + 4-role hierarchical RBAC | None (default, disabled) | Role-based | N/A |
| **Policy Guards** | PII, prompt injection, resource limits | None built-in | Policy-as-code | N/A |
| **API** | FastAPI REST + WebSocket | REST gateway | gRPC | K8s CRD |
| **Database** | SQLAlchemy 2.0 (SQLite/PostgreSQL) | File-based YAML | PostgreSQL | etcd |
| **CLI** | Full CLI (`occp start/demo/run/status`) | CLI available | CLI available | kubectl-based |
| **Dashboard** | Next.js real-time pipeline visualization | Web UI | Web UI | K8s dashboard |
| **Pricing** | Free (open source) | Free (open source) | Free / Team / Enterprise | Free / Cloud (waitlist) |

## Positioning

### OCCP vs OpenClaw

OpenClaw operates as a gateway hub-and-spoke model where agents connect to a central gateway. Governance is available only through the third-party GatewayStack plugin.

**OCCP advantage**: Governance is built into the protocol, not bolted on as a plugin. Every task passes through the VAP pipeline with mandatory policy gates, PII detection, and prompt injection blocking. The audit trail uses SHA-256 hash chaining for tamper evidence — something OpenClaw lacks entirely by default.

### OCCP vs Cordum

Cordum offers strong built-in governance with its Safety Kernel and policy-as-code approach. However, it uses the Business Source License 1.1 (BUSL-1.1), which restricts commercial use without a license.

**OCCP advantage**: MIT licensed — no usage restrictions for any purpose, commercial or otherwise. OCCP additionally provides sandboxed code execution (nsjail/bwrap/process auto-fallback) which Cordum does not offer.

### OCCP vs EV (eevee.build)

EV takes a Kubernetes-native approach using Custom Resource Definitions (CRDs) and declarative YAML for agent management. It targets teams already invested in the Kubernetes ecosystem.

**OCCP advantage**: Runtime enforcement, not just declarative resources. OCCP actively blocks policy violations in real-time during pipeline execution rather than relying on static configuration. Works anywhere Python runs — no Kubernetes dependency required.

## When to Choose OCCP

- You need **verified governance** built into the pipeline, not as an add-on
- You want **MIT-licensed** software with no commercial restrictions
- You need **tamper-evident audit trails** with cryptographic hash chains
- You want **sandboxed execution** for agent-generated code
- You need a solution that runs on **any Linux/macOS system** without Kubernetes
- You want a **single-binary deployment** path (Docker Compose or bare metal)
