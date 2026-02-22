"""FastAPI application factory for OCCP API server."""

from __future__ import annotations

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

from api.deps import AppState, set_state
from api.ws_manager import ConnectionManager
from api.routes import audit, pipeline, policy, status, tasks, ws


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = PolicyEngine()
    state = AppState()
    state.pipeline = Pipeline(
        planner=EchoPlanner(),
        policy_engine=engine,
        executor=MockExecutor(),
        validator=BasicValidator(),
        shipper=LogShipper(),
    )
    state.policy_engine = engine
    set_state(state)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="OCCP – OpenCloud Control Plane",
        version="0.2.0",
        description="Agent Control Plane with Verified Autonomy Pipeline",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(status.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(pipeline.router, prefix=prefix)
    app.include_router(policy.router, prefix=prefix)
    app.include_router(audit.router, prefix=prefix)
    app.include_router(ws.router, prefix=prefix)

    return app


app = create_app()
