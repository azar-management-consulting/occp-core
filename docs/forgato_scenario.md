# Forgatókönyv az OpenCloud Control Plane (OCCP) projekt jövőbemutató megvalósításához

## Háttér és célkitűzés
Az OCCP (OpenCloud Control Plane) célja, hogy a fejlesztők és vállalati csapatok számára olyan **felhasználóbarát, gyorsan beállítható, nyílt forrású** platformot biztosítson, amelyen többféle AI‑ügynök (pl. Claude Code, OpenCode, Bedrock, OpenAI Agentek) kezelhető, auditálható és irányítható. A megoldást az Azar Management Consulting fejleszti, **open‑core** licenc‑stratégiával (közösségi és vállalati kiadás). A forgatókönyv összeállításához mély kutatást végeztünk a GitHubon és szakmai fórumokon, hogy feltérképezzük a legnépszerűbb, legjobb gyakorlatokat nyújtó agent‑control‑plane és multi‑agent keretrendszereket.

## Kulcsmegállapítások a mély kutatásból

* **GitHub Enterprise Control Plane** – a GitHub 2025. októberi bejelentése szerint az "AI Controls" egy központi felületen ad átlátható, auditálható adminisztrációt: egyetlen nézetben menedzselhető a teljes ügynökflotta, a vállalati házirendek, a session‑aktivitások és auditnaplók【465824439025146†L46-L68】. Ez a vállalati használathoz nélkülözhetetlen funkciókat ad: testre szabható ügynökök, 24 órás session‑lista, részletes naplózás és finomhangolt jogosultságkezelés【465824439025146†L69-L117】.

* **Sandboxed.sh (korábban OpenAgent)** – a Th0rgal projektje (kb. 247 csillag) self‑hostolt orchestrátort kínál. **Előnyei:** izolált munkakörnyezetek (systemd‑nspawn), Git‑alapú "Library" a skillekhez, többszörös ügynök runtime (Claude Code, OpenCode, Amp) és könnyű telepítés Dockerrel: `git clone`, `.env` létrehozás, `docker compose up` és már fut a dashboard【605574603414891†L435-L459】. A telepítés ~5 perc, a felhasználónak csak a helyi böngészőt kell megnyitnia【605574603414891†L435-L459】.

* **Agent Control Plane (ACP)** – Kubernetes‑alapú ügynökütemező, amely hosszú életű, felügyelet nélküli ügynököket támogat. Fő értékei a **személyesség, egyszerűség, megbízhatóság** és a skálázható architektúra【657208564995335†L6-L14】. Core fogalmak: LLM, Agent, Tools, Task, ToolCall【657208564995335†L54-L66】. Az elindításhoz szükséges `kubectl`, `kind` és Docker, ami magasabb technikai szintet igényel; a projekt még alpha állapotú.

* **AgentField** – "Kubernetes for AI agents", mely mikro‑szolgáltatásként kezeli az ügynököket. Skálázható infrastruktúrát biztosít (útvonalválasztás, aszinkron végrehajtás, tartós állapot, megfigyelhetőség) és beépített bizalmi réteget (W3C DID identitások, hitelesíthető credential‑ök, policy enforcement)【752570199572417†L52-L70】. Több nyelvhez (Python/Go/TS) nyújt SDK‑t.

* **AxonFlow** – BSL 1.1 alatt kiadott AI control plane, amely a governance‑re és a workflow‑kontrollra fókuszál. Real‑time policy enforcementet, PII‑detekciót, auditálhatóságot és többmodelles routingot kínál. Gyors indítás Docker Compose‑szel (`git clone`, `.env` beállítása, `docker compose up`)【774231033996231†L340-L440】.

* **Agent Squad** (AWS Labs) – többszörös ügynök orchestrátort ad, TypeScript és Python implementációval. Fő funkciói: **multi‑agent orchestration, intelligens intent‑osztályozás, kontextuskezelés, streaming támogatás**. A dokumentáció kiemeli, hogy az ügynökök könnyen telepíthetők `npm install agent-squad` vagy `pip install agent-squad[aws]` paranccsal, és moduláris architektúrával rendelkezik【262783927927458†L27-L42】. A gyors indítás külön "Quick Start Guide"‑ot tartalmaz, amely lépésről lépésre bemutatja az első multi‑agent beszélgetés beállítását【907300612156500†L116-L161】.

