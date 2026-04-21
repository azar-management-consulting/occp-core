# OCCP Observability — Self-Hosted Stack

Self-hosted LLM trace backend for OCCP. Two interchangeable stacks are
provided; pick ONE per host (running both on a CX32 is tight but possible
for staging).

## Stack comparison

| Aspect | Phoenix (Arize) | Langfuse v3 |
|---|---|---|
| Footprint | postgres + 1 app container | postgres + clickhouse + redis + 2 app containers |
| Setup effort | Low — single compose, ~5 min | Medium — more services, secret generation |
| UI depth | Trace explorer, evals, datasets | Traces, prompt mgmt, evals, users, datasets, sessions, billing export |
| OTLP native | Yes (4317 gRPC / 4318 HTTP) | Yes via `/api/public/otel/v1/traces` |
| gen_ai semconv | Native rendering | Native rendering |
| RAM @ idle | ~1.5 GB | ~2.5 GB |
| Best for | Dev / quick self-host | Prod ops, prompt governance |

Default recommendation: **Phoenix for the first CX32 rollout**, Langfuse once
we need prompt/version management.

## Host layout

Target: Hetzner CX32 (4 vCPU, 8 GB RAM). ARM and x86 images both available.

```
/opt/occp-obs/
  occp-core/                      # cloned repo
    infra/observability/
      docker-compose.phoenix.yml
      docker-compose.langfuse.yml
      .env.phoenix                # <-- YOU create this, chmod 600
      .env.langfuse               # <-- YOU create this, chmod 600
```

## Initial deploy — Phoenix

```bash
ssh root@<cx32-ip>

# Prereqs (one-time)
apt update && apt install -y docker.io docker-compose-plugin git ufw
systemctl enable --now docker
ufw allow 22/tcp
ufw allow 443/tcp          # reverse proxy only — do NOT open 4317/4318/6006 publicly
ufw --force enable

# Repo + shared network
mkdir -p /opt/occp-obs && cd /opt/occp-obs
git clone https://github.com/azarconsulting/occp-core.git
cd occp-core/infra/observability

docker network create occp-obs

# Secrets
cp .env.phoenix.example .env.phoenix
chmod 600 .env.phoenix
# edit placeholders:
#   PHOENIX_PG_PASSWORD=$(openssl rand -hex 24)
#   PHOENIX_SECRET=$(openssl rand -hex 32)
#   PHOENIX_DB_URL must match PHOENIX_PG_PASSWORD

# Launch
docker compose -f docker-compose.phoenix.yml --env-file .env.phoenix up -d
docker compose -f docker-compose.phoenix.yml ps
docker compose -f docker-compose.phoenix.yml logs -f phoenix
```

## Initial deploy — Langfuse

```bash
cd /opt/occp-obs/occp-core/infra/observability
docker network create occp-obs     # skip if it exists

cp .env.langfuse.example .env.langfuse
chmod 600 .env.langfuse
# generate:
#   LANGFUSE_PG_PASSWORD=$(openssl rand -hex 24)
#   CLICKHOUSE_PASSWORD=$(openssl rand -hex 24)
#   REDIS_PASSWORD=$(openssl rand -hex 24)
#   NEXTAUTH_SECRET=$(openssl rand -base64 32)
#   SALT=$(openssl rand -base64 32)
#   ENCRYPTION_KEY=$(openssl rand -hex 32)
# then update LANGFUSE_DATABASE_URL and LANGFUSE_REDIS_URL to match.

docker compose -f docker-compose.langfuse.yml --env-file .env.langfuse up -d
```

## Exposing publicly — Cloudflare Tunnel (recommended)

No open ports, mTLS-ish via CF Access.

