## Nytt

**2.3.2 — Strömstad var tomt sett fra Oslo**

Stedsfilteret i `_les_kalender` var en ren delstrengsjekk:

```python
if self.sted and self.sted.lower() not in tittel.lower():
    continue
```

Instansen som står i Strömstad skriver «Strömstad – Navn» med ö. Er stedet skrevet
«Strømstad» med ø på en annen instans, finnes ikke strengen i tittelen, og hver eneste
hendelse kastes. Derfor viste stedet tomt sett fra Oslo og riktig sett fra Strömstad, som
sammenlignet navnet med seg selv. «Netter <person>: Utilgjengelig» kom av det samme: uten
posisjonsbrytere hentes personene fra hendelsene, og uten hendelser finnes ingen personer.

Steds- og personnavn sammenlignes nå på en normalisert nøkkel: små bokstaver, uten
skilletegn, og med ø/ö, æ/ä/å og aksenter slått sammen. «Strömstad» og «Strømstad» er
samme sted; «Toten» treffer fortsatt ikke Strömstad.

Samtidig tåler «Sted – Navn» nå tankestrek, bindestrek og kolon. Før ga en tittel med
vanlig bindestrek hele tittelen som personnavn.


**2.3.1 — «0 netter» hjemme**

`netter()` og `besok()` talte på oppholdets **startår**:

```python
sum(o.netter for o in self.opphold if o.start.year == aar and ...)
```

Hjemmeoppholdene er ikke kalenderhendelser, men sammenhengende blokker som
`_hjemmeopphold()` bygger av dagene ingen hytte dekker — over hele historikkvinduet, som
står på 400 dager. Blokka starter derfor i fjor, `start.year` er 2025, og hele blokka
falt ut av 2026-tellingen. Hvem som er hjemme kommer fra posisjonsbryterne og var riktig
hele tiden; det var bare nettene som forsvant.

Nettene telles nå på datoen til hver enkelt natt. Et opphold over nyttår fordeles på de
to årene, og teller som et besøk i begge.

Samtidig: hjemmeoppholdene regnes på nytt så snart en hytte har lest kalenderen sin.
Leste hjemstedet først ved oppstart, så det ingen hytteopphold og regnet hele vinduet som
ett opphold hjemme — og det ble stående til hjemstedet selv leste på nytt et kvarter
senere. Har hjemstedet egne hendelser i kalenderen, røres de ikke.

**2.3.0**
- `icons.json`: entitetene og tjenestene har fått faste ikoner – kalender, måne, historikk, person og kart – så de ser riktige ut overalt uten at du setter dem selv
- «Noen på stedet» bytter ikon mellom hus med person og tomt hus

## Merk om integrasjonsikonet

Logoen ved siden av «KI Hyttebesøk» i HACS kommer fra **brands.home-assistant.io** og krever en pull request dit. Filene ligger klare i `brands-ikoner.zip`.

## Tester

`tests/test_netter.py`: blokk over nyttår teller i begge år, regresjonen som ga null, og
vanlige hytteopphold teller som før.
