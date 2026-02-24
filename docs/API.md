# API Reference

OCCP exposes a REST API via FastAPI with automatic OpenAPI documentation at `/docs`.

**Base URL**: `https://api.occp.ai/api/v1` (production) or `http://localhost:8000/api/v1` (local)

---

## 1. Authentication

All protected endpoints require a JWT Bearer token in the `Authorization` header.

### POST `/api/v1/auth/login`

Authenticate and receive a JWT token pair.

- **RBAC**: Public (no token required)
- **Request body**:
  ```json
  {
    "username": "admin",
    "password": "your-password"
  }
  ```
- **Response** `200`:
  ```json
  {
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "token_type": "bearer"
  }
  ```
- **Error** `401`: Invalid credentials

### POST `/api/v1/auth/refresh`

Refresh an expired access token.

- **RBAC**: Authenticated (valid refresh token)
- **Request body**:
  ```json
  {
    "refresh_token": "eyJhbG..."
  }
  ```
- **Response** `200`: New token pair (same schema as login)
- **Error** `401`: Invalid or expired refresh token

### POST `/api/v1/auth/register`

Create a new user account.

- **RBAC**: `system_admin` or `org_admin` — `users:create`
- **Request body**:
  ```json
  {
    "username": "newuser",
    "password": "secure-password",
    "role": "operator"
  }
  ```
- **Response** `201`: Token pair for new user
- **Error** `403`: Insufficient permissions
- **Error** `422`: Validation error (weak password, duplicate username)

---

## 2. Status & Health

### GET `/api/v1/status`

System status and version info.

- **RBAC**: Public (no token required)
- **Response** `200`:
  ```json
  {
    "status": "operational",
    "version": "0.7.0",
    "platform": "OCCP",
    "environment": "production",
    "database": "connected",
    "sandbox": "nsjail"
  }
  ```

### GET `/api/v1/health`

Lightweight health probe for load balancers.

- **RBAC**: Public
- **Response** `200`:
  ```json
  {
    "healthy": true
  }
  ```

### GET `/api/v1/llm/health`

LLM adapter connectivity check.

- **RBAC**: `viewer` — `status:read`
- **Response** `200`: LLM provider status

---

## 3. Tasks

### POST `/api/v1/tasks`

Create a new pipeline task.

- **RBAC**: `operator` — `tasks:create`
- **Request body**:
  ```json
  {
    "name": "Analyze quarterly report",
    "description": "Extract key metrics from Q4 financial data",
    "agent_type": "default",
    "risk_level": "low",
    "metadata": {}
  }
  ```
- **Response** `201`:
  ```json
  {
    "id": "abc123...",
    "name": "Analyze quarterly report",
    "status": "pending",
    "created_at": "2026-02-24T10:00:00Z"
  }
  ```
- **Error** `401`: Missing or invalid token
- **Error** `403`: Role lacks `tasks:create`

### GET `/api/v1/tasks`

List all tasks with optional filtering.

- **RBAC**: `viewer` — `tasks:read`
- **Query params**: `?status=pending&limit=50&offset=0`
- **Response** `200`:
  ```json
  {
    "tasks": [...],
    "total": 42
  }
  ```

### GET `/api/v1/tasks/{task_id}`

Get details for a specific task.

- **RBAC**: `viewer` — `tasks:read`
- **Response** `200`: Full task object including plan, result, error fields
- **Error** `404`: Task not found

---

## 4. Pipeline

### POST `/api/v1/pipeline/run/{task_id}`

Execute the full VAP pipeline on a task.

- **RBAC**: `operator` — `pipeline:run`
- **Response** `200`:
  ```json
  {
    "task_id": "abc123...",
    "status": "completed",
    "stages": ["plan", "gate", "execute", "validate", "ship"],
    "duration_ms": 1234,
    "result": { ... }
  }
  ```
- **Error** `404`: Task not found
- **Error** `422`: Task not in runnable state

