# OCCP Onboarding 10/10 — 2026-Q2

**Dátum:** 2026-04-20 · Scope: Self-serve developer signup + activation flow
**Cél:** 10/10 developer onboarding, TTFT < 5 min

---

## §1 Executive — Current vs 10/10

**Jelenlegi (v0.8.2, 2026-02):**
- Landing → register (email+pw) → login → Welcome Panel state machine (MCP install, Skills, LLM health)
- 9 default agent, MCP config executor, session policy panel
- **Gap:** nincs OAuth, nincs "first success" 5 percen belül, nincs API key copy-reveal UX, nincs `create-occp-app` CLI, nincs drip email

**10/10:**
- Landing → GitHub OAuth 1-click → auto-provisioned workspace + API key + "hello-agent" task → **60 sec first task success** + curl snippet
- Email verify async, billing nem blokkol, 1M token/hó free, `npx create-occp-app` egy parancs
- **North Star:** TTFT (Time-To-First-Task) < 5 perc p75

---

## §2 "5 perces első task" stopwatch

| T+ (mm:ss) | Step | Friction |
|---|---|---|
| 00:00 | Landing CTA "Start free" | 0 |
| 00:10 | GitHub OAuth redirect | 1 click |
| 00:25 | Scope consent (read:user, email) | 1 click |
| 00:35 | Auto-create workspace (`user-login` slug) | 0 |
| 00:45 | Welcome modal: "Skip" / "Show me" | skippable |
| 01:00 | Dashboard: API key auto-generated, reveal-once banner | 1 copy click |
| 01:30 | "Hello agent" curl snippet prefilled key-jel | 1 copy click |
| 02:00 | Terminal paste → agent run | 0 |
| 02:30 | Dashboard live-tail: task running | 0 (SSE/WS) |
| 03:00 | Task success, result render | 0 |
| 03:15 | Celebration toast + "Next: Deploy to MCP" | optional |

OCCP **ne kérjen SMS-t** — Anthropic SMS-gate friction killer (Wisdom Gate 2026-01).

---

## §3 OAuth provider 2026

| Provider | Coverage | Priority |
|---|---|---|
| **GitHub OAuth** | ~95% dev | **Primary** (Vercel model) |
| **Google** | Enterprise + hobbyist | **Secondary** |
| Microsoft/Entra | B2B AD | Phase 2 |
| SAML | Enterprise >$10k | Phase 3 |
| Passkeys (WebAuthn) | Chrome 100%, Safari 97% | Phase 2, conditional create |
| Magic link | Fallback | Phase 2 |

Vercel 2026-02 CLI deprecated `--github` flag → OAuth 2.0 Device Flow. OCCP CLI-re ugyanezt.

**FELT:** ha Supabase Auth → GitHub+Google 15 perc setup; custom auth → ~1 nap.

---

## §4 Email verify vs skip

**Adat 2026:**
- Opt-in trial no credit card: median 23.4% konverzió, AI-personalized +6.1pp (Pulseahead)
- Double opt-in: +22.7% downstream (Prospeo)
- GDPR Art. 5(1)(d): verify ajánlott, nem blokkoló

**Ajánlás (EU user base):**
1. Signup → **azonnal dashboard** (verify async)
2. Verify gate csak: első *paid* upgrade előtt / 48h után email-send block
3. Disposable email ban (`mailinator.com` stb.)
4. Double opt-in CSAK marketing listára, nem transactional

→ +3-5pp konverzió vs Anthropic, GDPR-kompatibilis.

---

## §5 API key first display

**Stripe/OpenAI/Anthropic minta:**
- "Show only once" + hashed store
- Copy button prominens, "I saved it" confirmation
- Rotation: dual-key overlap 24-72h

**OCCP UX:**
```
┌─ Welcome! Your API key (shown once): ──────────┐
│ occp_live_sk_xxxxxxxxxxxxxxxxxx  [Copy] [⌘C]  │
│ ☐ I saved this somewhere safe                  │
│ ℹ We store only a hashed version               │
└─────────────────────────────────────────────────┘
```

