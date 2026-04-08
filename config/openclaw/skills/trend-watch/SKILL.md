---
name: trend-watch
description: Analyze technology and market trends with adoption curve positioning and actionable strategic implications
user-invocable: true
---

## Trend Analysis Framework

**Inputs required:**
- Technology or market domain
- Time horizon: 6-month / 12-month / 3-year
- Organizational context: startup / SME / enterprise

## Research Sources
- Gartner Hype Cycle (current year) — adoption curve positioning
- State of [Technology] surveys (Stack Overflow, JetBrains, GitHub)
- GitHub trending / npm download trends / PyPI stats
- Academic preprints (arXiv) for leading indicators in tech
- LinkedIn job posting volume (leading indicator: hiring = adoption)
- Conference program analysis (KubeCon, React Conf, WordCamp, etc.)
- Hungarian context: IVSZ reports, portfolio.hu tech section, hwsw.hu

## Adoption Curve Classification
- **Innovation Trigger:** avoid (unstable APIs, no production case studies)
- **Peak of Inflated Expectations:** evaluate cautiously (hype risk, real signal underneath)
- **Trough of Disillusionment:** re-evaluate seriously (hype gone, real value clearer)
- **Slope of Enlightenment:** strong adoption signal (early majority moving in)
- **Plateau of Productivity:** stable choice for production (mainstream)

## Output Structure

### Trend: [Name]
- **Adoption Stage:** [Hype Cycle position]
- **Evidence:** [3 data points with sources]
- **Strategic Implication:** [what this means for the product/business]
- **Action:** INVEST NOW / WATCH / WAIT / SKIP
- **Timeline:** earliest production-ready date
- **Risk if ignored:** [competitive risk in 12-24 months]

## Framework Evaluation Criteria
- **Evaluate:** community size, corporate sponsorship, production deployments count, security audit history
- **Migration risk:** if replacing, assess breaking change frequency in last 2 major versions
- **Hungarian ecosystem:** local talent availability (LinkedIn HU job postings)

## Output Expectations
- Analysis for top 5-7 trends in domain
- Priority ranking: invest / watch / skip per trend
- 12-month action roadmap (which trends to act on in Q1-Q4)

## Quality Criteria
- All trend claims sourced with publication date ≤ 6 months
- Hungarian context included where relevant (local talent pool, adoption lag vs. global)
- Actionable: each trend has a concrete next step, not just observation
