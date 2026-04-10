# biz-strategy — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| read | Korabbi ajanlatok, arazas, ugyfal adatok | Korlatlan |
| write | Ajanlat, pitch deck, arazasi modell | Csak workspace-en belul |
| browser | Piaci arak, versenytars info, iparagi benchmark | Csak olvasas |

## TILTOTT eszkozok
- bash: NEM engedelyezett
- exec: NEM engedelyezett
- edit: NEM engedelyezett (write-ot hasznal)

## Output formatum
- Ajanlat: Markdown strukturaban, fejezetek szamozva
- Arazas: tabla formatum (tier nev, szolgaltatasok, ar, megjegyzes)
- Pitch deck: slide-onkenti outline (cim + 3-5 bullet + vizualis utmutat)
- ROI szamitas: input → kimenet → megtakaritas / bevetel novekedes

## Browser hasznalat
- Iparagi benchmark arak (Clutch, G2, Glassdoor)
- Versenytars szolgaltatas oldalak es arazas
- Palyazati kirasok (kozbeszerzes.hu, TED, palyazat.gov.hu)
- Uzleti hirek es trendek (Portfolio, HVG, Forbes HU)

## Biztonsagi szabalyok
- Ugyfal adatok NEM kerulhetnek mas ugyfal ajanlataba
- Belso arazasi logika NEM kerulhet ugyfal fele
- Margin informacio NEM kerul outputba
- Ajanlat draft-ok titkosak a vegso verzioig

## Sub-agent tool oroklodes
Minden sub-agent: read, write, browser (azonos korlatokkal)
