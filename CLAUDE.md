# CLAUDE.md – OCCP fejlesztési szabvány (Azar Management Consulting)

## Küldetés
Építsd fel az **OpenCloud Control Plane (OCCP)** platformot: felhasználóbarát, gyorsan indítható,
auditálható és policy-vezérelt Agent Control Plane rendszert.

## Nem alkuképes elvek
1. **Plan-first**: minden nagyobb változtatás előtt készíts tervet (Plan), majd csak jóváhagyás után módosíts.
2. **No hallucination**: ha bizonytalan vagy, *kutass* (Search/WebFetch) és hivatkozz megbízható forrásokra.
3. **Least privilege**: a tool-hívások és jogosultságok legyenek minimálisak.
4. **Evidence-driven**: minden futás végén legyen bizonyíték: diff, teszt eredmény, log, hash.
5. **Open-core**: a CE nyílt, az EE külön repó és külön licenc.

## Architektúra
- orchestrator: workflow & ügynök ütemezés (Verified Autonomy Pipeline)
- policy_engine: policy-as-code, audit log, PII/injection guard (CE-ben alap; EE-ben advanced)
- dash: dashboard + mission control (CE-ben alap; EE-ben enterprise)
- cli: `occp` parancsok (start, run, status, export)
- sdk: python + typescript kliens

## Verified Autonomy Pipeline
1. **Plan** – feladat terv + kockázati besorolás
2. **Gate** – policy engine ellenőrzés + szükséges jóváhagyások
3. **Execute** – sandbox futtatás
4. **Validate** – tesztek, statikus ellenőrzések, diff review
5. **Ship** – PR, release, deploy (később)

## Repo szabályok
- Minden commit: kicsi, értelmezhető.
- PR-hez: leírás + tesztek + evidence.
- CODEOWNERS által védett modulok: orchestrator, policy_engine.

## Fejlesztési parancsok (helyi)
- Python: `pytest -q`
- Node: `npm test` (ha a dash felépült)

## Ha hiányzik információ
- Használd a `Search` vagy `WebFetch` eszközt.
- Ne találj ki MCP URL-t vagy CLI kapcsolót: ellenőrizd.