* **ChatDev (OpenBMB)** – multi‑agent platform szerep‑alapú szoftverfejlesztéshez (product manager, developer, tester). A 2.0‑ás verzió telepítéséhez Python/Node környezet szükséges; `uv sync` telepíti a backend függőségeit, a frontendet `npm install`, és `make dev` indítja mindkét komponenst【794959649293653†L523-L564】. A projekt webes konzolt kínál vizuális drag‑and‑drop workflow‑val és YAML‑alapú sablonokat különböző use case‑ekre【794959649293653†L620-L674】.

* **Open Interpreter** – AGPL‑licencű eszköz, amely a helyi gépen futtatja a kódot. Telepítése egyszerű: `pip install git+https://github.com/OpenInterpreter/open-interpreter.git` után a `interpreter` parancs indítja a terminálos chatet【642076730547792†L330-L343】. Teljes internet‑hozzáférés és bővíthető modellválasztás (LLM‑ek cseréje)【642076730547792†L374-L380】. Emeli, hogy a ChatGPT Code Interpreter korlátait megszünteti, mivel idő- és memóriakorlát nélkül, helyben fut【642076730547792†L360-L380】.

* **OpenClaw** – (milvus blog) kiemeli, hogy a projekt lokális, multi‑csatornás gateway‑t biztosít, több ügynökkel kommunikál és a memóriát Markdown/YAML fájlokban tárolja; 2024‑ben villámgyorsan 100 000 csillagot szerzett, ami bizonyítja a felhasználói igényt【505318971086374†L81-L142】. Szintén fontos a "prompt injection" elleni védelmi figyelmeztetés.

* **Agentek Top 10 listája** – az "Awesome AI Agents" listából kiderül, hogy a legnépszerűbb projektek (AutoGPT, Ollama, LangChain, Lobe Chat, OpenDevin, MetaGPT, stb.) elsősorban könnyű telepítési élményt és moduláris, bővíthető architektúrát kínálnak【694949520928129†L298-L344】.

## A felhasználóbarát, gyors indulást biztosító jó gyakorlatok

1. **"Egy perc alatt működésbe lép" telepítés** – A legsikeresebb projektek (sandboxed.sh, AxonFlow, Open Interpreter) mind pár parancsos telepítést kínálnak: `git clone` vagy `pip install`, `.env` létrehozása, majd `docker compose up` vagy `interpreter` futtatása【605574603414891†L435-L459】【774231033996231†L340-L440】【642076730547792†L330-L343】. Az OCCP‑t is ehhez kell igazítani: egyértelmű `README.md`‑t és "Gyorsindítás" szekciót készíteni.

2. **Kód‑alapú és vizuális interfész** – ChatDev és Agent Squad vizuális webkonzolt kínál, de emellett API‑t és SDK‑t is, így a felhasználók kódon keresztül automatizálhatják a folyamataikat【794959649293653†L620-L674】【907300612156500†L116-L161】. Az OCCP‑hez is érdemes webes dashboardot (pipeline tervező) + CLI/SDK‑t biztosítani.

3. **Moduláris, többnyelvű SDK** – Az Agent Squad Python/TypeScript verziót ad, AgentField Python/Go/TS SDK‑val rendelkezik, Open Interpreter Python könyvtáron keresztül is elérhető【752570199572417†L52-L70】【262783927927458†L27-L42】. Az OCCP‑nél javasolt Python + TypeScript kliens.

4. **Policy‑ és audit‑réteg** – GitHub Agent Control Plane auditnaplója és AxonFlow real‑time policy enforcemente mutatja, hogy a vállalati bizalom kulcsa a részletes naplózás, PII‑védelem és finomhangolt jogosultságkezelés【465824439025146†L69-L117】【774231033996231†L340-L440】. Az OCCP‑nek beépített policy engine‑nel és tamper‑evidens auditnaplóval kell rendelkeznie.

5. **Open‑core modell** – a nyílt mag (Community Edition) biztosítsa a fő workflow‑t, plugin‑keretrendszert, kódgenerálást; a fizetős Enterprise Edition extra funkciókat adjon (SSO, RBAC, compliance, magas rendelkezésre állás). Ez a minta bevált a piacon.

6. **Közösség és dokumentáció** – A sikeres projektek részletes dokumentációt, issue‑sablonokat, hozzájárulási útmutatót és CODEOWNERS szabályokat használnak. Az OCCP‑nél is fontos a jó dokumentáció és közösségépítés (GitHub Pages docs, Discord/Reddit fórum).

## Végleges forgatókönyv (számozott lépések)

1. **Szervezet létrehozása és branding** – Hozzuk létre az `opencloud-controlplane` GitHub‑szervezetet az Azar Management Consulting nevében. Ebbe kerülnek a nyílt (`occp-core`) és zárt (`occp-ee`) repository‑k. Alap licence: MIT/BSD a core‑hoz, vállalati modulhoz kereskedelmi licenc.