**Rotation:** `Settings > API Keys > Rotate` → new key, 48h grace, old key 401 + `X-Rotate-Notice: true` header. Revoke külön Danger zone.

**Prefix scoping** (Anthropic): `occp_live_` / `occp_test_` / `occp_pat_` — scanner-friendly (GitGuardian kompatibilis).

---

## §6 Welcome tour tech

| Library | Licenc | Bundle | React | Verdikt |
|---|---|---|---|---|
| **Driver.js** | **MIT** | ~5KB | wrapper | **Ajánlott** |
| Intro.js | AGPL / comm. | 25KB | no | Kerülni |
| Shepherd.js | AGPL / comm. | 40KB | partial | Kerülni |
| React Joyride | MIT | 60KB | yes | Alt |
| Reactour | MIT | 30KB | yes | Alt |

**Ajánlás:** **Driver.js** (lightweight, MIT — kritikus, mivel OCCP kereskedelmi).

**Native alt:** saját `<Tour>` Tailwind + Radix — 200 LoC, zero dep, brand consistency.

---

## §7 `npx create-occp-app` CLI

```bash
npx create-occp-app@latest my-agent
# Prompts:
#   ? Template: hello-agent | rag-pipeline | mcp-server | scheduler
#   ? Language: TypeScript | Python
#   ? Auth: API key (paste) | OAuth device flow | skip
#   ? PM: pnpm | npm | bun
```

**Tech:** Node 20+, ESM, `@clack/prompts` (szebb UX mint commander).
**Templates:** `github.com/occp-ai/templates/{hello-agent,rag-pipeline,mcp-server}`
**Post-install:** `occp login` device-flow ha nincs `OCCP_API_KEY`, majd `occp run hello-agent` → **60 sec** first result.
**AGENTS.md + CLAUDE.md** include (Next.js 2026 default) → Claude Code / Cursor ready.

---

## §8 Sample project: "hello-agent"

**Repo:** `github.com/occp-ai/hello-agent`

```
hello-agent/
├─ README.md           # 3-step quickstart
├─ AGENTS.md           # AI agent guide
├─ .env.example        # OCCP_API_KEY=
├─ package.json        # "run": "occp-sdk run"
├─ src/
│  ├─ agent.ts         # 20 LoC: import { Agent } from '@occp/sdk'
│  └─ tools/echo.ts    # sample tool
└─ .github/workflows/deploy.yml
```

**"Deploy to OCCP" button:**
```markdown
[![Deploy to OCCP](https://occp.ai/deploy-button.svg)](https://dash.occp.ai/deploy?repo=https://github.com/occp-ai/hello-agent)
```
→ GitHub OAuth → repo fork → API key env inject → deploy.

**Replit/CodeSandbox:** `Open in Replit` link `?template=occp-hello-agent`. e2b.dev inline exec Phase 2.

---

## §9 North Star metric: TTFTS5

**Time-To-First-Task-Success within 5 min (%)**
- Numerator: userek akik signup után 300s-en belül sikeres agent run
- Denominator: összes signup (OAuth-autentikált)

**Target trajectory:**
- v0.9 (Q2 baseline): ~15-25% (FELT, no guided flow)
- v0.9.5 (Q3): **40%+**
- v1.0 (Q4): **60%+** (best-in-class)

**Supporting:**
- Signup→OAuth: <15s p75
- OAuth→workspace: <5s p95 (backend SLA)
- API key copy: <60s p75 from first dashboard load
- Curl snippet execution: tracked via API log
- 7-day retention: >30% (industry good)

**Tech:** PostHog self-hosted (GDPR, EU) — funnels + lifecycle cohorts. OCCP self-host ethos kompatibilis.

---

## §10 Drip email — 5 email (day 0/1/3/7/14)

**Eszköz:** Resend (transactional) + PostHog trigger, vagy PostHog natív.

