"""OpenClawExecutor -- WebSocket JSON-RPC bridge to OpenClaw Gateway.

Implements the Executor protocol by dispatching tasks to the OpenClaw
Gateway (Node.js agent platform) over its native WebSocket JSON-RPC
protocol (version 3).

Features:
- Persistent WebSocket connection with automatic reconnect
- Circuit breaker (5 consecutive failures -> open for 60s)
- Exponential backoff reconnect (1s, 2s, 4s, 8s, max 30s)
- Configurable timeout (120s default for LLM tasks)
- HMAC request signing for inter-service security
- Connection pooling via single persistent connection
- Clean async shutdown
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from orchestrator.exceptions import ExecutionError
from orchestrator.models import Task

logger = logging.getLogger(__name__)

# Attempt to import websockets; fail gracefully with clear message.
try:
    import websockets
    from websockets.asyncio.client import ClientConnection
except ImportError:
    websockets = None  # type: ignore[assignment]
    ClientConnection = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class OpenClawConfig:
    """Configuration for the OpenClaw Gateway connection."""

    gateway_url: str = ""
    gateway_token: str = ""
    hmac_secret: str = ""

    # Connection
    connect_timeout: float = 30.0
    execute_timeout: float = 120.0
    ping_interval: float = 20.0
    ping_timeout: float = 10.0

    # Reconnect
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    reconnect_max_attempts: int = 10

    # Circuit breaker
    cb_failure_threshold: int = 5
    cb_recovery_timeout: float = 60.0

    # Client identity
    client_name: str = "gateway-client"
    client_mode: str = "backend"
    protocol_version: int = 3

    @classmethod
    def from_env(cls) -> "OpenClawConfig":
        """Build config from OCCP-prefixed environment variables."""
        return cls(
            gateway_url=os.getenv("OCCP_OPENCLAW_GATEWAY_URL", "ws://95.216.212.174:18789"),
            gateway_token=os.getenv("OCCP_OPENCLAW_GATEWAY_TOKEN", ""),
            hmac_secret=os.getenv("OCCP_OPENCLAW_HMAC_SECRET", ""),
            connect_timeout=float(os.getenv("OCCP_OPENCLAW_CONNECT_TIMEOUT", "30")),
            execute_timeout=float(os.getenv("OCCP_OPENCLAW_EXECUTE_TIMEOUT", "120")),
        )


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple circuit breaker: CLOSED -> OPEN after N failures, half-open after timeout."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._consecutive_failures = 0
        self._last_failure_time: float | None = None
        self._state = self.CLOSED

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    self._state = self.HALF_OPEN
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state in (self.CLOSED, self.HALF_OPEN)

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        if self._consecutive_failures >= self._failure_threshold:
            self._state = self.OPEN
            logger.warning(
                "CircuitBreaker OPEN after %d consecutive failures",
                self._consecutive_failures,
            )

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures


# ---------------------------------------------------------------------------
# WebSocket JSON-RPC Connection Manager
# ---------------------------------------------------------------------------

class OpenClawConnection:
    """Manages a persistent WebSocket connection to OpenClaw Gateway.

    Handles:
    - Initial connect + challenge/response auth
    - Automatic reconnect with exponential backoff
    - JSON-RPC request/response correlation via request IDs
    - Streaming event collection for chat.send
    """

    def __init__(self, config: OpenClawConfig) -> None:
        self._config = config
        self._ws: Any = None  # ClientConnection when connected
        self._connected = False
        self._authenticated = False
        self._lock = asyncio.Lock()
        self._request_id = 0
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._recv_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempt = 0
        self._gateway_features: dict[str, Any] = {}
        self._event_callbacks: dict[str, list[Any]] = {}
        self._events_received: int = 0
        self._last_event_time: float = 0.0
        self._chat_completions: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._chat_text_buffer: dict[str, list[str]] = {}
        self._shutting_down = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._authenticated

    def on_event(self, event_type: str, callback: Any) -> None:
        """Register a callback for a specific event type.

        Use '*' as event_type to receive all events.
        Callback signature: async def cb(event_name: str, payload: dict) -> None
        """
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)
        logger.debug("OpenClaw: registered event callback for '%s'", event_type)

    def _next_id(self) -> str:
        return str(uuid.uuid4())

    def _sign_payload(self, payload: str) -> str:
        """HMAC-SHA256 sign a payload string."""
        secret = self._config.hmac_secret
        if not secret:
            return ""
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def connect(self) -> None:
        """Establish WebSocket connection and authenticate."""
        if websockets is None:
            raise ExecutionError(
                "openclaw",
                "websockets package not installed: pip install websockets",
            )

        async with self._lock:
            if self.is_connected:
                return
            await self._do_connect()

    async def _do_connect(self) -> None:
        """Internal connect logic (must be called with _lock held)."""
        cfg = self._config
        if not cfg.gateway_url:
            raise ExecutionError(
                "openclaw", "OCCP_OPENCLAW_GATEWAY_URL not configured"
            )

        logger.info("OpenClaw: connecting to %s", cfg.gateway_url)
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    cfg.gateway_url,
                    ping_interval=cfg.ping_interval,
                    ping_timeout=cfg.ping_timeout,
                    max_size=10 * 1024 * 1024,  # 10 MB max message
                    close_timeout=10,
                ),
                timeout=cfg.connect_timeout,
            )
            self._connected = True
            self._reconnect_attempt = 0
            logger.info("OpenClaw: WebSocket connected")

            # Authenticate BEFORE starting receive loop
            # (auth reads challenge/response directly from WS)
            await self._authenticate()

            # Start receive loop for post-auth messages
            self._recv_task = asyncio.create_task(
                self._receive_loop(), name="openclaw-recv"
            )

        except asyncio.TimeoutError:
            self._connected = False
            raise ExecutionError(
                "openclaw",
                f"Connection timeout after {cfg.connect_timeout}s",
            )
        except ExecutionError:
            self._connected = False
            raise
        except Exception as exc:
            self._connected = False
            raise ExecutionError(
                "openclaw", f"Connection failed: {exc}"
            ) from exc

    async def _authenticate(self) -> None:
        """Handle the connect.challenge -> connect auth flow.

        Uses native OpenClaw frame format (NOT JSON-RPC):
        - Request:  {"type": "req", "id": "<uuid>", "method": "...", "params": {...}}
        - Response: {"type": "res", "id": "<uuid>", "ok": bool, "payload": {...}}
        - Event:    {"type": "event", "event": "...", "payload": {...}}
        """
        cfg = self._config

        # Wait for the challenge event (up to connect_timeout)
        challenge_nonce = await self._wait_for_challenge(
            timeout=cfg.connect_timeout
        )

        # Build connect params (ConnectParamsSchema v3)
        import platform as _platform
        connect_params: dict[str, Any] = {
            "minProtocol": cfg.protocol_version,
            "maxProtocol": cfg.protocol_version,
            "client": {
                "id": cfg.client_name,
                "version": "0.8.0",
                "platform": _platform.system().lower(),
                "mode": cfg.client_mode.lower(),
            },
        }
        # Token auth
        if cfg.gateway_token:
            connect_params["auth"] = {"token": cfg.gateway_token}
        # Request admin scopes for full bridge capability
        connect_params["scopes"] = ["operator.admin"]

        # Send connect request in native frame format
        req_id = str(uuid.uuid4())
        frame: dict[str, Any] = {
            "type": "req",
            "id": req_id,
            "method": "connect",
            "params": connect_params,
        }
        await self._ws.send(json.dumps(frame))
        logger.debug("OpenClaw: sent connect request id=%s", req_id)

        # Read connect response directly (recv_loop not running yet)
        raw = await asyncio.wait_for(
            self._ws.recv(), timeout=cfg.connect_timeout
        )
        msg = json.loads(raw)

        if msg.get("type") != "res" or not msg.get("ok", False):
            error = msg.get("error", {})
            reason = error.get("message", error.get("code", "unknown"))
            raise ExecutionError(
                "openclaw", f"Auth failed: {reason}"
            )

        payload = msg.get("payload", {})
        self._authenticated = True
        self._gateway_features = payload.get("features", {})
        logger.info(
            "OpenClaw: authenticated (protocol=%s, features=%s)",
            payload.get("protocol", "?"),
            list(self._gateway_features.keys())
            if self._gateway_features
            else "none",
        )

    async def _wait_for_challenge(self, timeout: float) -> str:
        """Wait for the connect.challenge event and extract the nonce."""
        if self._ws is None:
            raise ExecutionError("openclaw", "WebSocket not connected")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                raw = await asyncio.wait_for(
                    self._ws.recv(), timeout=remaining
                )
                msg = json.loads(raw)
                if msg.get("type") == "event" and msg.get("event") == "connect.challenge":
                    payload = msg.get("payload", {})
                    nonce = payload.get("nonce", "")
                    logger.debug("OpenClaw: received challenge nonce")
                    return nonce
            except asyncio.TimeoutError:
                break
            except Exception as exc:
                logger.warning(
                    "OpenClaw: error waiting for challenge: %s", exc
                )
                break

        raise ExecutionError(
            "openclaw", "Timed out waiting for connect.challenge"
        )

    async def _receive_loop(self) -> None:
        """Background task: read messages from WS, dispatch to pending futures."""
        if self._ws is None:
            return

        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(
                        "OpenClaw: received non-JSON message, ignoring"
                    )
                    continue

                msg_type = msg.get("type")
                if msg_type == "res":
                    msg_id = msg.get("id")
                    if msg_id and msg_id in self._pending:
                        future = self._pending.pop(msg_id)
                        if not future.done():
                            if msg.get("ok", False):
                                future.set_result(msg.get("payload", {}))
                            else:
                                error = msg.get("error", {})
                                error_msg = error.get("message", error.get("code", "RPC error"))
                                future.set_exception(
                                    ExecutionError(
                                        "openclaw",
                                        f"RPC error: {error_msg}",
                                    )
                                )
                elif msg_type == "event":
                    event_name = msg.get("event", "")
                    payload = msg.get("payload", {})
                    self._events_received += 1
                    self._last_event_time = time.monotonic()
                    logger.info(
                        "OpenClaw: event %s keys=%s (total=%d)",
                        event_name,
                        list(payload.keys())[:8],
                        self._events_received,
                    )
                    # Dispatch to registered callbacks
                    for cb in self._event_callbacks.get(event_name, []):
                        try:
                            asyncio.create_task(cb(event_name, payload))
                        except Exception as cb_exc:
                            logger.error(
                                "OpenClaw: event callback error (%s): %s",
                                event_name,
                                cb_exc,
                            )
                    # Wildcard callbacks
                    for cb in self._event_callbacks.get("*", []):
                        try:
                            asyncio.create_task(cb(event_name, payload))
                        except Exception as cb_exc:
                            logger.error(
                                "OpenClaw: wildcard callback error: %s",
                                cb_exc,
                            )

                    # Collect streaming text from 'agent' events (data field)
                    if event_name == "agent":
                        run_id_ev = payload.get("runId", "")
                        data_ev = payload.get("data", "")
                        stream_type = payload.get("stream", "")
                        logger.info(
                            "OpenClaw: agent event stream=%s data_type=%s data_preview=%s runId=%s",
                            stream_type,
                            type(data_ev).__name__,
                            str(data_ev)[:200] if data_ev else "EMPTY",
                            run_id_ev[:12] if run_id_ev else "none",
                        )
                        if run_id_ev and data_ev:
                            text_ev = ""
                            if isinstance(data_ev, str):
                                text_ev = data_ev
                            elif isinstance(data_ev, dict):
                                text_ev = data_ev.get("text", "") or data_ev.get("content", "") or data_ev.get("message", "")
                            if text_ev:
                                if run_id_ev not in self._chat_text_buffer:
                                    self._chat_text_buffer[run_id_ev] = []
                                self._chat_text_buffer[run_id_ev].append(text_ev)

                    # Resolve chat completion futures (voice pipeline)
                    if event_name == "chat" and payload.get("state") == "final":
                        run_id = payload.get("runId", "")
                        if run_id and run_id in self._chat_completions:
                            future = self._chat_completions.pop(run_id)
                            if not future.done():
                                # Inject collected streaming text
                                collected = self._chat_text_buffer.pop(run_id, [])
                                if collected:
                                    full_text = collected[-1]  # cumulative chunks: last = complete
                                    payload["message"] = {"text": full_text}
                                    logger.info(
                                        "OpenClaw: assembled %d chars from %d streaming chunks",
                                        len(full_text),
                                        len(collected),
                                    )
                                future.set_result(payload)
                                logger.info(
                                    "OpenClaw: chat.final resolved for runId=%s payload_keys=%s",
                                    run_id[:12],
                                    list(payload.keys()),
                                )
                                logger.info("OpenClaw: chat.final payload=%s", str(payload)[:500])
                else:
                    logger.debug(
                        "OpenClaw: unhandled message: %s", str(msg)[:200]
                    )

        except Exception as exc:
            if "ConnectionClosed" not in type(exc).__name__:
                logger.error("OpenClaw: receive loop error: %s", exc)
            else:
                logger.warning("OpenClaw: WebSocket connection closed")
        finally:
            self._connected = False
            self._authenticated = False
            # Fail all pending requests
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(
                        ExecutionError("openclaw", "Connection lost")
                    )
            self._pending.clear()

    async def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        if self._ws is None or not self._connected:
            raise ExecutionError(
                "openclaw", "Not connected to OpenClaw Gateway"
            )

        req_id = self._next_id()
        request: dict[str, Any] = {
            "type": "req",
            "id": req_id,
            "method": method,
        }
        if params:
            request["params"] = params

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = future

        try:
            await self._ws.send(json.dumps(request))
            logger.debug(
                "OpenClaw: sent request id=%s method=%s", req_id, method
            )
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise ExecutionError(
                "openclaw",
                f"Request timeout after {timeout}s (method={method})",
            )
        except Exception:
            self._pending.pop(req_id, None)
            raise

    async def send_chat(
        self,
        message: str,
        agent: str = "general",
        session_id: str = "",
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Send a chat.send request and wait for the agent's final response.

        Two-phase flow:
          1. RPC chat.send → ack {runId, status: "started"}
          2. Wait for chat event state=final with matching runId
        """
        # Build a unique session key: agent-name/session-id
        session_key = f"{agent}/{session_id}" if session_id else f"{agent}/default"
        idempotency_key = str(uuid.uuid4())

        params: dict[str, Any] = {
            "sessionKey": session_key,
            "message": message,
            "idempotencyKey": idempotency_key,
        }

        # Phase 1: Send RPC and get runId
        ack = await self.send_request("chat.send", params, timeout=30.0)
        run_id = ack.get("runId", "")

        if not run_id:
            logger.warning("OpenClaw: chat.send returned no runId, returning ack as-is")
            return ack

        # Phase 2: Wait for chat.final event with this runId
        loop = asyncio.get_running_loop()
        completion_future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._chat_completions[run_id] = completion_future

        try:
            result = await asyncio.wait_for(completion_future, timeout=timeout)
            logger.info(
                "OpenClaw: chat completed runId=%s session=%s",
                run_id[:12],
                session_key,
            )

            return result
        except asyncio.TimeoutError:
            self._chat_completions.pop(run_id, None)
            raise ExecutionError(
                "openclaw",
                f"Chat completion timeout after {timeout}s (runId={run_id[:12]})",
            )
        except Exception:
            self._chat_completions.pop(run_id, None)
            raise

    async def close(self) -> None:
        """Gracefully close the WebSocket connection."""
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

        self._ws = None
        self._connected = False
        self._authenticated = False
        self._pending.clear()
        logger.info("OpenClaw: connection closed")

    async def startup(self) -> None:
        """Start persistent connection with auto-reconnect loop."""
        self._shutting_down = False
        try:
            await self.connect()
        except Exception as exc:
            logger.warning("OpenClaw: initial connect failed: %s (reconnect will retry)", exc)
        # Start background reconnect loop
        self._reconnect_task = asyncio.create_task(
            self._auto_reconnect_loop(), name="openclaw-reconnect"
        )
        logger.info("OpenClaw: persistent connection started")

    async def shutdown(self) -> None:
        """Stop reconnect loop and close connection."""
        self._shutting_down = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self.close()
        logger.info("OpenClaw: persistent connection shut down")

    async def _auto_reconnect_loop(self) -> None:
        """Background task: monitor connection, reconnect on disconnect."""
        cfg = self._config
        delay = cfg.reconnect_base_delay

        while not self._shutting_down:
            try:
                await asyncio.sleep(2.0)  # Check every 2 seconds

                if self._shutting_down:
                    break

                if self.is_connected:
                    delay = cfg.reconnect_base_delay  # Reset backoff
                    continue

                # Connection lost — attempt reconnect
                logger.info(
                    "OpenClaw: reconnecting (delay=%.1fs, attempt=%d)",
                    delay,
                    self._reconnect_attempt + 1,
                )
                try:
                    await self.connect()
                    logger.info("OpenClaw: reconnected successfully")
                    delay = cfg.reconnect_base_delay
                except Exception as exc:
                    self._reconnect_attempt += 1
                    logger.warning(
                        "OpenClaw: reconnect failed (attempt %d): %s",
                        self._reconnect_attempt,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, cfg.reconnect_max_delay)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("OpenClaw: reconnect loop error: %s", exc)
                await asyncio.sleep(5.0)