2. **Repository struktúra** – Monorepóban (`occp-core`) hozzuk létre a következő modulokat:
   - `orchestrator/` – a Verified Autonomy Pipeline vezérlője (Plan → Gate → Execute → Validate → Ship)
   - `policy_engine/` – szabálymotor (YAML/JSON policy‑k); integráció a GitHub push rules‑szal
   - `dash/` – webes felület (React/Tailwind) grafikus pipeline‑tervezővel
   - `cli/` – parancssoros eszköz (`pip install occp`) a gyors indításhoz
   - `sdk/python/` és `sdk/typescript/` – klienskönyvtárak
   - `docs/` – teljes dokumentáció és quick‑start útmutatók
   - `.github/` – issue/pr sablonok, `CODEOWNERS`, `CONTRIBUTING.md`

3. **Gyors telepítés biztosítása** – Készítsünk "Quick Start" részleget a README‑ben, mely a sandboxed.sh és AxonFlow mintájára pár parancsban elindítja a rendszert:
   - `git clone https://github.com/opencloud-controlplane/occp-core.git`
   - `cp .env.example .env` és kitöltés
   - `docker compose up -d` vagy `pip install occp && occp start`
   - `http://localhost:3000` megnyitása a webkonzolhoz.  
  Ugyanitt rövid CLI‑példa, pl. `occp run --workflow hello_world.json`.

4. **Több ügynök támogatása** – Az "Ecosystem" szekcióhoz hasonlóan adjunk hivatalos adaptereket: Claude Code, OpenCode, Amp, AWS Bedrock, OpenAI. Minden adapter moduláris plugin, ami a könyvtár `plugins/` mappájába kerül.

5. **Policy‑ és audit rendszer** – Implementáljuk a policy engine‑t, amely minden eszközhívást ellenőriz: engedélyezett parancsok, kockázati szint, erőforrás‑korlátok. Az auditlog tartalmazza a felhasználó/ügynök azonosítóját, a végrehajtott műveletet, időbélyeget, bemeneti és kimeneti hash‑t【465824439025146†L69-L117】.

6. **Vizualizáció és UX** – A webes dashboard legyen drag‑and‑drop pipeline‑szerkesztő (mint ChatDev workflow canvas), valós idejű státuszkijelzéssel és log‑megtekintővel【794959649293653†L620-L674】. A CLI és SDK segítségével a fejlesztők kódból is futtathatnak workflow‑kat.

7. **Open‑core üzleti modell** – Határozzuk meg a Community Edition funkciókat (orchestrator, policy engine, plugin API, dashboard alapfunkciók), és az Enterprise Editionben kínáljuk a kiegészítő szolgáltatásokat (SSO/SCIM, RBAC, multi‑tenant üzemeltetés, compliance export, prémium integrációk). 

8. **Fejlesztési folyamat és hozzájárulás** – Állítsuk be a CODEOWNERS és branch‑védelmi szabályokat; kötelező review + CI pipeline (lint, teszt). Dokumentáljuk a DCO/CLA folyamatot és hozzunk létre issue/pr sablonokat. A projekt működését GitHub Projects segítségével kövessük.

9. **Jövőbeni bővítések** – 
   - **On‑prem és felhő**: biztosítsunk telepítési opciókat helyi szerveren (kubernetes/operator) és felhős szolgáltatásként.  
   - **Modellek közti routing**: implementáljuk a multi‑model routert (AxonFlow mintájára), ami a feladat típusa alapján választ modellt (pl. Claude, Gemini, Llama 3).  
   - **RAG és belső tudás**: integráljunk Retrieval Augmented Generation modult, hogy vállalati dokumentációból tudjon válaszolni.  
   - **Marketplace**: hozzunk létre plugin és policy piacteret (GitHub Registry) a közösségi bővítményekhez.

## Összefoglalás
A fenti forgatókönyv összeállítása során számos népszerű agent‑control‑plane és multi‑agent projektet vizsgáltunk meg. A legjobb gyakorlatokból (gyors telepítés, moduláris architektúra, vizuális + kódos interfészek, erős policy‑ és audit‑réteg, open‑core modell) következő OCCP platform **egyedülállóan ötvözi** a felhasználóbarát megközelítést a vállalati szintű megbízhatósággal. A megfelelő márkaépítéssel, átlátható fejlesztési folyamattal és közösségi támogatással az OCCP a jövő egyik legfelkapottabb AI‑ügynök irányítási platformjává válhat.
