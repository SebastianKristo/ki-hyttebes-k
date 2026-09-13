## Nytt

**2.5.0 — avreiser ble aldri skrevet, og en tur ut nullstilte «Her nå»**

To feil i posisjonsbryter-logikken, og den første forklarer hvorfor kalenderen har vært
så tom:

```python
sist = ny.last_changed or dt_util.utcnow()
if (dt_util.utcnow() - sist).total_seconds() < minutter * 60:
    return
```

`ny.last_changed` er tidspunktet bryteren nettopp slo av. Differansen er derfor alltid
null sekunder, som alltid er mindre enn forsinkelsen — så avreise-grenen returnerte hver
eneste gang, og `skriv_opphold` ble aldri kalt fra en bryter. Bare oppholdene du trykket
inn manuelt med «Lagre pågående opphold» havnet i kalenderen.

Forsinkelsen venter nå faktisk: når bryteren slår av, settes en timer, og etter
forsinkelsen sjekkes bryteren på nytt. Er personen tilbake, fortsetter oppholdet. Er hen
fortsatt borte, skrives oppholdet til kalenderen.

Den andre: `_pa_stedet` leste bryteren rått, så en tur rundt kvartalet slo «Her nå» til
null umiddelbart. Et fravær som er kortere enn forsinkelsen teller nå ikke som avreise,
så lenge personen hadde et pågående opphold.

Samtidig: mangler bryteren på denne instansen, eller er den `unavailable`, spør vi
kalenderen i stedet for å svare «borte». Det gjør at et sted man bare leser oppfører seg
likt uansett om noen har lagt inn en bryter for det eller ikke.


**2.4.1 — «Netter <navn>: Utilgjengelig»**

Personsensorene lages én gang, når plattformene settes opp. Ga den første kalenderlesingen
ingenting — typisk fordi kalenderintegrasjonen ikke var lastet ennå ved oppstart — fantes
det ingen personer på det tidspunktet, og senere lesinger kunne ikke opprette sensorene i
ettertid. De fra forrige kjøring ble stående som utilgjengelige til neste omstart, mens
«Netter i år» og «Siste besøk» fylte seg helt normalt.

* Dukker det opp personer i kalenderen som vi ikke hadde, lastes oppføringen på nytt, én
  gang, så de får sensorer med en gang.
* Gir den første lesingen ingen opphold, eller feiler den, leses kalenderen om igjen når
  Home Assistant melder seg ferdig startet — i stedet for å vente et kvarter.

Oversiktssensoren har fått tre felt til diagnose: `lest_hendelser` (hvor mange hendelser
kalenderen faktisk ga), `titler` (de femten første, rå) og `kjente_personer`. Står et sted
tomt, er det der du ser hvorfor.


**2.4.0 — hjemmenettene vippet mellom to helt ulike tall**

Hjemmenettene ble regnet ut fra fravær — dagene ingen var registrert på en hytte — men
bare når kalenderen ikke hadde en eneste hendelse for stedet:

```python
if self.rolle == ROLLE_HJEM and not opphold and self.personer:
    opphold = self._hjemmeopphold()
```

I det den første «Oslo – Navn» havnet i kalenderen, slo stedet om fra et par hundre netter
til bare det som var skrevet. To instanser kunne derfor vise vidt forskjellige tall for
samme sted, avhengig av hva hver av dem hadde rukket å lese.

Det er nå et valg i oppsettet, **«Hjemmenetter regnes fra»**:

* **Fravær** — alle netter ingen var på en hytte. Riktig for et hjem dere bor i.
* **Kalender** — bare det som er skrevet. Riktig for et sted som føres som alle andre.
* **Auto** — den gamle oppførselen, beholdt som standard så ingenting endrer seg av seg selv.

Oversiktssensoren har fått attributtet `hjemme_kilde`, som sier hvilken av dem som faktisk
er i bruk. Viser to instanser ulike tall, er det første sted å se.


**2.3.3 — stedet ble til en person**

Fant reservenavnet ingen kjent person i tittelen, tok det alt etter skilletegnet — og
uten skilletegn ble det hele tittelen. En hendelse som bare het «Strömstad» ga derfor en
person ved navn Strömstad, med egen `sensor.netter_stromstad`, og nettene hennes ble
lagt til i totalen.

Navnet hentes nå bare når tittelen faktisk har formen «Sted – Navn», og delen etter
skilletegnet forkastes hvis den er stedsnavnet om igjen. Oppholdet blir stående — noen var
der — men står som «Ukjent» i lista og lager ingen personsensor. Tankestrek, bindestrek,
kolon og loddrett strek godtas som skilletegn.

Rydd vekk `sensor.netter_stromstad` og tilsvarende manuelt i entitetsregisteret etter
oppgraderingen; de blir liggende som utilgjengelige ellers.


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
