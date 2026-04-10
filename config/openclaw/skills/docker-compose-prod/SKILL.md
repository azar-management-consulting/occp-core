---
name: docker-compose-prod
description: Create production-grade Docker Compose configurations with multi-stage builds and secrets management
user-invocable: true
---

## Production Compose Standards

**Format:** `compose.yaml` (not `docker-compose.yml` — deprecated name)
**Network:** always define explicit named networks, never use `host` mode for app containers

## Service Template
```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production          # multi-stage: development / testing / production
    image: occp-api:${VERSION:-latest}
    restart: unless-stopped
    environment:
      - DATABASE_URL=${DATABASE_URL}  # inject from .env — never hardcode
    secrets:
      - db_password
    networks:
      - internal
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

## Security Rules
- Never use `privileged: true`
- Never mount `/var/run/docker.sock` unless specifically justified
- Run containers as non-root user: `user: "1000:1000"` or Dockerfile `USER`
- Secrets via Docker secrets or env vars from `.env` (`.env` in `.gitignore`)
- Read-only filesystem where possible: `read_only: true` + tmpfs for `/tmp`

## Volume Strategy
- Named volumes for persistent data (DB, uploads)
- Bind mounts only for development (never in prod compose)
- Backup volume: label with `backup=true` for automated backup scripts

## Output Expectations
- Complete `compose.yaml` for production deployment
- Corresponding `Dockerfile` with multi-stage build
- `.env.example` with all required variables documented
- `healthcheck` defined for every service

## Quality Criteria
- `docker compose config` validates without warnings
- All images pinned to digest or specific version tag (no `latest`)
- Containers restart correctly after `docker compose restart`
