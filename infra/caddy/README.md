# Caddy reverse proxy for v2.occp.ai + docs.occp.ai

Self-hosted Next.js landing + docs on the brain server (195.201.238.144),
fronted by Cloudflare for TLS termination.

## Deploy (brain server)

```bash
# From occp-core/ repo root on the brain host
docker compose build landing docs caddy
docker compose up -d landing docs caddy
```

This brings up three containers:
- `landing` on `127.0.0.1:3100` -> container `:3000` (Next.js standalone)
- `docs`    on `127.0.0.1:3200` -> container `:3000` (Next.js standalone)
- `caddy`   on `127.0.0.1:3300` -> container `:80`   (reverse proxy entry)

## Cloudflare DNS + routing

1. Add CNAME (or A) records in Cloudflare:
   - `v2.occp.ai`   -> brain IP `195.201.238.144` (orange cloud ON / proxied)
   - `docs.occp.ai` -> brain IP `195.201.238.144` (orange cloud ON / proxied)

2. Cloudflare terminates TLS; origin is plain HTTP.
   Add a Cloudflare Origin Rule (or Page Rule) to rewrite the origin port:
   - Match: `v2.occp.ai` OR `docs.occp.ai`
   - Action: Override origin -> `195.201.238.144:3300` (HTTP)

3. SSL/TLS mode: `Flexible` is sufficient for now (CF -> origin HTTP on :3300).
   For stricter posture, terminate TLS at Caddy and switch CF mode to `Full`.

## Debugging

Tail Caddy logs (JSON):
```bash
docker compose logs -f caddy
```

Test routing locally on brain:
```bash
curl -H 'Host: v2.occp.ai'   http://127.0.0.1:3300/
curl -H 'Host: docs.occp.ai' http://127.0.0.1:3300/
```

Reload Caddyfile after edits (no restart needed):
```bash
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```
