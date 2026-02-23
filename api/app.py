"""FastAPI application factory for OCCP API server."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.echo_planner import EchoPlanner
from adapters.multi_llm_planner import MultiLLMPlanner
from adapters.mock_executor import MockExecutor
from adapters.basic_validator import BasicValidator
from adapters.log_shipper import LogShipper

from orchestrator.adapter_registry import AdapterRegistry
from orchestrator.models import AgentConfig
from orchestrator.pipeline import Pipeline
from policy_engine.engine import PolicyEngine

from store.database import Database
from store.task_store import TaskStore
from store.audit_store import AuditStore
from store.agent_store import AgentStore

from api.deps import AppState, set_state
from api.ws_manager import ConnectionManager
from api.routes import agents, audit, auth, pipeline, policy, status, tasks, ws
from config.settings import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()

    # Persistent storage
    db = Database(url=settings.database_url)
    await db.connect()
    task_store = TaskStore(db)
    audit_store = AuditStore(db)

    engine = PolicyEngine(audit_store=audit_store)

    # Restore audit chain head from DB for hash continuity
    last_audit = await audit_store.get_last()
    if last_audit:
        engine.set_chain_head(last_audit)

    agent_store = AgentStore(db)

    state = AppState(settings=settings)
    state.db = db
    state.task_store = task_store
    state.audit_store = audit_store
    state.agent_store = agent_store

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

    # Adapter registry — per-agent-type routing with defaults
    mock_executor = MockExecutor()
    basic_validator = BasicValidator()
    log_shipper = LogShipper()
    adapter_registry = AdapterRegistry(
        default_planner=multi_planner,
        default_executor=mock_executor,
        default_validator=basic_validator,
        default_shipper=log_shipper,
    )
    state.adapter_registry = adapter_registry

    state.pipeline = Pipeline(
        planner=multi_planner,
        policy_engine=engine,
        executor=mock_executor,
        validator=basic_validator,
        shipper=log_shipper,
        adapter_registry=adapter_registry,
    )
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
    ]
    for agent_cfg in _DEFAULT_AGENTS:
        await agent_store.upsert(agent_cfg)
    logger.info("Seeded %d default agent configs", len(_DEFAULT_AGENTS))

    set_state(state)
    logger.info("OCCP API started (env=%s, db=%s)", settings.occp_env, settings.database_url)
    yield

    # Cleanup
    await db.close()
    logger.info("OCCP API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OCCP – OpenCloud Control Plane",
        version="0.6.0",
        description="Agent Control Plane with Verified Autonomy Pipeline",
        lifespan=lifespan,
    )

    # CORS – merged from settings at startup; we read env here for middleware
    settings = Settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(status.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(pipeline.router, prefix=prefix)
    app.include_router(policy.router, prefix=prefix)
    app.include_router(agents.router, prefix=prefix)
    app.include_router(audit.router, prefix=prefix)
    app.include_router(ws.router, prefix=prefix)

    return app


app = create_app()
