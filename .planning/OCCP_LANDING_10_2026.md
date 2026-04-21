# OCCP Landing 10/10 — 2026-Q2

**Dátum:** 2026-04-20 · Scope: `occp.ai` (jelenleg 1999 sor static HTML, retro CRT esztétika)

---

## §1 Executive — 5 mistake + 5 win pattern

**5 mistake current OCCP landing:**
1. **CRT scanline + vignette over-applied** — pattern-match "retro demo", nem "production enterprise"
2. **Hero headline absztrakt** — "The Control Plane that governs AI agents" nem passes 5-second test: no pain, no outcome
3. **Three CTA verseng** — "Start Onboarding" + "Dashboard" + "GitHub" → modern: ONE primary + ONE secondary
4. **No inline code snippet hero** — `pip install` terminal box weak vs Vercel `streamText({...})` live snippet
5. **Monolith 1999-line HTML** — zero code-split, zero islands, zero ISR, zero Vercel Edge, no component reuse

**5 competitor winning patterns:**
1. **Outcome-first headline** — Temporal: "Failures happen. Temporal makes them irrelevant."
2. **Tangible benefit + scale** — Supabase: "Build in a weekend, Scale to millions"
3. **Runnable code in hero** — Vercel AI `streamText({...})`
4. **Split-screen hero (text + live product)** — Datadog 2026 standard
5. **Compliance badges above fold** — 66% B2B buyers require SOC2

---

## §2 Hero redesign (konkrét copy)

**Badge (eyebrow):** `v1.0 · Open Source · SOC2 Type II · EU AI Act Art. 14`

**H1:** `Ship AI agents you can defend in an audit.`

**H1 subline:** `Every autonomous action verified, logged, and reversible — before it runs.`

**Subheadline:** `The open-source Agent Control Plane with a 5-gate Verified Autonomy Pipeline. Policy-enforced. Tamper-evident. Self-hosted or managed.`

**Primary CTA:** `Start free — no credit card` → `dash.occp.ai/onboarding/start`
**Secondary CTA (ghost):** `Read the docs` → `docs.occp.ai`
**Tertiary (text link):** `★ 1.2k on GitHub` — FELT: verify actual count

**Trust row:** `Built on · OpenAI · Anthropic · MCP · OpenTelemetry · FastAPI · Postgres` (adopter logos §5-ben)

---

## §3 Feature sections struktúra (6-10 section)