```bash
# On the CX32
cloudflared tunnel login
cloudflared tunnel create occp-obs
cat > /etc/cloudflared/config.yml <<'YML'
tunnel: occp-obs
credentials-file: /root/.cloudflared/<tunnel-uuid>.json
ingress:
  # Phoenix UI + OTLP HTTP (port 4318 is proxied off 6006 internally)
  - hostname: traces.occp.ai
    service: http://phoenix:6006
  # OTLP gRPC needs HTTP/2
  - hostname: traces-grpc.occp.ai
    service: grpc://phoenix:4317
  - service: http_status:404
YML
cloudflared service install
```

Or **Caddy** if you prefer a local reverse proxy:

```caddy
traces.occp.ai {
  reverse_proxy phoenix:6006
}
traces-grpc.occp.ai {
  reverse_proxy h2c://phoenix:4317
}
```

## Pointing OCCP backend at it

On the OCCP API host, set:

```bash
OCCP_OTEL_ENABLED=true
OCCP_OBSERVABILITY_STACK=phoenix            # or: langfuse
OCCP_OTEL_ENDPOINT=https://traces.occp.ai:4318
# Phoenix auth (if PHOENIX_ENABLE_AUTH=true):
OCCP_OTEL_HEADERS=authorization=Bearer%20<phoenix-api-key>
```

For Langfuse:

```bash
OCCP_OBSERVABILITY_STACK=langfuse
OCCP_OTEL_ENDPOINT=https://traces.occp.ai/api/public/otel
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://traces.occp.ai
```

The `observability.phoenix_exporter.auto_configure()` hook in `api/app.py`
reads `OCCP_OBSERVABILITY_STACK` and calls `init_otel` with the right
endpoint. Missing/unset → no-op (safe default).

## Backups

### Phoenix

```bash
# pg_dump (nightly cron on host)
docker exec phoenix-postgres pg_dump -U phoenix phoenix \
  | gzip > /backup/phoenix-$(date +%F).sql.gz

# Volume snapshot (weekly)
docker run --rm -v phoenix-pg-data:/src -v /backup:/dst alpine \
  tar czf /dst/phoenix-pg-volume-$(date +%F).tgz -C /src .
```

### Langfuse

```bash
# Postgres
docker exec langfuse-postgres pg_dump -U langfuse langfuse \
  | gzip > /backup/langfuse-pg-$(date +%F).sql.gz

# ClickHouse — use BACKUP TO Disk or clickhouse-backup:
docker exec langfuse-clickhouse clickhouse-client \
  --user clickhouse --password "$CLICKHOUSE_PASSWORD" \
  --query "BACKUP DATABASE default TO Disk('backups', 'langfuse-$(date +%F).zip')"
```

Ship backups off-host (S3/B2). Retention: 30 days hot, 1 year cold.

## Upgrades

```bash
cd /opt/occp-obs/occp-core
git pull
cd infra/observability

# Pin the tag you want in docker-compose.*.yml, then:
docker compose -f docker-compose.phoenix.yml pull
docker compose -f docker-compose.phoenix.yml up -d
docker image prune -f
```

Rolling upgrades: Phoenix is a single process, expect ~30 s downtime.
Langfuse web+worker can be restarted independently — update worker first,
then web, to drain any in-flight events cleanly.

## Health checks

```bash
# Phoenix
curl -fsS http://localhost:6006/healthz

# Langfuse
curl -fsS http://localhost:3100/api/public/health
```

Both compose files declare container-level healthchecks; `docker compose ps`
will surface status.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `network occp-obs not found` | Forgot the external network | `docker network create occp-obs` |
| Phoenix: `sqlalchemy.exc.OperationalError` | Wrong `PHOENIX_DB_URL` password | Match `PHOENIX_PG_PASSWORD` exactly |
| Langfuse web: 503 on startup | ClickHouse migrations still running | Check `docker logs langfuse-worker`; wait ~60 s |
| OTLP 401 | Phoenix auth enabled, no bearer | Set `OCCP_OTEL_HEADERS=authorization=Bearer%20<key>` |
| Traces missing `gen_ai.*` attrs | `init_otel` not called in app lifespan | Verify `OCCP_OTEL_ENABLED=true` and `phoenix_exporter.auto_configure()` |
