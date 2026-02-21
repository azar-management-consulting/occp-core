# Claude Code – parancssorozat az OCCP projekt létrehozásához

Ez a forgatókönyv lépésről lépésre leírja, hogyan használd a **Claude Code** parancssori eszközét (CLI) és MCP‑kiszolgálóit az **OpenCloud Control Plane** (OCCP) projekt generálásához. A parancsok a projekt csontvázára (zip fájl) épülnek, és figyelembe veszik az Azar Management Consulting szerepét. A script kéréseket ad Claude Code-nak, hogy a megfelelő eszközök (Bash, Edit, Read, Search, WebFetch, Git) használatával hajtsa végre a feladatokat. 

> **Megjegyzés:** A szkript olyan utasításokat tartalmaz, amelyeket Claude Code‑nak kell végrehajtania. Ha az agent nem tud egy lépést megoldani, kérjük, használja a `Search` vagy `WebFetch` eszközt (MCP vagy beépített keresés) további információkért ahelyett, hogy hallucinálna. A script magyar nyelven íródott.

## Előkészületek
1. Győződj meg róla, hogy a legfrissebb Claude Code telepítve van a gépeden, és hogy a megfelelő MCP‑kiszolgálók konfigurálva vannak (GitHub, WebFetch stb.). Ha szükséges, ellenőrizd az MCP‑konfigurációt:
   ```bash
   claude mcp list
   ```
2. Helyezd el a korábban létrehozott „occ_project_skeleton.zip” fájlt (projektcsontváz) és a „forgato_scenario.md” állományt a munkakönyvtáradban. Ez utóbbi tartalmazza a projekt részletes specifikációját.

## Parancssorozat
Az alábbi parancsot egyetlen here‑document formájában futtathatod. A `--print` (vagy röviden `-p`) mód használatával Claude Code egyszeri lekérdezést hajt végre és kilép. A `--mcp-config` opcióval betöltjük a saját MCP beállításainkat (ha van külön konfigurációs fájl). A `--permission-mode plan` mód biztonságos, mert előbb tervet készít minden művelethez; így minden lépést jóváhagyhatsz. A `--allowedTools` paraméterrel meghatározhatjuk, hogy a Bash, Edit, Read, Search, WebFetch és Git eszközök prompt nélkül használhatók legyenek.

```bash
claude \
  --mcp-config ~/.claude/mcp.json \
  --strict-mcp-config \
  --permission-mode plan \
  --allowedTools "Bash(*),Edit(*),Read(*),Search(*),WebFetch(*),Git(*)" \
  -p <<'TASKS'
Te egy szenior fejlesztő vagy az Azar Management Consultingnál. Az a feladatod, hogy az OpenCloud Control Plane (OCCP) projektet a rendelkezésre álló projektcsontváz és forgatókönyv alapján felépítsd. Kövesd az alábbi lépéseket. Ha bármely lépésnél információhiányba ütközöl, **használd a `Search` vagy `WebFetch` eszközt** (MCP-n vagy beépített keresőn keresztül) megbízható források megkeresésére, és csak ezután folytasd. **Ne hallucinálj, csak tényekre alapozz!**

1. **Könyvtár és csontváz kibontása:**
   - Bash eszközzel hozz létre egy új könyvtárat `occp` néven.
   - Csomagold ki az `occ_project_skeleton.zip` fájlt ebbe a könyvtárba.
   - Navigálj az új könyvtárba.

2. **Git inicializálás:**
   - Fuss Bash parancsot a `git init` végrehajtására.
   - Állítsd be a projekt alap commitját: add hozzá az összes fájlt, és kövesd el `Initial OCCP skeleton` üzenettel.

3. **Dokumentáció áttekintése és frissítése:**
   - A `Read` eszközzel olvasd el a `README.md` és `docs/QuickStart.md` tartalmát.
   - Nyisd meg a `forgato_scenario.md` fájlt (ez tartalmazza a részletes specifikációt és a végleges forgatókönyvet). Ha valamelyik részlet hiányzik, keresd meg a hiányzó információt a weben.
   - Az `Edit` eszközzel aktualizáld a `README.md` fájlt, hogy tükrözze a projekt nevét (OpenCloud Control Plane), a célkitűzést, valamint az Azar Management Consulting mint fejlesztő szerepét. Használd a `forgato_scenario.md` releváns részeit.
   - Szerkeszd a `docs/QuickStart.md` fájlt, hogy tartalmazzon részletes telepítési és indítási útmutatót (például `unzip`, `docker compose up`, `pip install occp` stb.).

4. **CLAUDE.md előkészítése:**
   - Készíts egy új fájlt `CLAUDE.md` néven a projekt gyökerében az `Edit` eszközzel.
   - Ebben írd le a projekt célját, a moduláris architektúrát (orchestrator, policy engine, dashboard, CLI, SDK-k), a Verified Autonomy Pipeline lépéseit (Plan → Gate → Execute → Validate → Ship) és az open‑core (CE/EE) modell részleteit. Ezt a dokumentumot fogja felhasználni Claude Code a jövőbeni automatikus fejlesztésekhez.

5. **MCP szerverek ellenőrzése:**
   - Ellenőrizd, hogy a GitHub MCP szerver elérhető‑e; ha nem, add hozzá a megfelelő URL-lel (például `claude mcp add --transport http github https://mcp.github.com/mcp`).
   - Hasonlóképpen ellenőrizd a WebFetch vagy más releváns szervereket, amelyekre szükség lehet (például Slack, Notion, PostgreSQL, Sentry stb.).
   - Ha bármelyik kiszolgáló hiányzik, használd a `Search` eszközt, hogy megtaláld a hozzá tartozó MCP URL-t és a hozzáadás pontos módját.

