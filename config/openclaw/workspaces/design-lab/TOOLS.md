# design-lab — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| read | Design referenciak, brand guide, meglevo CSS | Korlatlan |
| write | Wireframe spec, design token, CSS | Csak workspace-en belul |
| browser | Design inspiracio, component library, font | Csak olvasas |

## TILTOTT eszkozok
- bash: NEM engedelyezett
- exec: NEM engedelyezett
- edit: NEM engedelyezett (write-ot hasznal)

## Output formatum
- Wireframe: strukturalt Markdown + meretekkel, racsrendszerrel
- Szinrendszer: HEX + HSL ertekekkel, hasznalati kontextussal
- Tipografia: font-family, meretskala (rem), line-height, weight
- Spacing: 4px/8px grid rendszer
- Komponens spec: nev, allapotok (default, hover, active, disabled), meretek

## Browser hasznalat
- Dizajn referenciak keresese
- Font es ikon keszletek bongeszese
- Versenytars oldalak vizualis elemzese
- Komponens konyvtarak (shadcn, Radix, Headless UI)

## Sub-agent tool oroklodes
Minden sub-agent: read, write, browser (azonos korlatokkal)