Per [evilmartians devtool study](https://evilmartians.com/chronicles/we-studied-100-devtool-landing-pages-here-is-what-actually-works-in-2025):

1. **Hero** — 100vh split layout
2. **Code snippet + "Run in 30s"** — tabs Python/TS/curl
3. **Verified Autonomy Pipeline** — animált 5-stage scroll-triggered (Motion/React)
4. **"Why OCCP" comparison table** — vs LangGraph (29.7k★) / CrewAI (45.9k★): governance-by-default win row
5. **Feature grid (3x2)** — Multi-LLM Failover · MCP Native · Policy-as-Code · Tamper-Evident Audit · Multi-Tenant · Skills Marketplace
6. **Interactive "Try a policy" playground** (§6)
7. **Compliance + trust** — SOC2, HIPAA, EU AI Act Art. 14 badges; `/trust`, `/status`, `/security.txt`
8. **Social proof** — testimonials, GitHub stars widget, Discord, changelog teaser
9. **Pricing** (§7)
10. **Final CTA + footer** — docs, status, community, legal, RSS

---

## §4 Code snippet hero — OCCP konkrét példa

**3-tab code block, default Python:**

```python
# pip install occp
from occp import ControlPlane

cp = ControlPlane(policy="policies/finance.rego")

result = cp.run(
    agent="claude-opus-4-7",
    task="Refund order #4521 if return window is open",
)
# → PLAN → VERIFY → APPROVE → EXECUTE → AUDIT (all signed, all reversible)
print(result.audit_chain_id)
```

**TypeScript:**
```ts
import { ControlPlane } from "@occp/sdk";
const cp = new ControlPlane({ policy: "policies/finance.rego" });
const { auditChainId } = await cp.run({ agent: "claude-opus-4-7", task: "…" });
```

**curl:**
```bash
curl -X POST https://api.occp.ai/v1/pipelines \
  -H "Authorization: Bearer $OCCP_KEY" \
  -d '{"agent":"claude-opus-4-7","task":"…","policy":"finance"}'
```

Right side: **live pipeline visualization** — 5 nodes lighting up mint "running". Motion 12 scroll.

---

## §5 Social proof plan

| Proof Type | Target | Source |
|---|---|---|
| GitHub stars widget (live) | ≥500 at launch | Shields.io badge |
| Design-partner logos (3-5) | secure via outbound Q2 | Stripe/Supabase grid |
| Written quote + headshot (2) | CTO-level | Temporal style |
| 60-sec video testimonial (1) | Loom embed autoplay muted | |
| Changelog teaser | weekly cadence | Vercel/Resend — FELT |
| Discord member count | ≥100 before launch | Discord widget |
| Compliance badges | SOC2 Type II pursuit + EU AI Act self-attest | |
| Status page | status.occp.ai (Vercel/BetterStack) | |

**Min viable @ soft launch:** stars + 3 logo + 1 quote + compliance badge + status page.

---

## §6 Interactive element: "Try a Policy"

**Koncept:** Inline Rego/OPA playground. User paste agent action JSON; OCCP shows 5-gate pipeline real-time finance policy-val.

**Tech:** Monaco editor (VS Code engine) + WASM-compiled OPA + React server action `/api/playground/evaluate`. Cap 100 eval/IP/hour.

**Default example:**
```json
{ "agent": "refund_bot", "action": "refund", "amount_usd": 8500 }
```
→ `GATE 3 (APPROVE): REQUIRES_HUMAN` — "amount > $5000, human-in-the-loop per EU AI Act Art. 14"

**Precedent:** Baseten interactive ML demo 2026 standard.

**Lighter alt:** asciinema cast → zero backend, still "live" feel.

---

## §7 Pricing strategy

Per [NxCode 2026](https://www.nxcode.io/resources/news/saas-pricing-strategy-guide-2026): hybrid (seat + usage) 43% adoption → 61% by EOY 2026.

| Tier | Price | Who | Limits |
|---|---|---|---|
| **OSS / Self-hosted** | Free (Apache 2.0) | Solo, OSS contrib | Unlimited, Discord support |
| **Team (Cloud)** | $49/mo + $0.001/action | Startups 3-20 dev | 100k actions free, 3 seats, email, 30d audit |
| **Business** | $499/mo + usage | Growth 20-100 dev | SSO, SOC2 report, 1y audit, Slack Connect |
| **Enterprise** | Contact sales | Regulated | HIPAA BAA, EU residency, VPC, 7y audit, SLA |

**Pszichológia:** OSS free anchor → Business ($499) center → Enterprise hides price (2026 B2B convention).

---

## §8 Typography + color tokens

**Font: Geist family** (free, SIL OFL, dev-native). Drop IBM Plex Mono.
- **Sans:** Geist Sans 400/500/600/700
- **Mono:** Geist Mono 400/500 (code only)
- **Badge accent:** Geist Pixel Square (nod to terminal heritage) — 2026-02-06 released

**Type scale (8pt grid):** 72/56/40/28/20/16/14/12. Line-height display 1.1, body 1.5.

**Color tokens OKLCH (Tailwind v4 default):**
```css
:root {
  /* Brand — OCCP green, kevésbé neon mint jelenlegi #33ff33 */
  --brand:        oklch(0.72 0.18 145);  /* verified-green */
  --brand-subtle: oklch(0.95 0.05 145);
  --warn:         oklch(0.78 0.16 70);   /* HITL amber */
  --danger:       oklch(0.62 0.22 27);   /* policy-violation red */
  /* Neutrals (Linear-ish) */
  --bg:           oklch(0.14 0.01 260);
  --bg-elev:      oklch(0.18 0.01 260);
  --border:       oklch(0.28 0.01 260);
  --fg:           oklch(0.96 0.01 260);
  --fg-muted:     oklch(0.70 0.01 260);
}
@media (prefers-color-scheme: light) {
  :root { --bg: oklch(0.99 0 0); --fg: oklch(0.18 0.01 260); }
}
```

**Dark-first** (Linear convention). Drop CRT scanline + vignette. **Keep egy tasteful jel** "terminal DNA":
- Geist Pixel version badge
- Cursor blink H1 utolsó szón
- Monospace install box

---

## §9 10-step migration plan (static HTML → Next.js → Vercel)

1. **Scaffold:** `pnpm create next-app@latest occp-web --ts --tailwind --app --src-dir --import-alias "@/*"` (Next 15, Tailwind v4)
2. **Install primitives:** `shadcn@latest init` — Button, Card, Tabs, Dialog + `geist` + `motion` + `lucide-react`
3. **Content extract:** 1999-line `landing/index.html` → `content/sections/*.mdx` (per §3 section)
4. **Layout:** `app/layout.tsx` Geist fonts, `next-themes`, `<Analytics />`, `<SpeedInsights />`
5. **Hero component:** split-layout server comp + client island (code-snippet tabs + copy)
6. **Pipeline animation:** CSS pipeline → `motion/react` `useScroll` + `useTransform`
7. **Playground route:** `app/api/playground/evaluate/route.ts` edge, Upstash Ratelimit
8. **SEO:** port OG from current lines 13-25 → `generateMetadata`, `sitemap.ts`, `robots.ts`, JSON-LD `SoftwareApplication`
9. **CI:** GHA → Vercel preview per PR, Lighthouse CI budget (LCP ≤1.8s, CLS ≤0.05, TBT ≤200ms)
10. **Deploy:** `vercel --prod`; DNS `occp.ai` + `dash.occp.ai` Hostinger split; 301 from old HTML after QA

**Rollback:** keep `v1.occp.ai` subdomain old static 30 nap post-launch; feature-flag cutover.

---

## §10 A/B test matrix

Via Vercel Edge Config + `@vercel/flags`. 50/50 split, min 2 hét / 5000 visitor/variant, primary metric `onboarding_started`.

| ID | Headline | Focus | Hipotézis |
|---|---|---|---|
| **A (control)** | "Ship AI agents you can defend in an audit." | audit/reversible | Fear-of-incident enterprise |
| **B** | "The Agent Control Plane for regulated industries." | compliance | Specificity beats outcome for CISOs |
| **C** | "Five gates between your agents and production." | mechanism | Devs click mechanism-specific |
| **D** | "Governed agents, by default." | minimalism (Linear) | Short copy wins mobile (44-char rule) |
| **E** | "Every autonomous action — verified before it runs." | cause-effect | Action-language drives sign-up |

**Secondary tests:**
- CTA: `Start free` vs `Try the playground` vs `Install OCCP`
- Media: static diagram vs Motion-animated vs 15-sec Loom
- Trust row: above CTA vs below vs sticky footer
- Snippet default tab: Python vs TS vs curl

**Stop criterion:** ha bármi >15% lift p<0.05 → azonnal promote.

---

## Confidence

- **CONFIRMED:** Temporal hero, Supabase hero, Vercel AI code snippet, Geist fonts, Tailwind v4 OKLCH, LangGraph 29.7k★, CrewAI 45.9k★, EU AI Act 2026-08 deadline, SOC2 B2B gate 66%, Motion 12 rename, Next.js 15 App Router stable
- **LIKELY:** Datadog split-screen hero, Supabase "Start your project" green CTA, interactive-demo-in-hero 2026 standard
- **FELT:** exact OCCP GitHub star count, verbatim anthropic.com hero text, Resend-style changelog, domain split `occp.ai` / `dash.occp.ai`

---

## Források (2026-04-20)

- [anthropic.com](https://www.anthropic.com/) · [openai.com/api](https://openai.com/api/) · [langchain.com](https://www.langchain.com/)
- [temporal.io](https://temporal.io/) · [vercel.com/ai](https://vercel.com/ai) · [vercel.com/font](https://vercel.com/font)
- [Geist Pixel 2026-02](https://vercel.com/blog/introducing-geist-pixel)
- [supabase.com](https://supabase.com/) · [modal.com](https://modal.com/) · [e2b.dev](https://e2b.dev/)
- [baseten.co interactive ML demo](https://www.baseten.co/blog/interactive-ml-demo-landing-page)
- [ui.shadcn.com Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4)
- [motion.dev](https://motion.dev) · [motion.dev/docs/react](https://motion.dev/docs/react)
- [linear.app/brand](https://linear.app/brand)
- [SaaS Hero value prop 2026](https://www.saashero.net/strategy/saas-value-proposition-examples-2026/)
- [SaaS Hero enterprise landing 2026](https://www.saashero.net/design/enterprise-landing-page-design-2026/)
- [Causalfunnel hero mistakes](https://www.causalfunnel.com/blog/10-hero-section-mistakes-you-must-avoid-in-2026/)
- [evilmartians 100 devtool pages](https://evilmartians.com/chronicles/we-studied-100-devtool-landing-pages-here-is-what-actually-works-in-2025)
- [NxCode SaaS pricing 2026](https://www.nxcode.io/resources/news/saas-pricing-strategy-guide-2026)
- [secureframe.com SOC2+HIPAA](https://secureframe.com/hub/hipaa/and-soc-2-compliance)
- [helpnetsecurity EU AI Act 2026](https://www.helpnetsecurity.com/2026/04/07/comp-ai-open-source-compliance-platform/)
- [Next.js migration docs](https://nextjs.org/docs/app/guides/migrating/app-router-migration)

---
*v1.0 · 2026-04-20 · deep-research agent output*