| Day | Subject | Goal | Content |
|---|---|---|---|
| **0** (T+5min, csak ha task NEM success) | "Got stuck? Run your first OCCP task in 60 sec" | Unstick | GIF curl snippet, link quickstart, "Reply for help" |
| **1** (+24h) | "Your AI agent: 3 things it can do today" | Breadth | 3 bullet use-case (RAG, MCP, scheduled), CTA: Try template |
| **3** (+72h) | "How [Company X] built [cool thing]" | Social proof | Case study 200 szó + quote |
| **7** (+7d) | "Hit the 1M free token tier? What's next" | Upgrade | Usage snapshot, Pro $19/mo, no hard upsell |
| **14** (+14d) | "Last look: this is what your OCCP can become" | Re-engage | Winback: roadmap preview, invite beta (FOMO), exit-survey |

**Triggers:** PostHog event `task_success` → suppress #0. `upgrade_clicked` → suppress #4. `unsubscribe_all` → stop.
**DKIM+SPF** `occp.ai`. Unsubscribe footer GDPR Art. 7.
**Open target:** #0 45%+, #1-3 30%+, #4-5 20%+.

---

## Confidence

| Claim | Level |
|---|---|
| GitHub OAuth primary for devs | CONFIRMED |
| Driver.js MIT | CONFIRMED |
| 23.4% opt-in konverzió median | LIKELY |
| Supabase 2-min project init | CONFIRMED |
| OCCP stack Supabase Auth | **FELT** |
| 60% TTFTS5 v1.0-ra | FELT (industry 40-55%, stretch) |

---

## Források (2026-04-20)

- [Treblle — API onboarding best practices](https://treblle.com/blog/accelerating-api-integrations-best-practices-for-faster-onboarding)
- [Amplitude — 7% Retention Rule](https://amplitude.com/blog/7-percent-retention-rule)
- [Amplitude — Time to Value drives retention](https://amplitude.com/blog/time-to-value-drives-user-retention)
- [Pulseahead — Trial-to-paid 2026](https://www.pulseahead.com/blog/trial-to-paid-conversion-benchmarks-in-saas)
- [Vercel CLI login flow 2026](https://vercel.com/changelog/new-vercel-cli-login-flow)
- [Vercel Deploy Button](https://vercel.com/docs/deploy-button)
- [Supabase Getting Started 2026](https://supabase.com/docs/guides/getting-started)
- [DEV — OpenAI Quick Start 2026](https://dev.to/abdul_qadir/openai-api-quick-start-2026-account-api-key-and-billing-setup-9b8)
- [Wisdom Gate — Anthropic API 2026](https://wisdom-gate.juheapi.com/blogs/how-to-get-an-anthropic-api-key-in-2026)
- [Clerk — Custom onboarding Next.js](https://clerk.com/docs/references/nextjs/add-onboarding-flow)
- [state-of-passkeys.io 2026](https://state-of-passkeys.io/)
- [OneUptime — API key mgmt 2026-02](https://oneuptime.com/blog/post/2026-02-20-api-key-management-best-practices/view)
- [Stripe API keys](https://docs.stripe.com/keys)
- [Prospeo — GDPR consent email 2026](https://prospeo.io/s/gdpr-consent-email-marketing)
- [Next.js create-next-app CLI](https://nextjs.org/docs/app/api-reference/cli/create-next-app)
- [OnboardJS — Best React onboarding 2026](https://onboardjs.com/blog/5-best-react-onboarding-libraries-in-2025-compared)
- [Inline Manual — Driver.js vs Intro.js](https://inlinemanual.com/blog/driverjs-vs-introjs-vs-shepherdjs-vs-reactour/)
- [PostHog — Email drip campaign](https://posthog.com/docs/workflows/email-drip-campaign)
- [PostHog — Onboarding email flow](https://posthog.com/blog/how-we-built-email-onboarding)
- [HowdyGo — SaaS onboarding emails](https://www.howdygo.com/blog/saas-onboarding-email-examples)

---
*v1.0 · 2026-04-20 · deep-research agent output*
