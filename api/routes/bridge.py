"""Bridge status/health route for monitoring the OCCP <-> OpenClaw connection."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.deps import AppState, get_state

router = APIRouter(tags=["bridge"])


@router.get("/bridge/status")
async def bridge_status(
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Return the current status of the OpenClaw bridge connection.

    Reports WebSocket connection state, circuit breaker status,
    and gateway features for operational monitoring.
    """
    registry = state.adapter_registry
    if registry is None:
        return {
            "bridge": "openclaw",
            "status": "not_configured",
            "detail": "AdapterRegistry not initialized",
        }

    # Check if openclaw executor is registered
    openclaw_types = [
        t for t in registry.registered_types if "openclaw" in t
    ]

    if not openclaw_types:
        return {
            "bridge": "openclaw",
            "status": "not_registered",
            "registered_types": registry.registered_types,
            "detail": "No openclaw agent types registered in AdapterRegistry",
        }

    # Try to get health from the executor
    try:
        executor = registry.get_executor(openclaw_types[0])
        if hasattr(executor, "get_health"):
            health = executor.get_health()
            connected = health.get("connected", False)
            event_bridge = getattr(state, "event_bridge", None)
            event_stats = (
                event_bridge.get_stats() if event_bridge else None
            )
            return {
                "bridge": "openclaw",
                "status": "connected" if connected else "disconnected",
                "registered_types": openclaw_types,
                "health": health,
                "event_bridge": event_stats,
            }
    except Exception as exc:
        return {
            "bridge": "openclaw",
            "status": "error",
            "registered_types": openclaw_types,
            "error": str(exc)[:300],
        }

    return {
        "bridge": "openclaw",
        "status": "registered",
        "registered_types": openclaw_types,
    }


@router.get("/bridge/health")
async def bridge_health(
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Readiness probe for the OpenClaw bridge.

    Returns a simple healthy/unhealthy status suitable for
    load balancer health checks.
    """
    registry = state.adapter_registry
    if registry is None:
        return {"status": "unhealthy", "reason": "no_registry"}

    openclaw_types = [
        t for t in registry.registered_types if "openclaw" in t
    ]
    if not openclaw_types:
        return {"status": "unhealthy", "reason": "not_registered"}

    try:
        executor = registry.get_executor(openclaw_types[0])
        if hasattr(executor, "get_health"):
            health = executor.get_health()
            cb_state = health.get("circuit_breaker", "unknown")
            connected = health.get("connected", False)

            if cb_state == "open":
                return {
                    "status": "unhealthy",
                    "reason": "circuit_breaker_open",
                    "failures": health.get("consecutive_failures", 0),
                }

            return {
                "status": "healthy" if connected else "degraded",
                "connected": connected,
                "circuit_breaker": cb_state,
            }
    except Exception as exc:
        return {"status": "unhealthy", "reason": str(exc)[:200]}

    return {"status": "degraded", "reason": "no_health_method"}


@router.get("/bridge/events")
async def bridge_events(
    limit: int = 50,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    """Return recent events from the OpenClaw Gateway event stream.

    The EventBridge buffers the last 200 events. This endpoint
    returns the most recent N events (newest first).
    """
    event_bridge = getattr(state, "event_bridge", None)
    if event_bridge is None:
        return {
            "status": "not_active",
            "events": [],
            "detail": "EventBridge not initialized (OpenClaw bridge may be disabled)",
        }

    events = event_bridge.get_recent_events(limit=min(limit, 200))
    stats = event_bridge.get_stats()

    return {
        "status": "active",
        "count": len(events),
        "stats": stats,
        "events": events,
    }