---

## 5. Policy

### POST `/api/v1/policy/evaluate`

Test content against all active policy guards.

- **RBAC**: `viewer` — `policy:evaluate`
- **Request body**:
  ```json
  {
    "content": "Text to evaluate for policy violations"
  }
  ```
- **Response** `200`:
  ```json
  {
    "passed": false,
    "violations": [
      {
        "guard": "PIIGuard",
        "severity": "high",
        "detail": "Email address detected"
      }
    ]
  }
  ```

---

## 6. Agents

### GET `/api/v1/agents`

List all registered agent adapters.

- **RBAC**: `viewer` — `agents:read`
- **Response** `200`:
  ```json
  {
    "agents": [
      {
        "type": "planner",
        "class": "EchoPlanner",
        "registered_at": "2026-02-24T10:00:00Z"
      }
    ]
  }
  ```

### GET `/api/v1/agents/{agent_type}`

Get details for a specific agent type.

- **RBAC**: `viewer` — `agents:read`
- **Response** `200`: Agent details with configuration
- **Error** `404`: Agent type not found

### GET `/api/v1/agents/{agent_type}/routing`

Get routing configuration for an agent type.

- **RBAC**: `viewer` — `agents:read`
- **Response** `200`: Routing rules and fallback chain

### POST `/api/v1/agents`

Register a new agent adapter.

- **RBAC**: `org_admin` — `agents:create`
- **Request body**:
  ```json
  {
    "type": "planner",
    "class_name": "CustomPlanner",
    "config": {}
  }
  ```
- **Response** `201`: Registered agent details
- **Error** `403`: Insufficient permissions

### DELETE `/api/v1/agents/{agent_type}`

Unregister an agent adapter.

- **RBAC**: `org_admin` — `agents:delete`
- **Response** `204`: No content
- **Error** `404`: Agent type not found

---

## 7. Audit

### GET `/api/v1/audit`

Retrieve the tamper-evident audit log with SHA-256 hash chain.

- **RBAC**: `viewer` — `audit:read`
- **Query params**: `?limit=100&offset=0`
- **Response** `200`:
  ```json
  {
    "entries": [
      {
        "id": 1,
        "event_type": "pipeline.completed",
        "actor": "system",
        "resource_type": "task",
        "resource_id": "abc123...",
        "detail": { ... },
        "hash": "sha256:abc...",
        "prev_hash": "sha256:def...",
        "timestamp": "2026-02-24T10:00:00Z"
      }
    ],
    "total": 500,
    "chain_valid": true
  }
  ```

---

## 8. WebSocket

### WS `/api/v1/ws/pipeline/{task_id}?token=JWT`

Real-time pipeline event stream.

- **Authentication**: JWT token as `?token=` query parameter
- **RBAC**: `viewer` — `tasks:read`
- **Events**:
  ```json
  {"event": "stage.started", "stage": "plan", "timestamp": "..."}
  {"event": "stage.completed", "stage": "plan", "duration_ms": 120}
  {"event": "pipeline.completed", "status": "success"}
  ```
- Connection closes automatically when pipeline completes or errors.

---

## 9. Error Codes

| Code | Meaning | When |
|------|---------|------|
| `400` | Bad Request | Malformed JSON, invalid parameters |
| `401` | Unauthorized | Missing or expired JWT token |
| `403` | Forbidden | Valid token but insufficient RBAC permissions |
| `404` | Not Found | Resource does not exist |
| `422` | Unprocessable Entity | Validation error (schema mismatch, business rule) |
| `500` | Internal Server Error | Unexpected server failure |

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error description",
  "error_code": "AUTH_TOKEN_EXPIRED"
}
```

---

## Interactive Documentation

Visit `https://api.occp.ai/docs` for the Swagger UI or `https://api.occp.ai/redoc` for ReDoc.

Both are auto-generated from the FastAPI route definitions and always reflect the current API surface.
