# API Reference

OCCP exposes a REST API via FastAPI with automatic OpenAPI documentation at `/docs`.

**Base URL**: `https://api.occp.ai/api/v1` (production) or `http://localhost:8000/api/v1` (local)

---

## 1. Authentication

All protected endpoints require a JWT Bearer token in the `Authorization` header.

### POST `/api/v1/auth/login`

Authenticate and receive a JWT token.

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
    "token_type": "bearer",
    "expires_in": 86400,
    "role": "system_admin"
  }
  ```
- **Error** `401`: Invalid credentials

### POST `/api/v1/auth/refresh`

Refresh an access token using a valid (non-expired) token.

- **RBAC**: Authenticated (valid token)
- **Request body**:
  ```json
  {
    "token": "eyJhbG..."
  }
  ```
- **Response** `200`: New token (same schema as login — `access_token`, `token_type`, `expires_in`, `role`)
- **Error** `401`: Invalid or expired token

### GET `/api/v1/auth/me`

Return the authenticated user's profile.

- **RBAC**: Authenticated (Bearer token)
- **Response** `200`:
  ```json
  {
    "username": "admin",
    "role": "system_admin",
    "display_name": "Admin"
  }
  ```
- **Error** `401`: Missing or invalid token

### POST `/api/v1/auth/register`

Public self-registration — creates viewer-only accounts.

- **RBAC**: Public (no token required)
- **Request body**:
  ```json
  {
    "username": "newuser",
    "password": "secure-password",
    "display_name": "New User"
  }
  ```
- **Response** `201`: TokenResponse (`access_token`, `token_type`, `expires_in`, `role: "viewer"`)
- **Error** `409`: Username already exists
- **Error** `422`: Validation error (password too short)

### POST `/api/v1/auth/register/admin`

Admin-only user creation — allows any role.

- **RBAC**: `org_admin` or `system_admin` — `users:create`
- **Request body**:
  ```json
  {
    "username": "newoperator",
    "password": "secure-password",
    "role": "operator",
    "display_name": "New Operator"
  }
  ```
  `role` accepts: `viewer`, `operator`, `org_admin`, `system_admin`
- **Response** `201`: TokenResponse (`access_token`, `token_type`, `expires_in`, `role`)
- **Error** `401`: Missing or invalid token
- **Error** `403`: Insufficient permissions
- **Error** `409`: Username already exists
- **Error** `422`: Validation error (invalid role, weak password)

---

## 2. Status & Health

### GET `/api/v1/status`

System status and version info.

- **RBAC**: Public (no token required)
- **Response** `200`:
  ```json
  {
    "platform": "OCCP",
    "version": "0.9.0",
    "status": "running",
    "tasks_count": 42,
    "audit_entries": 500
  }
  ```

### GET `/api/v1/health`

Readiness probe — verifies database connectivity and core subsystems.

- **RBAC**: Public
- **Response** `200`:
  ```json
  {
    "status": "healthy",
    "version": "0.9.0",
    "checks": [
      { "name": "database", "status": "ok", "latency_ms": 1.5 },
      { "name": "policy_engine", "status": "ok" },
      { "name": "pipeline", "status": "ok" }
    ]
  }
  ```
  `status` is one of: `healthy`, `degraded`, `unhealthy`

### GET `/api/v1/llm/health`

LLM adapter connectivity check.

- **RBAC**: `viewer` — `status:read`
- **Response** `200`: LLM provider status

---

## 3. User Management

### GET `/api/v1/users`

List all registered users.

- **RBAC**: `org_admin` or `system_admin` — `users:read`
- **Response** `200`:
  ```json
  {
    "users": [
      {
        "id": "abc123...",
        "username": "admin",
        "role": "system_admin",
        "display_name": "Admin",
        "is_active": true,
        "created_at": "2026-02-24T10:00:00Z",
        "updated_at": "2026-02-24T10:00:00Z"
      }
    ],
    "total": 12
  }
  ```
- **Error** `401`: Missing or invalid token
- **Error** `403`: Insufficient permissions

### GET `/api/v1/admin/stats`

Admin statistics — user counts, onboarding funnel, activity.

- **RBAC**: `org_admin` or `system_admin` — `users:read`
- **Response** `200`:
  ```json
  {
    "users_total": 12,
    "users_by_role": { "viewer": 8, "operator": 2, "org_admin": 1, "system_admin": 1 },
    "registrations_last_7_days": 3,
    "onboarding_funnel": {
      "landing": 2,
      "running": 1,
      "done": 9
    },
    "user_activity": [
      {
        "username": "user1",
        "role": "viewer",
        "last_seen": "2026-03-02T10:00:00Z",
        "onboarding_state": "done"
      }
    ]
  }
  ```
- **Error** `401`: Missing or invalid token
- **Error** `403`: Insufficient permissions

---

## 4. Tasks

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

## 5. Pipeline

### POST `/api/v1/pipeline/run/{task_id}`

Execute the full Verified Autonomy Pipeline on a task.

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

## 6. Policy

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

## 7. Agents

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

## 8. Audit

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

## 9. WebSocket

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

## 10. Error Codes

| Code | Meaning | When |
|------|---------|------|
| `400` | Bad Request | Malformed JSON, invalid parameters |
| `401` | Unauthorized | Missing or expired JWT token |
| `403` | Forbidden | Valid token but insufficient RBAC permissions |
| `404` | Not Found | Resource does not exist |
| `409` | Conflict | Duplicate resource (e.g. username already exists) |
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
