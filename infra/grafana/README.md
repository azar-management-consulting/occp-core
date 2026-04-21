# OCCP Grafana SLO Stack

Grafana 11 + Prometheus 2.55 + Alertmanager 0.28 for the OCCP Agent Control Plane.
See also: `infra/observability/README.md` for the OTEL / Phoenix / Langfuse stack.

## Prerequisites

- Docker + Docker Compose v2
- External network `occp-obs` must exist (created by the Phoenix compose in `infra/observability/`):
  ```
  docker network create occp-obs
  ```
- Copy `.env.grafana.example` to `.env.grafana` and set `GF_SECURITY_ADMIN_PASSWORD`.

## Deploy

```bash
cd infra/grafana
docker compose -f docker-compose.grafana.yml up -d
# Verify all three services are healthy:
docker compose -f docker-compose.grafana.yml ps
```

Grafana: http://localhost:3000
Prometheus: http://localhost:9090
Alertmanager: http://localhost:9093

## Dashboard import

**Via provisioning (automatic):** The `occp-slo.json` dashboard is auto-loaded from
`provisioning/dashboards/` on container start. No manual import needed.

**Manual import:** In Grafana UI → Dashboards → Import → Upload JSON file →
select `infra/grafana/dashboards/occp-slo.json`.

## Alert channel setup

1. Grafana UI → Alerting → Contact points → `occp-pagerduty`.
2. Set type `PagerDuty`, paste the `PAGERDUTY_INTEGRATION_KEY` from `.env.grafana`.
3. Test the channel before enabling burn-rate alerts.
4. The alert rules in `alerts/burn-rate.yaml` are provisioned via the Grafana API
   or imported manually via Alerting → Alert rules → Import.

## Burn-rate math

The OCCP SLO target is 99.5% API availability, giving a 30-day error budget of 0.5% × 43,200 min = 216 minutes.
The fast-burn rule fires when the 1-hour error rate exceeds 14.4× the baseline (7.2% errors), meaning the entire budget burns in ~2 hours at that rate.
The slow-burn rule fires when the 6-hour error rate exceeds 3× (1.5% errors), consuming the budget in ~10 hours.
Alert durations (`for: 2m` fast, `for: 15m` slow) prevent flapping on transient spikes.
Both rules include a real-metric fallback using `occp_pipeline_tasks{outcome!="success"}` until HTTP middleware instrumentation ships.

## TODO metrics

The following PromQL expressions in the dashboard and alerts reference metrics not yet
emitted by `observability/metrics_collector.py`. Add instrumentation before relying on them:

| Metric | Panel / Alert | Action needed |
|--------|---------------|---------------|
| `occp_http_request_duration_seconds_bucket` | Panel 1 (latency) | HTTP middleware histogram |
| `occp_http_requests_total` | Panel 2 (error rate), burn-rate alerts | HTTP middleware counter with `status` label |
| `occp_llm_cost_usd_total` | Panel 3 (token spend) | Counter in `gen_ai_tracer.py` with `model_id` label |
| `occp_kill_switch_active` | Panel 4 (kill switch) | Gauge in kill switch handler |
| `kill_switch_activations_total` | Panel 4 (activations) | Counter per activation event |
| `occp_pipeline_runs_total` | Panel 5 (pipeline) | Alias/replacement for `occp_pipeline_tasks` |
