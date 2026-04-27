/**
 * Onboarding tour + hint bubble strings — locale-aware lookup.
 *
 * Namespaces:
 *   tour.* — wizard steps (welcome, apikey, firsttask, brian, done)
 *   hint.* — contextual help bubbles (cmdk, brian, killswitch, etc.)
 *
 * 7 locales: en (default), hu, de, fr, es, it, pt.
 * Missing key in non-EN → falls back to EN with no console warn.
 */

export type OnboardingLocale =
  | "en"
  | "hu"
  | "de"
  | "fr"
  | "es"
  | "it"
  | "pt";

type OnboardingStrings = Record<string, string>;

const en: OnboardingStrings = {
  // ── Wizard ──────────────────────────────────────────────
  "tour.welcome.title": "Audit-ready AI agents in 5 minutes",
  "tour.welcome.subtitle":
    "OCCP governs every autonomous action: verified pipelines, policy gates, immutable audit trails. This tour takes under 5 minutes.",
  "tour.welcome.cta_primary": "Start",
  "tour.welcome.cta_skip": "Skip tour",
  "tour.welcome.persona_label": "Who are you?",
  "tour.welcome.persona_compliance": "Compliance Officer",
  "tour.welcome.persona_engineer": "Platform Engineer",
  "tour.welcome.persona_operator": "Operator",

  "tour.apikey.title": "Your API key — copy it now",
  "tour.apikey.subtitle":
    "This key authenticates the CLI and SDK. It is displayed only once. Store it in your .env file.",
  "tour.apikey.cta_primary": "I've copied it",
  "tour.apikey.cta_back": "Back",
  "tour.apikey.reveal_label": "Reveal",
  "tour.apikey.copy_label": "Copy",
  "tour.apikey.copy_success": "Copied!",

  "tour.firsttask.title": "Run your first verified task",
  "tour.firsttask.subtitle_compliance":
    "We'll run a safe echo task so you can see the audit row it generates. No production impact.",
  "tour.firsttask.subtitle_engineer":
    "Dispatch echo hello via the Verified Autonomy Pipeline. Watch the audit row appear in real time.",
  "tour.firsttask.cta_run": "Run",
  "tour.firsttask.cta_primary": "Next",
  "tour.firsttask.run_success": "Audit row created:",

  "tour.brian.title": "Meet Brian — your AI copilot",
  "tour.brian.subtitle":
    "Brian has full context about every pipeline run and audit entry. Press ⌘J to open it on any page.",
  "tour.brian.cta_open": "Open Brian drawer",
  "tour.brian.cta_primary": "Next",

  "tour.done.title": "You're compliance-ready.",
  "tour.done.subtitle":
    "Your first audit row is recorded. Here's where to go next.",
  "tour.done.cta_primary": "Close",
  "tour.done.restart": "Restart tour",
  "tour.done.next_pipeline": "Connect a real task",
  "tour.done.next_policy": "Write your first policy rule",
  "tour.done.next_mcp": "Add an MCP server",
  "tour.done.next_team": "Invite your team",

  "tour.common.next": "Next",
  "tour.common.back": "Back",
  "tour.common.dismiss": "Dismiss",
  "tour.common.step_label": "Step",
  "tour.common.of": "of",

  // ── Hint bubbles ────────────────────────────────────────
  "hint.cmdk.title": "Navigate instantly",
  "hint.cmdk.body":
    "Press ⌘K anywhere to open the command palette and jump to any route without touching the nav.",
  "hint.brian.title": "Context-aware AI help",
  "hint.brian.body":
    "Press ⌘J to open Brian. It reads your current pipeline state, audit log, and agent roster.",
  "hint.killswitch.title": "Emergency stop",
  "hint.killswitch.body":
    "Halts ALL agents instantly, mid-task. An audit row is written automatically. Use only during a compliance incident.",
  "hint.newtask.title": "Start a governance-checked run",
  "hint.newtask.body":
    "Every task passes through the Policy Gate before execution. Rejections are logged to the audit trail.",
  "hint.auditrow.title": "Tamper-proof record",
  "hint.auditrow.body":
    "Every row is SHA-256 hash-chained to the previous entry. Click a row to inspect the chain proof.",
  "hint.mcpconnect.title": "Expand your agent's toolbelt",
  "hint.mcpconnect.body":
    "Connect Slack, GitHub, or Supabase as MCP servers. Agents call these tools under full policy control.",
  "hint.restarttour.title": "Getting started again",
  "hint.restarttour.body":
    "Re-runs the 5-step guided onboarding from the beginning. Useful after onboarding a new team member.",
  "hint.costspend.title": "Live token spend",
  "hint.costspend.body":
    "Refreshes every 30 seconds via SSE. Click this card to drill into per-agent cost breakdowns.",

  "hint.common.got_it": "Got it",
  "hint.common.dismiss_all": "Don't show hints anymore",
  "hint.common.dismiss_label": "Dismiss hint",

  // ── Settings → Help ─────────────────────────────────────
  "settings.help.title": "Help & onboarding",
  "settings.help.subtitle":
    "Restart the guided tour or reset all hint bubbles you've dismissed.",
  "settings.help.restart_title": "Restart guided tour",
  "settings.help.restart_body": "Re-run the 5-step setup walkthrough.",
  "settings.help.restart_cta": "Restart",
  "settings.help.reset_hints_title": "Show all hint bubbles again",
  "settings.help.reset_hints_body":
    "Resets all dismissed in-context hints across the dashboard.",
  "settings.help.reset_hints_cta": "Reset hints",
  "settings.help.toggle_title": "Show hints for new features",
  "settings.help.toggle_body":
    "Display help bubbles when you encounter a feature for the first time.",

  // ── Empty states (v2 lists) ─────────────────────────────
  "empty.pipeline.title": "No pipeline runs yet",
  "empty.pipeline.body":
    "Kick off your first Verified Autonomy task. Every run is policy-gated and audit-logged.",
  "empty.pipeline.cta": "Run your first task",
  "empty.agents.title": "No agents registered",
  "empty.agents.body":
    "Register an agent to start dispatching governed tasks. Each agent has its own tool policy.",
  "empty.agents.cta": "Register an agent",
  "empty.audit.title": "No audit entries yet",
  "empty.audit.body":
    "Audit rows appear as soon as your first pipeline task runs. They are immutable and hash-chained.",
  "empty.audit.cta": "Go to Pipeline",
  "empty.mcp.title": "No MCP servers connected",
  "empty.mcp.body":
    "Connect an MCP server to give your agents verified tool access to Slack, GitHub, and more.",
  "empty.mcp.cta": "Connect a server",
};