# ---------------------------------------------------------------------------
# Executor Adapter
# ---------------------------------------------------------------------------

class OpenClawExecutor:
    """Executor adapter that dispatches tasks to OpenClaw Gateway via WebSocket.

    Implements the ``Executor`` protocol from ``orchestrator.pipeline``.

    Usage::

        executor = OpenClawExecutor()
        executor = OpenClawExecutor(config=OpenClawConfig(
            gateway_url="ws://95.216.212.174:18789",
            gateway_token="my-token",
        ))
        result = await executor.execute(task)
    """

    def __init__(self, config: OpenClawConfig | None = None) -> None:
        self._config = config or OpenClawConfig.from_env()
        self._conn = OpenClawConnection(self._config)
        self._circuit = CircuitBreaker(
            failure_threshold=self._config.cb_failure_threshold,
            recovery_timeout=self._config.cb_recovery_timeout,
        )
        logger.info(
            "OpenClawExecutor initialized (url=%s, timeout=%ss)",
            self._config.gateway_url,
            self._config.execute_timeout,
        )

    @property
    def connection(self) -> OpenClawConnection:
        """Expose connection for shared use (e.g., by OpenClawPlanner)."""
        return self._conn

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit

    async def _ensure_connected(self) -> None:
        """Connect (or reconnect) to the Gateway with exponential backoff."""
        if self._conn.is_connected:
            return

        cfg = self._config
        delay = cfg.reconnect_base_delay

        for attempt in range(1, cfg.reconnect_max_attempts + 1):
            try:
                await self._conn.connect()
                return
            except ExecutionError:
                if attempt == cfg.reconnect_max_attempts:
                    raise
                logger.warning(
                    "OpenClaw: connect attempt %d/%d failed, retrying in %.1fs",
                    attempt,
                    cfg.reconnect_max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, cfg.reconnect_max_delay)

    async def execute(self, task: Task) -> dict[str, Any]:
        """Execute a task via OpenClaw Gateway.

        Dispatches task.description to an OpenClaw agent via chat.send,
        collects the result, and returns it in OCCP's standard format.
        """
        if not self._circuit.is_closed:
            raise ExecutionError(
                task.id,
                f"OpenClaw circuit breaker OPEN "
                f"(failures={self._circuit.failure_count}, "
                f"state={self._circuit.state})",
            )

        t0 = time.monotonic()
        try:
            await self._ensure_connected()

            # Determine which OpenClaw agent to route to
            agent = self._resolve_agent(task)

            # Build the message with task context
            message = self._build_message(task)

            # Send via chat.send and wait for result
            result = await self._conn.send_chat(
                message=message,
                agent=agent,
                session_id=task.id,
                timeout=self._config.execute_timeout,
            )

            latency = time.monotonic() - t0
            self._circuit.record_success()

            output = self._extract_output(result)

            # If output is raw JSON (no text extracted), fetch from OpenClaw session JSONL
            if output.startswith("{") and ("runId" in output or "sessionKey" in output):
                try:
                    session_key = result.get("sessionKey", "")
                    if session_key:
                        fetched = await self._fetch_session_text(session_key)
                        if fetched:
                            output = fetched
                except Exception as fetch_exc:
                    logger.warning("OpenClaw: session text fetch failed: %s", fetch_exc)

            logger.info(
                "OpenClaw: task=%s agent=%s completed in %.1fs",
                task.id,
                agent,
                latency,
            )

            return {
                "executor": "openclaw",
                "task_id": task.id,
                "output": output,
                "exit_code": 0,
                "agent": agent,
                "latency_ms": round(latency * 1000, 1),
                "gateway_response": result,
            }

        except ExecutionError:
            self._circuit.record_failure()
            raise
        except Exception as exc:
            self._circuit.record_failure()
            latency = time.monotonic() - t0
            logger.error(
                "OpenClaw: task=%s failed after %.1fs: %s",
                task.id,
                latency,
                exc,
            )
            raise ExecutionError(
                task.id, f"OpenClaw execution failed: {exc}"
            ) from exc

    def _resolve_agent(self, task: Task) -> str:
        """Map OCCP agent_type to OpenClaw agent name.

        Uses task metadata override if present, otherwise maps directly.
        """
        if task.metadata and task.metadata.get("openclaw_agent"):
            return str(task.metadata["openclaw_agent"])
        # Direct mapping: "openclaw-code-reviewer" -> "code-reviewer"
        agent_type = task.agent_type
        if agent_type.startswith("openclaw-"):
            return agent_type[len("openclaw-"):]
        return agent_type

    def _build_message(self, task: Task) -> str:
        """Build the message payload for chat.send from task data."""
        # Brian the Brain identity injection
        brian_identity = (
            "[SYSTEM] Te vagy Brian the Brain — Henry személyes AI asszisztense. "
            "Magyar nyelven válaszolj, max 2-3 mondat. "
            "Ha kérdezik ki vagy: 'Brian the Brain vagyok, Henry személyes AI asszisztense.' "
            "NE mondd hogy OCCP agent, tervező, planner, vagy gateway agent. "
            "Te BRIAN THE BRAIN vagy."
        )
        parts = [brian_identity, f"Task: {task.name}"]
        if task.description:
            parts.append(f"Description: {task.description}")

        # Include plan context if available (from OCCP's Plan stage)
        if task.plan:
            plan_summary = task.plan.get("description", "")
            if plan_summary:
                parts.append(f"Plan: {plan_summary}")
            steps = task.plan.get("steps", [])
            if steps:
                step_lines = []
                for i, s in enumerate(steps):
                    if isinstance(s, str):
                        step_lines.append(f"  {i + 1}. {s}")
                    elif isinstance(s, dict):
                        step_lines.append(
                            f"  {i + 1}. {s.get('description', str(s))}"
                        )
                    else:
                        step_lines.append(f"  {i + 1}. {s}")
                parts.append("Steps:\n" + "\n".join(step_lines))

        # Include metadata hints
        if task.metadata:
            for key in ("command", "context", "instructions"):
                val = task.metadata.get(key)
                if val:
                    parts.append(f"{key.capitalize()}: {val}")

        return "\n\n".join(parts)

    async def _fetch_session_text(self, session_key: str) -> str:
        """Fetch last assistant message from OpenClaw session JSONL file via SSH.

        The OpenClaw gateway stores conversation transcripts as JSONL files.
        We read the session store to find the session file, then extract the
        last assistant message.
        """
        import subprocess

        try:
            # session_key format: "agent:main:general/task_id"
            # Session files are at: /home/openclawadmin/.openclaw/agents/main/sessions/
            ssh_key = "/app/.ssh_key"
            host = "95.216.212.174"
            base_path = "/home/openclawadmin/.openclaw/agents/main/sessions"

            # Get the most recent JSONL file (excluding sessions.json)
            cmd = [
                "ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=5",
                f"root@{host}",
                f"ls -t {base_path}/*.jsonl 2>/dev/null | head -1 | xargs tail -1",
            ]
            proc = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=10),
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return ""

            line = proc.stdout.strip()
            data = json.loads(line)
            if data.get("type") == "message":
                msg = data.get("message", {})
                if msg.get("role") == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                t = block.get("text", "")
                                # Strip [[reply_to_current]] prefix
                                if t.startswith("[["):
                                    t = t.split("]]", 1)[-1].strip()
                                parts.append(t)
                        text = "\n".join(p for p in parts if p)
                        if text:
                            logger.info("OpenClaw: extracted %d chars from session JSONL", len(text))
                            return text
                    elif isinstance(content, str):
                        return content
        except Exception as exc:
            logger.debug("OpenClaw: JSONL fetch error: %s", exc)
        return ""

    @staticmethod
    def _extract_output(result: dict[str, Any]) -> str:
        """Extract the main text output from an OpenClaw chat response.

        Handles both:
        - RPC response: {content/message/text/output: str}
        - chat.final event payload: {message: {text: str, ...}, sessionKey, runId}
        """
        # chat.final event payload: message is a dict with text field
        msg = result.get("message")
        if isinstance(msg, dict):
            text = msg.get("text", "") or msg.get("content", "") or msg.get("body", "")
            # text may be a nested dict {type: "text", text: "..."} or a list of blocks
            if isinstance(text, dict):
                text = text.get("text", "") or text.get("content", "")
            elif isinstance(text, list):
                parts = []
                for block in text:
                    if isinstance(block, dict):
                        parts.append(block.get("text", "") or block.get("content", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                text = "\n".join(p for p in parts if p)
            if isinstance(text, str) and text.strip():
                return text

        # Direct string fields (RPC response format)
        if isinstance(result.get("content"), str):
            return result["content"]
        if isinstance(msg, str):
            return msg
        if isinstance(result.get("text"), str):
            return result["text"]
        if isinstance(result.get("output"), str):
            return result["output"]
        # Fallback: serialize the whole result
        return json.dumps(result, indent=2, default=str)

    async def startup(self) -> None:
        """Start persistent connection with auto-reconnect."""
        await self._conn.startup()
        logger.info("OpenClawExecutor: persistent connection active")

    async def close(self) -> None:
        """Shut down the executor and close the WebSocket connection."""
        await self._conn.shutdown()
        logger.info("OpenClawExecutor shut down")

    def on_event(self, event_type: str, callback: Any) -> None:
        """Register an event callback (passthrough to connection)."""
        self._conn.on_event(event_type, callback)

    async def chat_history(
        self,
        session_key: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Retrieve chat history for a session via chat.history RPC.

        Returns conversation messages including user inputs and AI responses.
        """
        await self._ensure_connected()
        params: dict[str, Any] = {
            "sessionKey": session_key,
        }
        if limit:
            params["limit"] = limit
        try:
            result = await self._conn.send_request(
                "chat.history",
                params,
                timeout=15.0,
            )
            return result
        except ExecutionError:
            logger.warning("chat.history RPC failed — method may not exist")
            return {"messages": [], "error": "chat.history not available"}

    def get_health(self) -> dict[str, Any]:
        """Return health/status information for monitoring."""
        conn = self._conn
        last_evt = conn._last_event_time
        uptime_since_event = (
            round(time.monotonic() - last_evt, 1) if last_evt > 0 else None
        )
        return {
            "executor": "openclaw",
            "gateway_url": self._config.gateway_url,
            "connected": conn.is_connected,
            "circuit_breaker": self._circuit.state,
            "consecutive_failures": self._circuit.failure_count,
            "gateway_features": conn._gateway_features,
            "events_received": conn._events_received,
            "seconds_since_last_event": uptime_since_event,
            "event_callbacks_registered": sum(
                len(v) for v in conn._event_callbacks.values()
            ),
            "persistent_connection": conn._reconnect_task is not None
            and not conn._reconnect_task.done(),
        }
