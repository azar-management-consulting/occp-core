"""LLM provider health and configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.rbac import PermissionChecker
from api.deps import AppState, get_state
from api.models import LLMHealthResponse, LLMProviderStatus

router = APIRouter(tags=["llm"])


@router.get(
    "/llm/health",
    response_model=LLMHealthResponse,
    dependencies=[Depends(PermissionChecker("status", "read"))],
)
async def llm_health(
    state: AppState = Depends(get_state),
) -> LLMHealthResponse:
    """Check health of configured LLM providers."""
    settings = state.settings
    providers: list[LLMProviderStatus] = []

    # Anthropic
    providers.append(LLMProviderStatus(
        provider="anthropic",
        configured=settings.has_anthropic,
        model=settings.anthropic_model if settings.has_anthropic else "",
        status="ok" if settings.has_anthropic else "not_configured",
    ))

    # OpenAI
    providers.append(LLMProviderStatus(
        provider="openai",
        configured=settings.has_openai,
        model="gpt-4o" if settings.has_openai else "",
        status="ok" if settings.has_openai else "not_configured",
    ))

    # Echo fallback (always available)
    providers.append(LLMProviderStatus(
        provider="echo",
        configured=True,
        model="echo-v1",
        status="ok",
    ))

    # Active provider from multi_planner
    active_provider = "echo"
    if state.multi_planner:
        active_provider = getattr(state.multi_planner, "active_provider", "echo")
        # Try to get from providers list
        if hasattr(state.multi_planner, "_providers"):
            for name, _p, _prio in state.multi_planner._providers:
                active_provider = name
                break

    any_configured = settings.has_anthropic or settings.has_openai

    return LLMHealthResponse(
        status="ok" if any_configured else "fallback",
        active_provider=active_provider,
        providers=providers,
        token_present=any_configured,
    )
