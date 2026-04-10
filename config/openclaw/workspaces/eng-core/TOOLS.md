# eng-core — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| bash | git, npm, pip, pytest, docker build | Nem torolhet prod adatot |
| read | Forrasfajlok, logok, config olvasasa | Korlatlan |
| write | Uj fajlok letrehozasa | Csak workspace-en belul |
| edit | Letezo fajlok modositasa (diff) | Preferal write helyett |
| browser | Dokumentacio, API reference | Csak olvasas |

## Bash korlatozasok
- ENGEDELYEZETT: git, npm, npx, pip, pytest, python, node, docker build, curl (API test)
- TILTOTT: rm -rf, shutdown, reboot, ssh prod szerverre, force push main-re
- Timeout: 120s

## Konvenciok
- Fajl kereses: glob pattern, NEM find
- Tartalom kereses: grep tool, NEM shell grep
- Fajl olvasas: read tool, NEM cat/head/tail
- Fajl iras: write/edit tool, NEM echo/sed

## Sub-agent tool oroklodes
Sub-agentek ugyanazokat a tool-okat kapjak, kivetel:
- qa-test: +exec (teszt futatashoz)
- code-review: -write (csak olvashat, nem irhat)
