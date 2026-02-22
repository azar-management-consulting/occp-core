"""FastAPI application factory for OCCP API server."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.echo_planner import EchoPlanner
from adapters.mock_executor import MockExecutor
from adapters.basic_validator import BasicValidator
from adapters.log_shipper import LogShipper

from orchestrator.pipeline import Pipeline
from policy_engine.engine import PolicyEngine

from store.database import Database
from store.task_store import TaskStore
from store.audit_store import AuditStore

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

    state = AppState(settings=settings)
    state.db = db
    state.task_store = task_store
    state.audit_store = audit_store

    # Select planner: real LLM if key present, else echo demo
    planner = EchoPlanner()
    if settings.has_anthropic:
        try:
            from adapters.claude_planner import ClaudePlanner
            planner = ClaudePlanner(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
            logger.info("Using ClaudePlanner (model=%s)", settings.anthropic_model)
        except ImportError:
            logger.warning("anthropic not installed – falling back to EchoPlanner")

    state.pipeline = Pipeline(
        planner=planner,
        policy_engine=engine,
        executor=MockExecutor(),
        validator=BasicValidator(),
        shipper=LogShipper(),
    )
    state.policy_engine = engine
    set_state(state)
    logger.info("OCCP API started (env=%s, db=%s)", settings.occp_env, settings.database_url)
    yield

    # Cleanup
    await db.close()
    logger.info("OCCP API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OCCP – OpenCloud Control Plane",
        version="0.3.0",
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
