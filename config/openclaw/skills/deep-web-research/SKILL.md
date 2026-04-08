---
name: deep-web-research
description: Conduct multi-source deep research with citation tracking, bias detection, and structured synthesis
user-invocable: true
---

## Research Protocol

**Minimum sources:** 5 independent sources per major claim
**Source hierarchy (descending reliability):**
1. Peer-reviewed research / official statistical bodies (KSH, Eurostat, government)
2. Industry analyst reports (Gartner, Forrester, IDC)
3. Primary company data (annual reports, official press releases)
4. Quality journalism (Reuters, FT, HVG, portfolio.hu for HU)
5. Expert commentary (named, verified credentials)

## Research Steps
1. **Query formulation:** 3-5 search queries in both Hungarian and English
2. **Source discovery:** parallel search via multiple engines/databases
3. **Source verification:** check publication date, author credentials, conflict of interest
4. **Data extraction:** pull specific claims with exact quotes and URLs
5. **Cross-validation:** verify key facts across 2+ independent sources
6. **Bias detection:** identify if sources have financial, political, or commercial bias
7. **Synthesis:** structure findings by theme, not by source

## Bias Detection Flags
- Single-source claims → flag as UNVERIFIED
- Industry association data → flag as POTENTIALLY BIASED (self-serving)
- Undated content → flag as STALE RISK
- Contradictory findings between sources → present both, note discrepancy

## Output Format
```markdown
## [Research Topic]

### Key Findings
1. [Finding] — Source: [Name, Date, URL]
2. [Finding] — Source: [Name, Date, URL]

### Data Points
| Metric | Value | Source | Date |
|--------|-------|--------|------|

### Conflicting Evidence
[Describe discrepancy and both sources]

### Confidence Assessment
HIGH / MEDIUM / LOW — reason: [X sources corroborate, Y unverified]

### Sources
[Numbered reference list with full citations]
```

## Quality Criteria
- No claim without citation
- All sources accessed and verified (not just search result snippets)
- Hungarian market data uses Hungarian sources where available
- Research date logged — findings valid for 90 days maximum before refresh
