'use strict';
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.join(__dirname, 'articles');
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

// ─── Article data ────────────────────────────────────────────────────────────
const articles = [
  {
    id: '001', date: '2025-10-15', tag: 'vision', version: '',
    title: 'Why We Built OCCP: The Case for a New AI Orchestration Layer',
    slug: 'why-we-built-occp',
    excerpt: 'The infrastructure layer that enterprise AI has been missing — and why the time to build it is now.',
    readTime: '9 min read',
    body: `
<p>In the autumn of 2025, a question kept surfacing in conversations with enterprise engineering teams: <em>who is responsible for what the AI agent actually does?</em> Not who wrote the prompt. Not who approved the model. But who owns the runtime behaviour — the sequence of actions an autonomous system takes between receiving a task and returning a result. The answer, almost universally, was: nobody. That gap is why we built OCCP.</p>

<h2>The Invisible Layer Problem</h2>
<p>Modern AI deployments have become surprisingly sophisticated at the edges. Foundation model providers offer increasingly capable APIs. Prompt engineering has matured into a recognised discipline. Vector databases, retrieval-augmented generation pipelines, and fine-tuning workflows are well-understood. Yet between the model call and the business outcome sits a vast, largely uncharted territory: the orchestration layer.</p>
<p>This layer coordinates task decomposition, manages agent lifecycles, routes tool calls, enforces resource limits, and — critically — decides what the system is permitted to do. In most current deployments, this logic is scattered across application code, hidden in LangChain chains, embedded in custom Python scripts, or simply absent. The result is AI systems that are powerful but ungovernable.</p>
<p>Ungovernable AI is not merely a compliance risk, though it certainly is that. It is a product quality risk. When an autonomous agent can take arbitrary tool actions without a coherent governance layer, debugging becomes archaeology. Audit trails are incomplete or nonexistent. Rollback is impossible. The business cannot answer the most basic operational question: what did our AI system do, exactly, and why?</p>

<h2>Why Existing Tools Fall Short</h2>
<p>The obvious question is: why not use one of the existing orchestration frameworks? We evaluated them carefully. Most fell into one of two categories. The first category prioritises developer experience — low friction, rapid prototyping, expressive APIs — but treats governance as an afterthought. Policy hooks, if they exist at all, are bolt-ons rather than first-class primitives. The second category prioritises enterprise features but is so heavyweight that adoption becomes a multi-quarter project, by which time the AI landscape has shifted under your feet.</p>
<p>Neither category treats the <strong>verified autonomy pipeline</strong> as a core architectural concept. The idea that every agent action should flow through a plan-gate-execute-validate cycle — with cryptographic evidence of each step — simply does not appear in the design of existing tools. This is the gap that the next-generation AI orchestration platform must address.</p>
<p>There is also a cultural dimension. Many existing frameworks were designed by researchers or startup engineers who have never operated AI systems at enterprise scale. The assumptions baked into their designs — that you control the model, that latency is acceptable, that security is someone else's problem — are incompatible with the realities of regulated industries, multi-tenant deployments, and genuine production operations.</p>

<h2>First Principles: What an Orchestration Layer Must Do</h2>
<p>Before writing a single line of code, we spent several weeks articulating what the orchestration layer must actually accomplish. We identified six non-negotiable requirements:</p>
<ul>
  <li><strong>Deterministic audit trails.</strong> Every action, decision, and output must be recorded in a tamper-evident log. Not just logged — cryptographically chained so that any retrospective modification is detectable.</li>
  <li><strong>Policy-as-code governance.</strong> Permissions, constraints, and approval workflows must be expressed as code, version-controlled, and evaluated at runtime — not configured through a GUI that nobody can diff.</li>
  <li><strong>Sandbox isolation.</strong> Agent execution must be isolated from the host environment. Tool calls should run in constrained contexts with explicit capability grants, not with ambient permissions.</li>
  <li><strong>Protocol-agnostic integration.</strong> The orchestration layer must not assume a particular model provider, tool protocol, or deployment topology. Pluggability is not a nice-to-have; it is a survival requirement in a market that changes quarterly.</li>
  <li><strong>Observable by default.</strong> Metrics, traces, and structured logs must be emitted without configuration. Observability cannot be an add-on.</li>
  <li><strong>Human override at every gate.</strong> The system must support synchronous human-in-the-loop approval for high-risk actions, with clear escalation paths and timeout handling.</li>
</ul>
<p>These requirements shaped every subsequent architectural decision. They explain why OCCP is not a wrapper around an existing framework. Building on foundations that do not share these principles would mean fighting the framework at every step.</p>

<h2>The Market Inflection Point</h2>
<p>We also recognised that 2025 represented a genuine inflection point for enterprise AI adoption. Three forces were converging simultaneously. First, foundation models had crossed a capability threshold where fully autonomous task completion became viable for a broad class of business processes — not just narrow, well-defined tasks but genuinely open-ended work. Second, regulatory pressure was intensifying: the EU AI Act, sector-specific guidance from financial regulators, and emerging standards around AI transparency were creating compliance obligations that could not be met with ungoverned systems. Third, the security community had begun publishing serious research on prompt injection, model manipulation, and supply chain attacks against AI systems — threats that required infrastructure-level defences, not application-level patches.</p>
<p>The confluence of capability, compliance, and security pressure meant that the market was about to demand exactly the kind of <strong>enterprise-grade AI governance</strong> infrastructure that OCCP was designed to provide. The question was not whether this category would exist, but who would define it.</p>

<h2>What OCCP Is, and What It Is Not</h2>
<p>OCCP is an <strong>autonomous workflow engine</strong> with governance at its core. It is the layer between your application code and your AI agents — the control plane that ensures agents act within defined boundaries, every action is auditable, and the system remains operable as complexity scales.</p>
<p>It is not a model provider. It is not a prompt library. It is not a chatbot framework. OCCP does not care which foundation model you use, which cloud provider you run on, or which industry you operate in. It provides the infrastructure primitives — policy evaluation, audit chaining, sandbox isolation, capability management — that allow organisations to deploy agent-driven automation with genuine confidence.</p>
<p>The <strong>verified autonomy pipeline</strong> is the central concept: a formal, auditable cycle that every agent action must traverse. Plan first, gate against policy, execute in isolation, validate the result, then ship or escalate. This cycle is not optional. It is not configurable out of existence. It is the foundation on which trust in autonomous systems is built.</p>

<blockquote>"The question is not whether AI agents can be autonomous. They clearly can. The question is whether they can be autonomously trustworthy — and that requires infrastructure, not just models."</blockquote>

<h2>The Road Ahead</h2>
<p>Building OCCP means building a new category. That is harder than building a better product in an existing category. It requires educating the market about problems they may not yet have articulated, demonstrating value in contexts where the alternatives are hand-rolled solutions of uncertain quality, and maintaining the discipline to stay focused on infrastructure rather than being seduced by the application layer above.</p>
<p>We believe the infrastructure layer for enterprise AI governance is one of the most important software problems of this decade. The organisations that get it right — that build agent-driven automation on foundations of genuine accountability and control — will operate with capabilities their competitors cannot match. Those that skip the governance layer will find, sooner or later, that the costs of ungovernable AI are higher than they anticipated.</p>
<p>This is why we built OCCP. Not because it was easy, but because the alternative — a world of powerful, ungovernable AI systems deployed at scale in enterprises — is a world none of us want to operate in.</p>

<div class="summary-box">
  <h3>// Key Takeaways</h3>
  <ul>
    <li>The orchestration layer between model APIs and business outcomes is largely ungoverned in current deployments</li>
    <li>Six non-negotiable requirements drove OCCP's architecture from first principles</li>
    <li>Capability, compliance, and security pressures are converging to create demand for AI governance infrastructure</li>
    <li>OCCP is a control plane — not a model, prompt library, or framework wrapper</li>
    <li>The verified autonomy pipeline is the core concept: every agent action must be planned, gated, executed, validated</li>
  </ul>
</div>
`
  },
  {
    id: '002', date: '2025-10-22', tag: 'architecture', version: '',
    title: 'Designing the Verified Autonomy Pipeline: First Principles',
    slug: 'designing-verified-autonomy-pipeline',
    excerpt: 'How we designed a five-stage pipeline that turns autonomous AI actions into auditable, reversible, policy-governed operations.',
    readTime: '10 min read',
    body: `
<p>The Verified Autonomy Pipeline (VAP) is the architectural heart of OCCP. Every agent action, every tool call, every workflow step flows through it. Understanding why it is designed the way it is requires understanding the failure modes it was built to prevent — and the engineering trade-offs that shaped each of its five stages.</p>

<h2>The Problem with Unstructured Agent Execution</h2>
<p>When an LLM agent executes a task without a formal pipeline, the typical flow looks something like this: receive input, reason about it internally, emit a sequence of tool calls, collect results, reason again, emit more tool calls, eventually produce an output. This loop is powerful and flexible, but it has several properties that make it unsuitable for enterprise deployment at scale.</p>
<p>First, it is opaque. The reasoning steps are embedded in the model's context window and are not externally observable except through the final output. Second, it is ungated. Nothing prevents the agent from calling tools in sequences that are individually permitted but collectively problematic. Third, it is non-deterministic in ways that matter operationally — the same input can produce different tool call sequences across runs, making reproducibility and debugging extraordinarily difficult.</p>
<p>The VAP addresses all three problems by imposing structure on the execution flow without constraining the agent's reasoning capability. The pipeline does not make agents less capable; it makes their capabilities governable.</p>

<h2>Stage One: Plan</h2>
<p>The first stage of the VAP is task decomposition and risk assessment. Before any tool calls are made, the agent must produce a structured plan: a sequence of intended actions, each annotated with a capability requirement and a risk classification. This plan is not merely advisory — it is the basis for gate evaluation in stage two.</p>
<p>The planning stage enforces several important properties. It makes the agent's intentions explicit before they are executed, creating a record of what was intended versus what actually happened. It enables risk-proportionate governance: a plan consisting entirely of read operations can be auto-approved, while a plan including filesystem writes or external API calls requires policy evaluation. And it creates a natural checkpoint for human-in-the-loop review when the risk classification exceeds a configurable threshold.</p>
<p>Designing the planning stage required resolving a genuine tension. On one hand, we wanted plans to be detailed enough to be meaningful for governance purposes. On the other hand, overly rigid planning requirements would create a bureaucratic overhead that made the system impractical for fast-moving workloads. The solution was a tiered planning model: lightweight plans for low-risk, well-understood task types; detailed plans with explicit capability declarations for novel or high-risk tasks.</p>

<h2>Stage Two: Gate</h2>
<p>The gate stage is where the policy engine evaluates the plan against the applicable rule set. This is the most architecturally significant stage of the pipeline because it is where governance becomes operational rather than aspirational.</p>
<p>The gate evaluator receives the structured plan from stage one, the agent's identity and capability set, the current policy context (which may vary by tenant, environment, or time of day), and any relevant historical data about the agent's behaviour. It produces a verdict: approve, deny, or escalate. Escalation triggers a human approval workflow; denial produces a structured error that the agent can reason about and potentially replan around.</p>
<p>A key design decision was to make policy evaluation synchronous and blocking. This was a deliberate choice that surprised some early reviewers who expected an asynchronous governance model. The reasoning is simple: asynchronous governance means the action may have already been taken by the time the policy verdict arrives. For irreversible or high-impact actions, that is unacceptable. Synchronous gating adds latency — typically under 20 milliseconds for cache-warm policy evaluation — but provides hard guarantees that no out-of-policy action can execute.</p>

<h2>Stage Three: Execute</h2>
<p>Execution in the VAP happens inside a sandbox. The isolation layer ensures that even if an agent's behaviour is unexpected — whether due to model error, prompt manipulation, or adversarial input — the blast radius is bounded. Tool calls are routed through a capability-checked dispatcher that verifies each call against the approved plan before forwarding it to the underlying tool implementation.</p>
<p>The execution stage captures a complete trace of every tool call, including inputs, outputs, timing, and any errors. This trace is the raw material for the audit chain in stage four. The executor also enforces resource limits — maximum execution time, maximum memory consumption, maximum number of tool calls — that prevent runaway agents from consuming shared infrastructure.</p>
<p>Sandbox implementation is necessarily platform-specific. The <strong>secure MCP integration</strong> layer abstracts over different isolation primitives — namespace-based isolation on Linux, process-level isolation on other platforms — so that the VAP can operate across deployment environments without requiring changes to higher-level code. This abstraction was harder to build than it sounds; isolation primitives vary significantly in their semantics and their performance characteristics.</p>

<h2>Stage Four: Validate</h2>
<p>After execution completes, the validate stage performs two functions: quality assessment and audit chain extension. Quality assessment applies a configurable set of output validators — type checking, schema validation, PII detection, and policy-specific checks — to the execution results. If validation fails, the pipeline can retry execution (with limits), escalate to a human reviewer, or return a structured error.</p>
<p>Audit chain extension is the mechanism by which OCCP provides tamper-evident execution records. Each completed execution produces a signed record that includes the plan, the gate verdict, the execution trace, the validation results, and a cryptographic link to the previous record in the chain. The SHA-256 hash chain means that any retrospective modification of the audit log is detectable — not because we assume bad actors inside the system, but because tamper evidence is a compliance requirement for regulated industries and a trust requirement for enterprise customers.</p>

<h2>Stage Five: Ship</h2>
<p>The final stage handles result delivery, workflow continuation, and post-execution housekeeping. In simple cases, ship means returning the execution result to the caller. In complex workflows, it means feeding results into the next pipeline stage, updating workflow state, and triggering any downstream processes that depend on the completed action.</p>
<p>The ship stage also handles the case where execution produced a result that satisfies the immediate task but has implications for future tasks. Capability learning — the ability of the system to refine its risk assessments based on observed execution patterns — happens at the ship stage, feeding back into the planning and gating stages for future runs.</p>

<blockquote>"Every architectural decision in the VAP reflects a single underlying principle: autonomous action without accountability is not autonomy — it is unpredictability with extra steps."</blockquote>

<h2>Trade-offs and Lessons</h2>
<p>The VAP design involves real trade-offs. The synchronous gate adds latency. The planning requirement adds overhead for simple tasks. The audit chain adds storage costs. We made these trade-offs deliberately, prioritising governance fidelity over raw throughput, because we believe the governance properties are what make <strong>enterprise-grade AI governance</strong> viable in practice.</p>
<p>Building the pipeline also taught us that the most important design decisions are not the obvious ones. The obvious decisions — what to log, how to evaluate policy — are hard but tractable. The subtle decisions — how to handle partial failures mid-pipeline, how to maintain pipeline integrity under concurrent execution, how to make the pipeline observable without making it a performance bottleneck — are where the real engineering challenges live.</p>

<div class="summary-box">
  <h3>// Key Takeaways</h3>
  <ul>
    <li>The VAP imposes structure on agent execution without constraining reasoning capability</li>
    <li>Five stages: Plan, Gate, Execute, Validate, Ship — each with distinct governance responsibilities</li>
    <li>Synchronous gating was a deliberate choice to prevent policy bypass through timing</li>
    <li>The SHA-256 audit chain provides tamper-evident execution records for compliance</li>
    <li>Real trade-offs: latency and overhead in exchange for hard governance guarantees</li>
  </ul>
</div>
`
  },
  {
    id: '003', date: '2025-10-30', tag: 'vision', version: '',
    title: 'Beyond Prompt Engineering: Why AI Needs Governance Infrastructure',
    slug: 'beyond-prompt-engineering',
    excerpt: 'Prompt engineering optimises what AI systems do. Governance infrastructure determines what they are permitted to do — and ensures there is evidence of both.',
    readTime: '9 min read',
    body: `
<p>The prompt engineering discipline has matured remarkably quickly. In two years, it has gone from a collection of informal techniques shared on Twitter threads to a body of practice complete with structured methodologies, evaluation frameworks, and specialist roles at major technology companies. This maturation is genuinely valuable. Better prompts produce better model outputs, and better model outputs are the foundation of useful AI applications.</p>
<p>But prompt engineering has a ceiling. It optimises the interface between human intent and model behaviour — a critically important interface, but only one of the surfaces that determines whether an AI system is safe, compliant, and operationally trustworthy. The surfaces that prompt engineering cannot address — runtime governance, capability management, audit accountability, policy enforcement — require infrastructure, not prompting technique.</p>

<h2>What Prompt Engineering Actually Solves</h2>
<p>To understand what prompt engineering cannot solve, it helps to be precise about what it can. Prompt engineering addresses the problem of eliciting desired behaviour from a language model given a particular input. It provides techniques for structuring instructions, providing examples, managing context length, decomposing complex tasks, and reducing unwanted outputs. These are genuine and important capabilities.</p>
<p>What prompt engineering does not address is the environment in which the model operates. It cannot prevent a well-prompted model from being fed adversarial inputs by a downstream user. It cannot ensure that the tools the model has access to are the tools it should have access to in a given context. It cannot produce an audit trail that satisfies regulatory requirements. It cannot enforce rate limits, spending caps, or approval workflows. These are infrastructure concerns, and infrastructure is not promptable.</p>
<p>This distinction matters because it clarifies the respective domains of prompt engineering and governance infrastructure. They are not competing approaches — they are complementary layers. Prompt engineering optimises behaviour within the space of permitted actions; governance infrastructure defines and enforces what that space is.</p>

<h2>The Compliance Gap in Current AI Deployments</h2>
<p>Consider the compliance requirements of a regulated industry — financial services, healthcare, or critical infrastructure. These industries require demonstrable controls over automated systems: evidence that the system behaved as intended, that deviations were detected and logged, that human oversight was exercised where required, and that the audit trail has not been modified after the fact.</p>
<p>None of these requirements can be met through prompt engineering. A system prompt that says "always comply with financial regulations" is not a control. It is a hope. Regulators, rightly, do not accept hopes as evidence of compliance. What they require is infrastructure: systems with deterministic behaviour in defined contexts, observable outputs, tamper-evident logs, and documented approval workflows.</p>
<p>The EU AI Act makes this explicit. High-risk AI systems must implement technical documentation, logging, human oversight mechanisms, and accuracy and robustness requirements. These are infrastructure requirements. Satisfying them requires building governance infrastructure as a first-class concern, not as an afterthought applied to a system designed without it.</p>

<h2>The Security Gap in Current AI Deployments</h2>
<p>The security picture is equally concerning. Prompt injection — the technique of embedding adversarial instructions in inputs to manipulate model behaviour — has gone from a theoretical concern to a practical attack vector in production systems. Supply chain attacks against AI systems, including compromised model weights and poisoned training data, are increasingly documented. Model output containing sensitive data from the training corpus or from in-context documents is a recurring incident type.</p>
<p>Prompt engineering provides partial defences against some of these attacks. Careful instruction structuring can make prompt injection harder. Output formatting constraints can reduce (but not eliminate) data leakage. But these are probabilistic defences, not deterministic controls. Against a determined attacker with knowledge of the model's instruction-following behaviour, prompt-level defences provide limited assurance.</p>
<p>Infrastructure-level defences operate differently. Input validation and sanitisation at the orchestration layer can detect and block known injection patterns before they reach the model. Output filtering can enforce constraints on what the system returns, regardless of what the model produced. Capability restriction can ensure that even a successfully manipulated model cannot access tools or data it should not have access to. These defences are not foolproof — no security measure is — but they are deterministic where prompt-level defences are probabilistic.</p>

<h2>Governance as a Product Property</h2>
<p>There is a third reason why governance infrastructure matters beyond compliance and security: it is increasingly a product differentiator. Enterprise buyers evaluating AI platforms are asking harder questions than they were two years ago. Can you demonstrate that your system acted within policy? Can you show me the audit trail for this decision? What happens when the model is wrong — can we roll back? Who approved this action?</p>
<p>The organisations that can answer these questions with technical evidence rather than vague assurances will win enterprise deals. Those that cannot will find themselves relegated to lower-stakes use cases where governance requirements are less stringent — or find that their ungoverned deployments become the subject of the next major AI incident report.</p>
<p><strong>Enterprise-grade AI governance</strong> is not a compliance tax on AI development. It is the infrastructure that enables AI systems to be deployed in contexts where they can create the most value — high-stakes, high-complexity, high-trust environments where the potential impact of both success and failure is substantial.</p>

<h2>The Infrastructure Deficit</h2>
<p>The gap between where the industry is and where it needs to be is significant. Most organisations deploying AI today are doing so with minimal governance infrastructure. They have prompt engineering; they may have some logging; they probably have rate limiting at the API level. But they do not have policy-as-code governance, verified audit chains, or capability-based access control for their agents.</p>
<p>This deficit is partly a consequence of the speed of AI adoption — the technology moved faster than the governance tooling. It is partly a consequence of the tooling landscape — until recently, production-grade AI governance infrastructure simply did not exist as a product category. And it is partly a consequence of incentive misalignment — the people who build AI applications are optimised for capability and speed, not governance and compliance.</p>
<p>The <strong>next-generation AI orchestration platform</strong> must address this deficit by making governance infrastructure as easy to adopt as the capability tooling that preceded it. That means clean APIs, good documentation, clear upgrade paths, and a developer experience that does not make governance feel like a burden. OCCP is built on the conviction that governance and developer productivity are not in tension — they are complementary, and building the infrastructure that proves it is one of the defining challenges of this moment in AI development.</p>

<blockquote>"Governance infrastructure is not the opposite of AI capability. It is what makes AI capability trustworthy at scale."</blockquote>

<div class="summary-box">
  <h3>// Key Takeaways</h3>
  <ul>
    <li>Prompt engineering and governance infrastructure are complementary, not competing</li>
    <li>EU AI Act and sector regulations require infrastructure-level controls, not prompt-level hopes</li>
    <li>Infrastructure defences are deterministic; prompt defences are probabilistic</li>
    <li>Governance is increasingly a product differentiator for enterprise AI buyers</li>
    <li>The infrastructure deficit in current deployments represents a significant operational risk</li>
  </ul>
</div>
`
  },
  {
    id: '004', date: '2025-11-05', tag: 'milestone', version: 'v0.1.0',
    title: 'OCCP v0.1.0: The First Verified Orchestration Cycle',
    slug: 'occp-v010-first-cycle',
    excerpt: 'The first release of OCCP establishes the core modules — orchestrator, policy engine, CLI, and SDK — and completes the first end-to-end verified autonomy pipeline execution.',
    readTime: '8 min read',
    body: `
<p>v0.1.0 is not a polished product release. It is a proof of concept that answers the most fundamental question we had been carrying since the project started: can we build a verified autonomy pipeline that actually runs? The answer, as of November 5, 2025, is yes. This post is a record of what we built, how we built it, and what we learned in the process.</p>

<h2>What Ships in v0.1.0</h2>
<p>The v0.1.0 release contains four core modules, each implementing a distinct layer of the OCCP architecture. These modules are not complete — they are deliberately minimal, built to demonstrate integration rather than exhaustive functionality. The goal was a working end-to-end pipeline, not a feature-complete product.</p>
<p>The <strong>orchestrator</strong> module handles workflow scheduling and agent lifecycle management. In v0.1.0 it supports sequential workflow execution, basic agent registration, and the first implementation of the VAP cycle. Concurrent execution, workflow branching, and agent pool management are on the roadmap but not present in this release.</p>
<p>The <strong>policy engine</strong> module provides the governance layer. It evaluates agent plans against a policy ruleset, produces approve/deny/escalate verdicts, and maintains the SHA-256 audit chain. The policy language in v0.1.0 is intentionally simple — a structured rule format that is readable by non-specialists. More expressive policy languages are planned for future releases.</p>
<p>The <strong>CLI</strong> provides the primary interface for this release. We made a deliberate choice to start without a dashboard — more on that decision in a separate post — which means v0.1.0 is entirely command-line driven. The CLI supports starting the orchestrator, registering agents, submitting tasks, and inspecting the audit log.</p>
<p>The <strong>SDK</strong> provides Python and TypeScript clients for integrating OCCP into existing applications. The v0.1.0 SDK is thin — it wraps the orchestrator's internal interfaces rather than a stable external API — but it establishes the patterns that the production SDK will follow.</p>

<h2>The First Verified Pipeline Execution</h2>
<p>The milestone we were working toward with v0.1.0 was a complete end-to-end execution of the verified autonomy pipeline. On November 4, 2025, we achieved it: a test agent received a task, produced a plan, passed through the gate, executed a set of tool calls in a sandboxed environment, had its output validated, and produced a complete audit record — all within a single coherent pipeline run.</p>
<p>The test task was deliberately simple: summarise a text document and extract key entities. The point was not to demonstrate sophisticated AI capability but to exercise every stage of the pipeline with a real execution. The result was a complete VAP cycle with a 47-entry audit trail, a cryptographically chained execution record, and a validated output — all produced without manual intervention.</p>
<p>This might sound modest. In the context of what we were building, it was not. Completing the first verified pipeline execution required resolving dozens of integration challenges: the policy engine needed to understand the plan format produced by the orchestrator; the sandbox needed to be able to execute tool calls without breaking the audit chain; the validator needed to receive execution traces in a format it could process. Every one of these integrations involved design decisions that will shape the architecture for the foreseeable future.</p>

<h2>Architecture Decisions Made in v0.1.0</h2>
<p>Three architectural decisions made in v0.1.0 deserve particular attention because they constrain future development in ways that are worth documenting now, while the reasoning is fresh.</p>
<p>First, we chose to make the audit chain append-only and synchronous. This means audit writes happen in the critical path of execution — they add latency. We considered an asynchronous audit pipeline, which would add no latency, but rejected it because asynchronous writes create windows where execution has occurred but has not been recorded. For a governance tool, that gap is unacceptable. The latency cost of synchronous audit writes is a deliberate architectural tax on throughput in exchange for guaranteed audit completeness.</p>
<p>Second, we chose a structured plan format over free-form agent reasoning. This means agents cannot currently express plans in natural language — they must produce structured output that conforms to a schema. This is more restrictive but far more governable. A natural-language plan cannot be reliably evaluated by a policy engine; a structured plan can. We may relax this constraint in the future, but we will do so carefully.</p>
<p>Third, we chose to make the policy engine stateless. Each gate evaluation is independent — it does not depend on previous evaluations. This makes the policy engine easier to reason about and easier to scale, but it means policy cannot currently express rules like "this agent has made three suspicious requests in the last hour." Stateful policy evaluation is on the roadmap.</p>

<h2>What v0.1.0 Does Not Do</h2>
<p>v0.1.0 does not have a REST API, a dashboard, JWT authentication, or any production-ready deployment infrastructure. It does not support concurrent agent execution. It does not integrate with external model providers — it uses a mock LLM for testing purposes. It does not have a stable external API; the interfaces will change.</p>
<p>These are not oversights — they are deliberate scope decisions. Building a governance layer correctly requires starting with the governance primitives, not with the deployment infrastructure. The production platform — API, authentication, dashboard, deployment tooling — comes in subsequent releases once the governance foundation is solid.</p>

<blockquote>"Getting the governance primitives right in v0.1.0 is more important than getting the developer experience right. You can improve a developer experience later; you cannot retrofit governance onto a system designed without it."</blockquote>

<h2>What We Learned</h2>
<p>Building v0.1.0 confirmed several hypotheses and challenged several others. The hypothesis that the VAP could be implemented as a clean, composable pipeline was confirmed — the five stages integrate more cleanly than expected. The hypothesis that policy evaluation could be made fast enough to not be a practical bottleneck was confirmed — median gate latency in our test environment is 8 milliseconds.</p>
<p>The challenge was the audit chain. We underestimated the complexity of maintaining chain integrity under error conditions. When an execution fails mid-pipeline, the audit chain must still be updated — but with a failure record, not a success record. Handling this correctly required several iterations of the chain management code and produced the most complex test cases in the v0.1.0 test suite.</p>

<div class="summary-box">
  <h3>// Key Takeaways</h3>
  <ul>
    <li>v0.1.0 ships four core modules: orchestrator, policy engine, CLI, SDK</li>
    <li>First end-to-end VAP execution completed on November 4, 2025</li>
    <li>Three key architectural decisions: synchronous audit, structured plans, stateless policy</li>
    <li>No REST API, dashboard, or production deployment infrastructure — deliberate scope decision</li>
    <li>Audit chain integrity under error conditions was the hardest v0.1.0 engineering challenge</li>
  </ul>
</div>
`
  },
  {
    id: '005', date: '2025-11-10', tag: 'architecture', version: 'v0.1.0',
    title: 'Inside the Policy Engine: Code-Level Governance for LLM Actions',
    slug: 'policy-engine-governance',
    excerpt: 'How OCCP\'s policy engine evaluates agent plans against structured rulesets to produce deterministic governance verdicts at runtime.',
    readTime: '9 min read',
    body: `
<p>The policy engine is the component of OCCP that most directly embodies the principle of governance-as-infrastructure. It is not a configuration panel, a set of guidelines, or a list of prohibited behaviours. It is a runtime evaluation system that takes a structured representation of an agent's intended actions, applies a versioned ruleset, and produces a deterministic verdict: approve, deny, or escalate. This post describes how it works and why it is designed the way it is.</p>

<h2>Why Policy-as-Code Matters</h2>
<p>The alternative to policy-as-code is policy-as-prose. Most organisations that think carefully about AI governance write their policies as documents: use cases that are permitted, use cases that are prohibited, approval workflows for ambiguous cases. These documents have real value — they represent serious thinking about governance requirements — but they have a critical limitation: they cannot be evaluated at runtime.</p>
<p>A policy document that says "agents must not access customer data without explicit authorisation" cannot be checked by a computer. It can be read by a human reviewer, but humans are not present for every agent action in a production system. Policy-as-code addresses this by expressing governance rules in a form that can be evaluated programmatically, deterministically, and at the speed of machine execution rather than human review.</p>
<p>The challenge of policy-as-code for AI systems is that AI actions are less structured than the database operations or API calls that traditional policy frameworks were designed to govern. An agent might decide to take a novel sequence of individually-permitted actions that collectively constitute a policy violation. Governing this requires a policy language expressive enough to capture intent and context, not just individual action types.</p>

<h2>Policy Language Design</h2>
<p>The v0.1.0 policy language is deliberately simple. A policy is a collection of rules; each rule has a condition and an effect. The condition is a structured predicate over the agent's plan — it can reference the action types in the plan, the capabilities the agent has declared, the risk classification the agent has assigned, and contextual attributes like the time of day or the tenant identity. The effect is one of: allow, deny, or escalate.</p>
<p>Rules are evaluated in priority order. The first matching rule determines the verdict. If no rule matches, the default verdict is deny — a fail-closed posture that errs on the side of caution. This default is configurable but the configuration requires explicit opt-out, not opt-in, reinforcing the principle that ungoverned action is not the default.</p>
<p>A simple example: a rule that allows read-only tool calls for agents with the <code>read</code> capability, denies write tool calls without explicit authorisation, and escalates any plan that includes external network requests. This three-rule policy covers a substantial portion of common governance requirements for document processing workflows without requiring complex rule logic.</p>

<h2>Plan Representation</h2>
<p>Policy evaluation is only as good as the plan representation it operates on. A plan that accurately represents the agent's intended actions enables precise governance; a plan that omits or misrepresents actions enables governance bypass. This creates a fundamental tension: we want plans to be generated by agents (because only the agent knows what it intends to do), but we also want plans to be accurate (because inaccurate plans defeat the governance purpose).</p>
<p>Our approach to this tension in v0.1.0 is threefold. First, we require structured plan output rather than natural language — the plan must conform to a schema, which makes omission or misrepresentation mechanically harder. Second, we validate the plan's internal consistency: an agent that declares it will only use read capabilities but includes write tool calls in its plan will fail validation before the plan reaches the policy engine. Third, we compare the approved plan against the actual execution trace in the validate stage, flagging divergences for review.</p>
<p>This three-layer approach reduces but does not eliminate the risk of plan-execution divergence. A sufficiently sophisticated agent could produce a plan that passes all three checks while performing undeclared actions — but doing so would require actively defeating governance mechanisms in ways that should be detectable through other signals.</p>

<h2>Performance Architecture</h2>
<p>Policy evaluation sits in the critical path of every agent action. If it is slow, the entire system is slow. Our performance target for gate evaluation was a median latency of under 10 milliseconds for cache-warm policy evaluation, with a 99th percentile under 50 milliseconds. These targets are aggressive but achievable with the right architecture.</p>
<p>The key optimisation is policy compilation. Raw policy files are parsed and compiled into an optimised representation at system startup and whenever the policy is updated. The compiled representation is designed for fast evaluation — condition checking is reduced to a sequence of attribute lookups and comparisons rather than expression parsing. This compilation step means policy updates have a brief startup cost but essentially zero runtime cost per evaluation.</p>
<p>Policy caching adds another layer of performance. For repeated evaluations of identical (agent identity, plan type, context) tuples — which are common in production workloads where many agents are performing similar tasks — the compiled verdict can be cached with a short TTL. Cache invalidation is triggered by any policy update.</p>

<h2>Audit Integration</h2>
<p>Every policy evaluation produces an audit record: the input (agent identity, plan, context), the verdict, the rule that matched, and the evaluation timestamp. This record is appended to the audit chain in the same transaction as the verdict delivery to the orchestrator. The design ensures that there is no window between "policy evaluated" and "evaluation recorded" — both happen atomically or neither happens.</p>
<p>The audit record for a denied action is particularly important. It tells the operator not just that an action was denied, but which rule denied it, what the agent's plan contained, and what the agent's identity was at the time of the request. This information is essential for both compliance reporting and for debugging unexpected denials — which do happen, especially during the initial period of policy deployment when rule calibration is ongoing.</p>

<blockquote>"A policy engine that cannot explain its denials is not a governance tool — it is a black box. Every denial record in OCCP includes the rule that matched, so operators always know why an action was blocked."</blockquote>

<h2>Looking Forward: Stateful Policy</h2>
<p>The v0.1.0 policy engine is stateless — each evaluation is independent. This is a deliberate simplification that trades expressiveness for reliability. But stateless policy cannot express important governance requirements: rate limiting by agent identity, behavioural pattern detection across multiple requests, or approval workflows that span multiple pipeline cycles.</p>
<p>Stateful policy evaluation, planned for a future release, will extend the policy language with predicates over historical evaluation data. An agent that has triggered escalation three times in an hour can be automatically suspended. A pattern of requests that individually pass policy but collectively constitute suspicious behaviour can be flagged. These capabilities require a policy state store — a component that does not exist in v0.1.0 but whose design is already underway.</p>

<div class="summary-box">
  <h3>// Key Takeaways</h3>
  <ul>
    <li>Policy-as-code enables deterministic, runtime evaluation — policy-as-prose cannot</li>
    <li>Default verdict is deny (fail-closed) — ungoverned action is never the default</li>
    <li>Three-layer approach to plan accuracy: structured format, internal validation, execution comparison</li>
    <li>Policy compilation at startup enables sub-10ms median evaluation latency</li>
    <li>Every denial audit record includes the matching rule for operational transparency</li>
  </ul>
</div>
`
  }
];

// placeholder — articles 6–55 appended below
module.exports = { articles };
