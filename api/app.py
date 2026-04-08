"""FastAPI application factory for OCCP API server."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.logging_config import setup_logging
from api.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)

from adapters.echo_planner import EchoPlanner
from adapters.multi_llm_planner import MultiLLMPlanner
from adapters.mock_executor import MockExecutor
from adapters.sandbox_executor import SandboxBackend, SandboxConfig, SandboxExecutor
from adapters.basic_validator import BasicValidator
from adapters.log_shipper import LogShipper
from adapters.event_bridge import EventBridge

from orchestrator.adapter_registry import AdapterRegistry
from orchestrator.models import AgentConfig
from orchestrator.pipeline import Pipeline
from orchestrator.project_manager import ProjectManager
from policy_engine.engine import PolicyEngine

from store.database import Database
from store.task_store import TaskStore
from store.audit_store import AuditStore
from store.agent_store import AgentStore
from store.user_store import UserStore
from store.onboarding_store import OnboardingStore
from store.token_store import TokenStore

from security.encryption import TokenEncryptor
from security.agent_allowlist import AgentToolGuard
from security.channel_auth import ChannelAuthenticator
from store.conversation_store import ConversationStore
from store.approval_store import ApprovalStore
from adapters.confirmation_gate import ConfirmationGate
from orchestrator.brain_flow import BrainFlowEngine

from api.deps import AppState, set_state
from api.ws_manager import ConnectionManager
from api.routes import agents, audit, auth, brain, dashboard, pipeline, policy, status, tasks, ws
from api.routes import onboarding, mcp, skills, llm, tokens
from api.routes import users, admin, projects, quality
from api.routes import cloudcode, bridge, voice
from api.routes import mcp_bridge as mcp_bridge_route
from api.routes import observability as observability_route
from api.routes import governance as governance_route
from config.settings import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()

    # Structured logging (structlog wrapping stdlib)
    setup_logging(level=settings.log_level, fmt=settings.log_format)

    # Persistent storage
    db = Database(url=settings.database_url)
    await db.connect()
    # Create a long-lived session for app-scoped stores
    session = db.session()
    task_store = TaskStore(session)
    audit_store = AuditStore(session)

    engine = PolicyEngine(audit_store=audit_store)

    # Restore audit chain head from DB for hash continuity
    last_audit = await audit_store.get_last()
    if last_audit:
        engine.set_chain_head(last_audit)

    # ── Audit retention enforcement (EU AI Act Art. 19) ───────────
    if settings.audit_retention_days > 0:
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_retention_days)
        cutoff_iso = cutoff.isoformat()
        pruned = await audit_store.prune_before(cutoff_iso)
        if pruned:
            logger.info(
                "Audit retention: pruned %d entries older than %d days",
                pruned,
                settings.audit_retention_days,
            )

    agent_store = AgentStore(session)
    user_store = UserStore(session)

    # Seed admin user from env vars if no users exist yet (idempotent bootstrap)
    if await user_store.count() == 0:
        await user_store.create(
            username=settings.admin_user,
            password=settings.admin_password,
            role="system_admin",
            display_name="Admin",
        )
        logger.info("Seeded admin user '%s' (system_admin)", settings.admin_user)

    # Sync admin password from env if changed from default
    if await user_store.count() > 0 and settings.admin_password != "changeme":
        admin = await user_store.get_by_username(settings.admin_user)
        if admin:
            await user_store.update_password(settings.admin_user, settings.admin_password)
            logger.info("Admin password synced from environment")

    # Token encryption (AES-256-GCM envelope encryption)
    encryptor = TokenEncryptor(settings.encryption_key)
    token_store = TokenStore(session, encryptor)

    state = AppState(settings=settings)
    state.db = db
    state.task_store = task_store
    state.audit_store = audit_store
    state.agent_store = agent_store
    state.user_store = user_store
    state.onboarding_store = OnboardingStore(session)
    state.token_store = token_store
    state.token_encryptor = encryptor

    # Multi-LLM planner with automatic failover chain
    multi_planner = MultiLLMPlanner()

    # Priority 1: Anthropic Claude
    if settings.has_anthropic:
        try:
            from adapters.claude_planner import ClaudePlanner
            multi_planner.add_provider(
                "anthropic",
                ClaudePlanner(
                    api_key=settings.anthropic_api_key,
                    model=settings.anthropic_model,
                ),
                priority=1,
            )
            logger.info("LLM provider: Anthropic (model=%s)", settings.anthropic_model)
        except ImportError:
            logger.warning("anthropic package not installed – skipping")

    # Priority 2: OpenAI GPT
    if settings.has_openai:
        try:
            from adapters.openai_planner import OpenAIPlanner
            multi_planner.add_provider(
                "openai",
                OpenAIPlanner(api_key=settings.openai_api_key),
                priority=2,
            )
            logger.info("LLM provider: OpenAI (gpt-4o)")
        except ImportError:
            logger.warning("openai package not installed – skipping")

    # Priority 99: Echo fallback (always available)
    multi_planner.add_provider("echo", EchoPlanner(), priority=99)

    state.multi_planner = multi_planner

    # Sandbox executor — auto-detects best isolation backend
    sandbox_cfg = SandboxConfig(
        backend=(
            SandboxBackend(settings.sandbox_backend)
            if settings.sandbox_backend
            else None
        ),
        time_limit_seconds=settings.sandbox_time_limit,
        memory_limit_mb=settings.sandbox_memory_limit,
        enable_network=settings.sandbox_enable_network,
        nsjail_bin=settings.sandbox_nsjail_bin,
        bwrap_bin=settings.sandbox_bwrap_bin,
        nsjail_config=settings.sandbox_nsjail_config,
    )
    sandbox_executor = SandboxExecutor(config=sandbox_cfg)
    logger.info("Sandbox executor: backend=%s", sandbox_executor.backend.value)

    # Adapter registry — per-agent-type routing with defaults
    basic_validator = BasicValidator()
    log_shipper = LogShipper()
    adapter_registry = AdapterRegistry(
        default_planner=multi_planner,
        default_executor=sandbox_executor,
        default_validator=basic_validator,
        default_shipper=log_shipper,
    )
    # Keep mock executor registered for demo agent type
    mock_executor = MockExecutor()
    adapter_registry.register("demo", executor=mock_executor)
    state.adapter_registry = adapter_registry

    # -------------------------------------------------------------------
    # OpenClaw Gateway bridge (optional — only if URL is configured)
    # -------------------------------------------------------------------
    openclaw_executor = None
    if getattr(settings, "has_openclaw", False):
        try:
            from adapters.openclaw_executor import OpenClawConfig, OpenClawExecutor
            from adapters.openclaw_planner import OpenClawPlanner

            oc_config = OpenClawConfig(
                gateway_url=settings.openclaw_gateway_url,
                gateway_token=settings.openclaw_gateway_token,
                hmac_secret=settings.openclaw_hmac_secret,
                connect_timeout=settings.openclaw_connect_timeout,
                execute_timeout=settings.openclaw_execute_timeout,
            )
            openclaw_executor = OpenClawExecutor(config=oc_config)
            openclaw_planner = OpenClawPlanner(openclaw_executor)

            adapter_registry.register(
                "openclaw", planner=openclaw_planner, executor=openclaw_executor,
            )
            for _at in ("general", "code-reviewer", "main"):
                adapter_registry.register(_at, executor=openclaw_executor)
            adapter_registry.register("remote-agent", executor=openclaw_executor)
            multi_planner.add_provider("openclaw", openclaw_planner, priority=5)

            await openclaw_executor.startup()
            event_bridge = EventBridge(executor=openclaw_executor)
            event_bridge.start()
            state.event_bridge = event_bridge

            logger.info("OpenClaw bridge: active (url=%s)", settings.openclaw_gateway_url)
        except ImportError:
            logger.warning("websockets not installed — OpenClaw bridge disabled")
        except Exception as exc:
            logger.error("OpenClaw bridge init failed: %s", exc)

    agent_tool_guard = AgentToolGuard()
    state.agent_tool_guard = agent_tool_guard
    state.pipeline = Pipeline(
        planner=multi_planner,
        policy_engine=engine,
        executor=sandbox_executor,
        validator=basic_validator,
        shipper=log_shipper,
        adapter_registry=adapter_registry,
        agent_tool_guard=agent_tool_guard,
    )
    # Connect pipeline to EventBridge for Brain routing
    if getattr(state, "event_bridge", None) is not None:
        state.event_bridge.set_pipeline(pipeline=state.pipeline, task_store=state.task_store)
    state.policy_engine = engine

    # Seed default agent configs (idempotent upsert)
    _DEFAULT_AGENTS = [
        AgentConfig(
            agent_type="general",
            display_name="General Assistant",
            capabilities=["planning", "execution", "validation"],
        ),
        AgentConfig(
            agent_type="demo",
            display_name="Demo Agent",
            capabilities=["echo", "testing"],
        ),
        AgentConfig(
            agent_type="code-reviewer",
            display_name="Code Reviewer",
            capabilities=["code-analysis", "pr-review", "security-scan"],
            max_concurrent=3,
            timeout_seconds=600,
        ),
        AgentConfig(
            agent_type="onboarding-wizard",
            display_name="Onboarding Wizard",
            capabilities=["onboarding", "setup", "wizard"],
        ),
        AgentConfig(
            agent_type="mcp-installer",
            display_name="MCP Installer",
            capabilities=["mcp-install", "mcp-config", "connector-setup"],
        ),
        AgentConfig(
            agent_type="llm-setup",
            display_name="LLM Setup",
            capabilities=["llm-config", "token-validation", "provider-health"],
        ),
        AgentConfig(
            agent_type="skills-manager",
            display_name="Skills Manager",
            capabilities=["skills-inventory", "enable-disable", "token-budget"],
        ),
        AgentConfig(
            agent_type="session-policy",
            display_name="Session Policy",
            capabilities=["session-scope", "secure-mode", "tool-policy"],
        ),
        AgentConfig(
            agent_type="ux-copy",
            display_name="UX Copy Agent",
            capabilities=["ui-text", "i18n", "crt-style"],
        ),
        AgentConfig(
            agent_type="openclaw",
            display_name="OpenClaw Remote Agent",
            capabilities=["remote-execution", "agent-dispatch", "llm-routing"],
            max_concurrent=5, timeout_seconds=120,
        ),
        AgentConfig(
            agent_type="remote-agent",
            display_name="Remote Agent (OpenClaw)",
            capabilities=["remote-execution"],
            max_concurrent=5, timeout_seconds=120,
        ),
    ]
    for agent_cfg in _DEFAULT_AGENTS:
        await agent_store.upsert(agent_cfg)
    logger.info("Seeded %d default agent configs", len(_DEFAULT_AGENTS))

    # Project manager — 10-project concurrent routing
    project_manager = ProjectManager(max_projects=10)
    await project_manager.seed_defaults()
    state.project_manager = project_manager
    logger.info("ProjectManager initialized with %d default projects", project_manager.project_count)

    # ── Persistence stores ──────────────────────────────────────────
    conversation_store = ConversationStore(db.session_factory)
    state.conversation_store = conversation_store

    approval_store = ApprovalStore(db.session_factory)
    state.approval_store = approval_store

    # ── ChannelAuth ───────────────────────────────────────────────
    import os
    owner_tg_id = int(os.getenv("OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID", "0") or "0")
    if settings.has_voice and owner_tg_id == 0:
        logger.warning(
            "OCCP_VOICE_TELEGRAM_OWNER_CHAT_ID not set — Telegram strict auth "
            "will reject all messages. Set it to Henry's chat_id."
        )
    channel_auth = ChannelAuthenticator(
        jwt_secret=settings.jwt_secret,
        webhook_secret=getattr(settings, "webhook_secret", ""),
        owner_telegram_id=owner_tg_id,
    )
    state.channel_auth = channel_auth

    # ── ConfirmationGate with ApprovalStore ───────────────────────
    confirmation_gate = ConfirmationGate(approval_store=approval_store)
    await confirmation_gate.load_pending_from_db()
    state.confirmation_gate = confirmation_gate

    # ── BrainFlowEngine with ConversationStore ────────────────────
    from orchestrator.task_router import TaskRouter
    from orchestrator.quality_gate import QualityGate
    task_router = TaskRouter()
    quality_gate = QualityGate()
    brain_flow = BrainFlowEngine(
        task_router=task_router,
        quality_gate=quality_gate,
        project_manager=project_manager,
        confirmation_gate=confirmation_gate,
        conversation_store=conversation_store,
        approval_store=approval_store,
    )
    # Also set state.brain_flow so /brain/message endpoint can find it
    state.brain_flow = brain_flow
    loaded = await brain_flow.load_active_conversations()
    state.brain_flow = brain_flow
    logger.info("BrainFlowEngine initialized (%d conversations loaded)", loaded)

    # -------------------------------------------------------------------
    # Voice command pipeline (optional — only if enabled + token set)
    # -------------------------------------------------------------------
    voice_bot = None
    if getattr(settings, "has_voice", False):
        try:
            from adapters.telegram_voice_bot import TelegramVoiceBot
            from adapters.whisper_client import WhisperClient
            from adapters.intent_router import IntentRouter
            from adapters.voice_handler import VoiceCommandHandler

            whisper = WhisperClient(
                timeout=60.0,
                api_key=settings.openai_api_key,
                language=getattr(settings, "voice_default_language", "hu"),
            )
            intent_router = IntentRouter(
                anthropic_api_key=getattr(settings, "anthropic_api_key", ""),
                openai_api_key=settings.openai_api_key,
                anthropic_model=getattr(settings, "anthropic_model", ""),
            )
            voice_handler = VoiceCommandHandler(
                whisper=whisper,
                intent_router=intent_router,
                pipeline=state.pipeline,
                task_store=task_store,
                audit_store=audit_store,
                confirmation_gate=confirmation_gate,
                brain_flow=brain_flow,
                channel_auth=channel_auth,
            )
            voice_bot = TelegramVoiceBot(
                token=settings.voice_telegram_bot_token,
                handler=voice_handler,
                owner_chat_id=int(getattr(settings, "voice_telegram_owner_chat_id", 0) or 0),
            )
            voice_handler.set_bot(voice_bot)
            await voice_bot.start()

            state.voice_bot = voice_bot
            state.voice_handler = voice_handler
            logger.info("Voice pipeline: started (lang=%s)", getattr(settings, "voice_default_language", "hu"))
        except Exception as exc:
            logger.error("Voice pipeline init failed: %s", exc)

    set_state(state)
    logger.info("OCCP API started (env=%s, db=%s)", settings.occp_env, settings.database_url)
    yield

    # Cleanup
    if voice_bot is not None:
        await voice_bot.stop()
        logger.info("Voice bot: shut down")
    if openclaw_executor is not None:
        await openclaw_executor.close()
        logger.info("OpenClaw bridge: shut down")
    await db.close()
    logger.info("OCCP API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OCCP – OpenCloud Control Plane",
        version="0.9.0",
        description="Agent Control Plane with Verified Autonomy Pipeline",
        lifespan=lifespan,
    )

    # Middleware stack (applied in reverse order — last added runs first)
    settings = Settings()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        include_hsts=settings.is_production,
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Rate limiting (auth endpoints)
    rate_paths = [
        p.strip()
        for p in settings.rate_limit_paths.split(",")
        if p.strip()
    ]
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_window=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window,
        rate_limit_paths=rate_paths or None,
    )

    prefix = "/api/v1"
    app.include_router(status.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(pipeline.router, prefix=prefix)
    app.include_router(policy.router, prefix=prefix)
    app.include_router(brain.router, prefix=prefix)
    app.include_router(agents.router, prefix=prefix)
    app.include_router(audit.router, prefix=prefix)
    app.include_router(ws.router, prefix=prefix)
    app.include_router(onboarding.router, prefix=prefix)
    app.include_router(mcp.router, prefix=prefix)
    app.include_router(skills.router, prefix=prefix)
    app.include_router(llm.router, prefix=prefix)
    app.include_router(tokens.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(quality.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    app.include_router(projects.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)
    app.include_router(cloudcode.router, prefix=prefix)
    app.include_router(bridge.router, prefix=prefix)
    app.include_router(voice.router, prefix=prefix)
    app.include_router(mcp_bridge_route.router, prefix=prefix)
    app.include_router(observability_route.router, prefix=prefix)
    app.include_router(governance_route.router, prefix=prefix)

    return app


app = create_app()
