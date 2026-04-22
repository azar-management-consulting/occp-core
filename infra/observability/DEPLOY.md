# OCCP Observability Stack — Deploy Runbook

**Target:** brain server `195.201.238.144` (Hetzner AX41, Ubuntu 22.04, Docker 24+)
**Stack:** Phoenix 6006 + Grafana 3000 + Prometheus 9090 + Alertmanager 9093

---

## Prerequisites

- OCCP core already deployed to `/opt/occp` (creates the `occp-core_default` network)
- DNS records exist: `grafana.occp.ai` and `traces.occp.ai` → brain IP (Cloudflare proxy ON)
- Caddy running and serving `api.occp.ai` / `dash.occp.ai`

---

## Step 1 — SSH to brain

```bash
ssh root@195.201.238.144
```

---

## Step 2 — Verify OCCP core is up and network exists

```bash
cd /opt/occp
docker compose up -d
docker network ls | grep occp-core_default
# Must output: <id>  occp-core_default  bridge  local
```

If network is absent, OCCP core is not running. Fix before proceeding.

---

## Step 3 — Deploy Phoenix

```bash
cd /opt/occp/infra/observability

# First deploy only:
cp .env.phoenix.example .env.phoenix

# Edit secrets:
# PHOENIX_PG_PASSWORD=$(openssl rand -base64 24)
# PHOENIX_SECRET=$(openssl rand -base64 32)
# PHOENIX_DB_URL=postgresql://phoenix:<PHOENIX_PG_PASSWORD>@phoenix-postgres:5432/phoenix
nano .env.phoenix

docker compose -f docker-compose.phoenix.yml --env-file .env.phoenix up -d

# Verify:
docker compose -f docker-compose.phoenix.yml --env-file .env.phoenix ps
docker logs phoenix --tail=30
# Expect: "Phoenix is running" on port 6006
```

---

## Step 4 — Deploy Grafana + Prometheus + Alertmanager

```bash
cd /opt/occp/infra/grafana

# First deploy only:
cp .env.grafana.example .env.grafana

# Edit secrets:
# GF_SECURITY_ADMIN_PASSWORD=<strong password>
# GF_SERVER_ROOT_URL=https://grafana.occp.ai
# ALERTMANAGER_EXTERNAL_URL=http://localhost:9093
nano .env.grafana

docker compose -f docker-compose.grafana.yml --env-file .env.grafana up -d

# Verify services are healthy:
docker compose -f docker-compose.grafana.yml --env-file .env.grafana ps
```

---

## Step 5 — Verify Prometheus scrape targets

```bash
# Wait ~30s for Prometheus to scrape first cycle, then:
curl -s http://127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# Expected: "health": "up" for occp-api, prometheus, grafana, alertmanager
# If occp-api shows "down": confirm api container is on occp-core_default network:
docker inspect occp-core-api-1 | jq '.[0].NetworkSettings.Networks | keys'
```

---

## Step 6 — Expose via Caddy

```bash
cd /opt/occp/infra/caddy

# Append the obs virtual hosts (or use import):
cat Caddyfile.obs >> Caddyfile

# Reload Caddy (no downtime):
docker exec occp-caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## Step 7 — Cloudflare DNS (if not done)

In Cloudflare dashboard for `occp.ai`:
```
grafana.occp.ai  CNAME  195.201.238.144  (Proxy: ON)
traces.occp.ai   CNAME  195.201.238.144  (Proxy: ON)
```

---

## Step 8 — Smoke test

```bash
# Grafana UI (expect 200):
curl -s -o /dev/null -w "%{http_code}" https://grafana.occp.ai/api/health

# Phoenix UI (expect 200):
curl -s -o /dev/null -w "%{http_code}" https://traces.occp.ai/healthz

# Prometheus targets (expect all "up"):
curl -s http://127.0.0.1:9090/api/v1/targets | jq '[.data.activeTargets[].health]'
```

---

## Rollback

```bash
# Stop obs stack (preserves volumes):
cd /opt/occp/infra/grafana && docker compose -f docker-compose.grafana.yml down
cd /opt/occp/infra/observability && docker compose -f docker-compose.phoenix.yml --env-file .env.phoenix down

# Destroy volumes if full reset needed (data loss):
# docker volume rm phoenix-pg-data grafana-data prometheus-data alertmanager-data
```

---

## Resource budget (AX41, 64 GB)

| Container       | RAM limit | RAM typical |
|-----------------|-----------|-------------|
| phoenix         | 4 GB      | ~1.5 GB     |
| phoenix-postgres| 2 GB      | ~256 MB     |
| grafana         | —         | ~300 MB     |
| prometheus      | —         | ~512 MB     |
| alertmanager    | —         | ~64 MB      |
| **Total obs**   | **~6 GB** | **~2.6 GB** |

OCCP core (api + dash) adds ~512 MB. Total committed: ~7 GB of 64 GB (11%).