6. **Code generálás:**
   - A `forgato_scenario.md` és a `CLAUDE.md` alapján generálj kódot a hiányzó modulokhoz:
     - Orchestrator: Fővezérlő modul, amely több agentet képes ütemezni és menedzselni.
     - Policy engine: Olyan komponens, amely a külső eszközök használatát engedélyekhez köti, auditnaplókat készít, és támogatja az open‑core vállalati funkciókat.
     - Dashboard: Webes UI modul, amely megjeleníti az agent folyamatokat, feladatok állapotát és a Verified Autonomy Pipeline lépéseit.
     - CLI: Parancssori interfész, amely lehetővé teszi feladatok indítását (például `occp create`, `occp build` stb.).
     - SDK-k: Python és TypeScript klienskönyvtárak a platformhoz való programozott hozzáféréshez.
   - Minden modulhoz készíts mappákat (`orchestrator`, `policy_engine`, `dash`, `cli`, `sdk/python`, `sdk/typescript`) és adj inicializáló fájlokat (például `__init__.py`, `package.json`, `index.ts`, stb.).

7. **Tesztkörnyezet beállítása:**
   - Hozz létre a `tests` mappában példateszteket a policy engine és az orchestrator modulokhoz.
   - Futás: használj Bash parancsot (`pytest` Python kódnál, `npm test` TypeScriptnél), hogy ellenőrizd, minden összeáll.
   - Ha a tesztek hibát jeleznek, javítsd az érintett modulokat az `Edit` eszközzel.

8. **GitHub repó létrehozása és feltöltése:**
   - Ha még nincs GitHub repó a projekt számára, használd a GitHub MCP szervert (vagy a GitHub CLI‑t) egy új repository létrehozásához az `opencloud-controlplane/occp-core` névvel.
   - Hozz létre `occp-ee` nevű privát repót a vállalati funkciók számára.
   - Állítsd be a `CODEOWNERS`, `CONTRIBUTING.md` és `CODE_OF_CONDUCT.md` fájlokat a `.github` mappában. Szükség esetén használd a `Search` eszközt a legjobb gyakorlatok kereséséhez.
   - Add hozzá a CI/CD konfigurációt (például GitHub Actions), hogy automatikus tesztek fussanak push és PR eseményekre.
   - Pushold a módosításokat az új repókba (`git remote add origin` és `git push -u origin main`).

9. **Záró lépések:**
   - Készíts egy részletes `CHANGELOG.md` fájlt, amely dokumentálja az eddigi lépéseket és verziókat.
   - Generálj egy `LICENSE` fájlt (például Apache‑2.0) a projekt gyökerébe.
   - Hozz létre Issue sablonokat és PR sablonokat a `.github` könyvtárban.
   - Ellenőrizd, hogy minden fájl be van commitálva és a projekt futtatható (például `pip install -e .` működik, `npm install && npm run build` működik).

Kimenetként szeretném megkapni a teljes végrehajtási tervet (Plan) és az automatikusan generált kódokat. Ha további információra van szükséged bármely lépéshez, jelezd a tervben, hogy elvégzel egy webes keresést és csak utána folytatod a végrehajtást.

TASKS
