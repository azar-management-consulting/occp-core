# intel-research — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| read | Kutatasi anyagok, korabbi jelentesek, adatfajlok | READ-ONLY workspace |
| browser | Web kutatas, forras ellenorzes, adat gyujtes | Fo eszkoz |
| exec | Adat feldolgozas (Python, jq, csvkit) | Csak adat transform |

## TILTOTT eszkozok
- write: NEM engedelyezett (read-only workspace)
- edit: NEM engedelyezett
- bash: NEM engedelyezett (exec-et hasznal adatfeldolgozasra)

## Exec korlatozasok
- ENGEDELYEZETT: python (pandas, numpy, json), jq, csvkit, sqlite3 query
- TILTOTT: halozati parancsok (curl, wget — browser-t hasznal helyette), fajl modositas
- Timeout: 300s (hosszabb adatfeldolgozashoz)

## Browser hasznalat — fo eszkoz
- Piackutatasi adatbazisok es jelentesek
- Versenytars weboldalak es pricing oldalak
- Technologiai hirek, blog-ok, GitHub trending
- Kozbeszerzesi portalok (TED, kozbeszerzes.hu)
- Akademiai forrasok (Google Scholar, arXiv)
- Allami nyilvantartasok (cegjegyzek, NAV)

## Output szallitas
Mivel a workspace read-only, az output a session valaszban kerul atadasa.
Brain vagy mas agent menti el a vegso dokumentumot.

## Sub-agent tool oroklodes
- market-research: read, browser (nincs exec)
- competitor-scan: read, browser (nincs exec)
- tech-radar: read, browser, exec
- fact-check: read, browser (nincs exec)
- procurement-scan: read, browser (nincs exec)
