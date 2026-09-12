<p align="center">
  <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/logo.svg" width="120" alt="KI Hyttebesøk">
</p>

<h1 align="center">KI Hyttebesøk</h1>

<p align="center">
  Hvem var på hytta, når, og hvor lenge – ført automatisk til Google-kalenderen og lest tilbake som statistikk.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/HACS-egendefinert-orange.svg"> 
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5.svg"> 
  <img src="https://img.shields.io/badge/versjon-1.0.0-brightgreen.svg">
</p>

---

## Hvorfor

Et opphold på hytta er lett å glemme å registrere, og «hvem har vært der mest i år» er umulig å svare på uten
å bla gjennom kalenderen. Denne integrasjonen fører loggen selv: den ser når noen kommer, når de drar, og
skriver ett innslag per person i kalenderen du allerede bruker.

Den erstatter en pakke med `input_datetime`-hjelpere, template-sensorer og to automasjoner per sted.

## Hva den gjør

| | |
|---|---|
| <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/personer.svg" width="34"> | **Merker ankomst og avreise.** Hver person har en bryter, `person`- eller `device_tracker`-entitet som sier om hen er på stedet. Kommer noen, starter et opphold. Drar de – og blir borte lenger enn forsinkelsen – skrives oppholdet til kalenderen. |
| <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/kalender.svg" width="34"> | **Én kalender for flere steder.** Hendelsene heter «Strömstad – Sebastian», så Oslo, Toten og Strömstad kan dele samme Google-kalender. Hvert sted er sin egen oppføring i integrasjonen. |
| <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/netter.svg" width="34"> | **Riktig antall netter.** Én hendelse per person betyr at det stemmer selv når én drar søndag og resten blir til mandag. |
| <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/statistikk.svg" width="34"> | **Leser historikken tilbake.** Kalenderen leses hvert kvarter og gir netter og besøk per person, siste og neste besøk, netter per måned, og hvem som var der hver enkelt dag. |

## Installasjon

**HACS**

1. HACS → tre prikker → *Egendefinerte repositorier*
2. Legg til `https://github.com/SebastianKristo/ki-hyttebes-k` som type **Integration**
3. Installer **KI Hyttebesøk** og start Home Assistant på nytt
4. Innstillinger → Enheter og tjenester → *Legg til integrasjon* → **KI Hyttebesøk**

**Manuelt**

Kopier `custom_components/ki_hyttebesok` til `/config/custom_components/` og start på nytt.

## Oppsett

Legg til én oppføring per sted.

| Felt | Betydning |
|---|---|
| **Sted** | Strömstad, Toten, Oslo … Navnet brukes i hendelsestittelen og til å skille stedene i en delt kalender |
| **Kalender** | Google-kalenderen som skal skrives til og leses fra |
| **Brytere** | Én per person: `switch.sebastian_posisjon_hjemme_borte`, `person.rune`, `device_tracker.cybele` … |
| **Navn** | Navnene i samme rekkefølge, skilt med komma. Tomt gir navnet fra entiteten |
| **Forsinkelse** | Minutter borte før avreisen regnes som ekte. Standard 10 – hindrer at en tur på butikken avslutter oppholdet |
| **Historikk** | Hvor mange dager bakover kalenderen leses. Standard 400, så du får med fjoråret |

Kalenderen må ha skrivetilgang (`calendar.create_event`), og Home Assistant må være 2024.5 eller nyere for
`calendar.get_events`.

## Entiteter

| Entitet | Viser |
|---|---|
| `sensor.<sted>_oversikt` | Hvem som er der nå. Attributtene har alt kortet bruker: personer, opphold, kommende turer, netter per måned og dag-for-dag-oversikt |
| `sensor.<sted>_netter_i_år` | Antall netter i år, med `per_maaned` som attributt |
| `sensor.<sted>_netter_<person>` | Netter per person, med siste besøk og om hen er der nå |
| `sensor.<sted>_siste_besøk` | Siste opphold, med de 20 foregående som attributt |
| `sensor.<sted>_neste_besøk` | Første planlagte tur fra kalenderen |
| `sensor.<sted>_her_nå` | Hvor mange som er der |
| `binary_sensor.<sted>_noen_på_stedet` | Av eller på |

## Tjenester

```yaml
# Hent historikken på nytt med en gang
action: ki_hyttebesok.les_kalender

# Legg inn et opphold som ikke ble fanget opp
action: ki_hyttebesok.registrer_opphold
data:
  person: Rune
  fra: '2026-07-04'
  til: '2026-07-09'     # siste natt
  sted: Strömstad       # valgfritt når du har flere steder
```

## Kortet

<p align="center">
  <img src="https://raw.githubusercontent.com/SebastianKristo/ki-hyttebes-k/main/brand/logo.svg" width="60">
</p>

`ki-hytte-card` i [ki-cards](https://github.com/SebastianKristo/ki-cards) viser dette som:

- **Kalender** – en månedsrute der hver dag fargelegges etter hvem som var der. Er flere der samtidig, deles
  dagen i striper. Planlagte turer får stiplet kant.
- **Opphold** – planlagte turer øverst, historikken under, med datoer og antall netter.
- **Statistikk** – netter per måned som stablede søyler per person, og et kort per person.

Øverst et statuskort der hytta får lys i vinduene og røyk fra pipa når noen er der.

```yaml
type: custom:ki-hytte-card
sted: Strömstad
faner: [kalender, opphold, statistikk]
```

## Slik virker registreringen

1. Bryteren for en person går til «på» → ankomstdatoen lagres (og overlever omstart).
2. Bryteren går til «av» og blir der lenger enn forsinkelsen → en heldagshendelse skrives:
   `Strömstad – Sebastian`, fra ankomstdatoen til dagen etter avreisen (Google bruker eksklusiv sluttdato).
3. Kalenderen leses på nytt, og tallene oppdateres.

Ligger det allerede opphold i kalenderen fra før, plukkes de opp med en gang – historikken starter ikke på null.

## Ikoner

Ikonene ligger i `brand/` som SVG og PNG i 256 px. `brand/logo.png` passer som *Social preview* i
repo-innstillingene.
