# Vercel deploy — OCCP web surfaces

Two Next.js apps live in this repo that target Vercel:

| App           | Path            | Domain              | Project name      |
|---------------|-----------------|---------------------|-------------------|
| Landing       | `landing-next/` | `v2.occp.ai`        | `occp-landing`    |
| Docs          | `docs-next/`    | `docs.occp.ai`      | `occp-docs`       |

The dashboard (`dash/`) ships as a Docker container on Hetzner, not on
Vercel. See `../.planning/OCCP_DASHBOARD_10_2026.md`.

## 1. Create Vercel projects

Run once from a laptop with Vercel CLI logged in:

```bash
cd landing-next
vercel link --project occp-landing --yes
vercel --prod

cd ../docs-next
vercel link --project occp-docs --yes
vercel --prod
```

Vercel auto-detects the `vercel.json` in each directory (framework =
Next.js, region = `fra1`, install = `npm ci --no-audit --no-fund`).

## 2. Environment variables

### landing-next

| Var                       | Where    | Value                              |
|---------------------------|----------|------------------------------------|
| `NEXT_PUBLIC_OCCP_API_URL`| prod+prev| `https://api.occp.ai`              |
| `NEXT_PUBLIC_SITE_URL`    | prod     | `https://v2.occp.ai`               |

### docs-next

| Var                       | Where    | Value                              |
|---------------------------|----------|------------------------------------|
| `NEXT_PUBLIC_OCCP_API_URL`| prod+prev| `https://api.occp.ai`              |
| `NEXT_PUBLIC_SITE_URL`    | prod     | `https://docs.occp.ai`             |

Set via `vercel env add <NAME> production` or the dashboard.

## 3. DNS wiring

Both domains sit behind Cloudflare (zone `occp.ai`). Add these two CNAME
records with proxy **off** (grey cloud — Vercel needs direct CNAME):

```
v2.occp.ai.     CNAME   cname.vercel-dns.com.
docs.occp.ai.   CNAME   cname.vercel-dns.com.
```

Then in each Vercel project → Settings → Domains, add the hostname.
Vercel issues the Let's Encrypt cert automatically (≤60s).

The legacy `landing/index.html` stays live on `occp.ai` until cutover.

## 4. Cutover plan

1. Deploy `landing-next` to `v2.occp.ai` (staging).
2. QA: Core Web Vitals, Lighthouse, manual smoke.
3. Cut `occp.ai` A/AAAA → Vercel (proxied via Cloudflare OK at this point).
4. Retire `/opt/occp/landing/index.html` on brain.

Rollback: flip `occp.ai` back to the brain IP (DNS TTL 300s).

## 5. Preview deploys

Every PR gets an auto-preview at `<branch>-occp-landing.vercel.app` and
`<branch>-occp-docs.vercel.app`. Merge protection should require a green
Vercel deploy status check.

## Artifacts

- `landing-next/vercel.json` — landing config (headers, regions)
- `docs-next/vercel.json` — docs config (headers, regions)
- `.planning/OCCP_LANDING_10_2026.md` — landing roadmap
- `.planning/OCCP_DOCS_10_2026.md` — docs roadmap
