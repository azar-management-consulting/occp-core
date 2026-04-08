---
name: procurement-scan
description: Scan Hungarian and EU procurement databases for relevant tenders and funding opportunities
user-invocable: true
---

## Procurement Data Sources

**Hungarian:**
- Közbeszerzési Értesítő (KÉ): kozbeszerzesek.hu — official HU procurement journal
- Közbeszerzési Hatóság: kh.gov.hu — policy, statistics, historical data
- Palyazat.gov.hu — EU-funded grant programs
- Szechenyi2020.hu — Széchenyi Plan tenders

**EU-level:**
- TED (Tenders Electronic Daily): ted.europa.eu — all EU public procurement above threshold
- CORDIS: cordis.europa.eu — EU R&D / Horizon funding

**Private sector intelligence:**
- Opten.hu — Hungarian company financial data (detect large project budgets)
- LinkedIn company news — acquisition/expansion signals that trigger procurement

## Search Parameters
```
Required inputs:
- CPV codes (Common Procurement Vocabulary): list 3-5 relevant codes
- Contracting authority type: central gov / municipality / state enterprise / EU body
- Estimated value range (EUR): min / max
- Deadline window: next 14 / 30 / 60 days
- Keywords (HU + EN): must cover Hungarian procurement language
```

## Tender Evaluation Criteria
Score each opportunity 1-5 on:
1. **Fit score:** how well services match tender scope
2. **Win probability:** incumbent risk, previous contract history, competition level
3. **Strategic value:** reference client quality, sector expansion
4. **Resource requirement:** estimate person-days to respond
5. **Deadline feasibility:** can a competitive bid be prepared in time?

## Output Format
```markdown
## Tender: [Title]
- Source: [KÉ / TED / palyazat.gov.hu]
- Reference: [tender number]
- Contracting Authority: [name]
- Estimated Value: [HUF / EUR]
- Submission Deadline: [date]
- CPV Codes: [list]
- Fit Score: [1-5] | Win Probability: [%] | Deadline Feasible: [Y/N]
- Summary: [2 sentences on scope]
- Go/No-Go recommendation: GO / WATCH / SKIP
- Reason: [1 sentence]
```

## Quality Criteria
- Scan covers minimum 2 sources per search
- All deadlines verified against official source (not aggregator)
- Go/No-Go includes explicit win probability reasoning
- Results delivered within scope/deadline ordered by priority
