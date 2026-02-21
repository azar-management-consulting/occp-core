# OpenCloud Control Plane (OCCP) – Community Edition (CE)

**Fejlesztő:** Azar Management Consulting  
**Cél:** felhasználóbarát, gyorsan beüzemelhető (1–5 perc), auditálható és bővíthető *Agent Control Plane* platform.

Az OCCP a **Verified Autonomy Pipeline** elvén működik:

**Plan → Gate → Execute → Validate → Ship**

A CE (Community Edition) nyílt forrású magot ad. A vállalati funkciók az **OCCP Enterprise Edition (EE)** csomagban érhetők el (külön, privát repóban).

---

## Gyorsindítás (Docker Compose)

### 1) Klónozás
```bash
git clone <repo-url> occp-core
cd occp-core
```

### 2) Környezeti változók
```bash
cp .env.example .env
# töltsd ki a szükséges API kulcsokat / beállításokat
```

### 3) Indítás
```bash
docker compose up -d
```

### 4) Megnyitás
- Dashboard: `http://localhost:3000`

---

## Gyorsindítás (CLI – hamarosan)

A CLI csomagolás előkészítve van (`cli/`, `sdk/`). A következő milestone-ban:
```bash
pip install occp-cli
occp start
```

---

## Projektstruktúra

- `orchestrator/` – Verified Autonomy Pipeline motor (tervezés, gating, futtatás, validálás, szállítás).
- `policy_engine/` – policy-as-code, audit log, engedélyezés.
- `dash/` – webes kezelőfelület (React/Next.js terv).
- `cli/` – parancssoros eszköz (terv).
- `sdk/python/`, `sdk/typescript/` – kliensek.
- `docs/` – QuickStart + forgatókönyv + Claude Code futtatási parancsok.
- `.github/` – hozzájárulási, issue/PR sablonok, CI.

---

## Dokumentáció
- `docs/QuickStart.md`
- `docs/forgato_scenario.md`
- `docs/claude_code_commands.md`

---

## Közreműködés
Lásd: `.github/CONTRIBUTING.md`  
A kritikus területeket a `.github/CODEOWNERS` védi.

---

## Licenc
A Community Edition (occp-core) **MIT** licenc alatt érhető el. Lásd: `LICENSE`.