const hu: OnboardingStrings = {
  "tour.welcome.title": "Auditálható AI-ügynökök 5 perc alatt",
  "tour.welcome.subtitle":
    "Az OCCP minden autonóm műveletet felügyel: ellenőrzött pipeline-ok, policy-kapuk, megváltoztathatatlan audit-naplók. Ez a bemutató 5 percnél rövidebb.",
  "tour.welcome.cta_primary": "Kezdjük",
  "tour.welcome.cta_skip": "Kihagyom",
  "tour.welcome.persona_label": "Mi a szerepköröd?",
  "tour.welcome.persona_compliance": "Compliance-felelős",
  "tour.welcome.persona_engineer": "Platform-mérnök",
  "tour.welcome.persona_operator": "Operátor",

  "tour.apikey.title": "Az API-kulcsod — másold most",
  "tour.apikey.subtitle":
    "Ez a kulcs azonosítja a CLI-t és az SDK-t. Csak egyszer jelenik meg. Mentsd el a .env fájlodba.",
  "tour.apikey.cta_primary": "Másoltam",
  "tour.apikey.cta_back": "Vissza",
  "tour.apikey.reveal_label": "Mutatás",
  "tour.apikey.copy_label": "Másolás",
  "tour.apikey.copy_success": "Másolva!",

  "tour.firsttask.title": "Futtasd az első ellenőrzött feladatot",
  "tour.firsttask.subtitle_compliance":
    "Egy biztonságos echo-feladatot futtatunk, hogy lásd a keletkező audit-sort. Nincs éles hatás.",
  "tour.firsttask.subtitle_engineer":
    "Indíts el egy echo hello feladatot a Verified Autonomy Pipeline-on. Nézd, ahogy az audit-sor megjelenik.",
  "tour.firsttask.cta_run": "Futtatás",
  "tour.firsttask.cta_primary": "Tovább",
  "tour.firsttask.run_success": "Audit-sor létrehozva:",

  "tour.brian.title": "Ismerd meg Briant — az AI-kopilótádat",
  "tour.brian.subtitle":
    "Brian minden pipeline-futásról és audit-sorról tudással rendelkezik. Nyomd meg a ⌘J kombinációt bármelyik oldalon.",
  "tour.brian.cta_open": "Brian-panel megnyitása",
  "tour.brian.cta_primary": "Tovább",

  "tour.done.title": "Készen állsz a compliance-re.",
  "tour.done.subtitle":
    "Az első audit-sorod rögzítve van. Íme, merre mehetsz tovább.",
  "tour.done.cta_primary": "Bezárás",
  "tour.done.restart": "Bemutató újraindítása",
  "tour.done.next_pipeline": "Éles feladat csatlakoztatása",
  "tour.done.next_policy": "Első policy-szabály megírása",
  "tour.done.next_mcp": "MCP-szerver hozzáadása",
  "tour.done.next_team": "Csapat meghívása",

  "tour.common.next": "Tovább",
  "tour.common.back": "Vissza",
  "tour.common.dismiss": "Bezárás",
  "tour.common.step_label": "Lépés",
  "tour.common.of": "/",

  "hint.cmdk.title": "Azonnali navigáció",
  "hint.cmdk.body":
    "Nyomd meg a ⌘K-t bárhol a parancspaletta megnyitásához — navigálj anélkül, hogy a menühöz nyúlnál.",
  "hint.brian.title": "Kontextusérzékeny AI-segítség",
  "hint.brian.body":
    "Nyomd meg a ⌘J-t Brian megnyitásához. Ismeri az aktuális pipeline-t, az audit-naplót és az ügynöklista állapotát.",
  "hint.killswitch.title": "Vészleállítás",
  "hint.killswitch.body":
    "AZONNAL leállít minden ügynököt, akár futás közben is. Automatikusan audit-sort ír. Csak compliance-incidens esetén használd.",
  "hint.newtask.title": "Irányítás-ellenőrzött futás indítása",
  "hint.newtask.body":
    "Minden feladat átmegy a Policy-kapun futtatás előtt. Az elutasítások bekerülnek az audit-naplóba.",
  "hint.auditrow.title": "Hamisításbiztos napló",
  "hint.auditrow.body":
    "Minden sor SHA-256 hash-lánccal kapcsolódik az előzőhöz. Kattints egy sorra a lánc ellenőrzéséhez.",
  "hint.mcpconnect.title": "Bővítsd az ügynök eszköztárát",
  "hint.mcpconnect.body":
    "Csatlakoztass Slack, GitHub vagy Supabase MCP-szervereket. Az ügynökök teljes policy-ellenőrzés alatt hívhatják ezeket.",
  "hint.restarttour.title": "Újrakezdés",
  "hint.restarttour.body":
    "Újraindítja az 5 lépéses bemutatót az elejétől. Hasznos új csapattag bevezetésekor.",
  "hint.costspend.title": "Valós idejű token-felhasználás",
  "hint.costspend.body":
    "30 másodpercenként frissül SSE-n keresztül. Kattints a kártyára az ügynökönkénti bontáshoz.",

  "hint.common.got_it": "Értem",
  "hint.common.dismiss_all": "Ne mutass többé tippeket",
  "hint.common.dismiss_label": "Tipp bezárása",

  "settings.help.title": "Súgó és bemutató",
  "settings.help.subtitle":
    "Indítsd újra a vezetett bemutatót vagy állítsd vissza az elrejtett tippeket.",
  "settings.help.restart_title": "Vezetett bemutató újraindítása",
  "settings.help.restart_body": "Újrafutásra kerül az 5 lépéses telepítés.",
  "settings.help.restart_cta": "Újraindítás",
  "settings.help.reset_hints_title": "Tippek újra megjelenítése",
  "settings.help.reset_hints_body":
    "Visszaállítja az összes elrejtett kontextusos tippet a felületen.",
  "settings.help.reset_hints_cta": "Visszaállítás",
  "settings.help.toggle_title": "Tippek új funkciókhoz",
  "settings.help.toggle_body":
    "Tippek megjelenítése, amikor először találkozol egy funkcióval.",

  "empty.pipeline.title": "Még nincs pipeline-futás",
  "empty.pipeline.body":
    "Indítsd el az első Verified Autonomy feladatot. Minden futás policy-ellenőrzött és audit-naplózott.",
  "empty.pipeline.cta": "Első feladat futtatása",
  "empty.agents.title": "Nincs regisztrált ügynök",
  "empty.agents.body":
    "Regisztrálj egy ügynököt a felügyelt feladatokhoz. Minden ügynöknek saját eszköz-policy-je van.",
  "empty.agents.cta": "Ügynök regisztrálása",
  "empty.audit.title": "Még nincs audit-bejegyzés",
  "empty.audit.body":
    "Az audit-sorok megjelennek, amint az első pipeline lefut. Megváltoztathatatlanok és hash-láncoltak.",
  "empty.audit.cta": "Pipeline megnyitása",
  "empty.mcp.title": "Nincs csatlakoztatott MCP-szerver",
  "empty.mcp.body":
    "Csatlakoztass egy MCP-szervert, hogy az ügynökeid eszközöket használhassanak (Slack, GitHub stb.).",
  "empty.mcp.cta": "Szerver csatlakoztatása",
};

// Stub locales — fallback to EN. Replace with native translations in iter-12.
const stubFromEn = (): OnboardingStrings => ({ ...en });
const de = stubFromEn();
const fr = stubFromEn();
const es = stubFromEn();
const it = stubFromEn();
const pt = stubFromEn();

const TABLES: Record<OnboardingLocale, OnboardingStrings> = {
  en,
  hu,
  de,
  fr,
  es,
  it,
  pt,
};

export function tOnboarding(
  locale: OnboardingLocale,
  key: string,
  fallback?: string,
): string {
  return TABLES[locale]?.[key] ?? en[key] ?? fallback ?? key;
}

export function getOnboardingStrings(
  locale: OnboardingLocale,
): OnboardingStrings {
  return TABLES[locale] ?? en;
}
