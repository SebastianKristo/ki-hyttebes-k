## Endret

**Hvert sted bruker sine egne posisjonsbrytere.** På betyr her, av betyr borte – bryteren i Oslo sier om du er i Oslo, den på Toten om du er på Toten. Stedet en Home Assistant står på, registrerer oppholdene sine i kalenderen, også når stedet er hjemmet.

**De andre stedene leses fra kalenderen.** Legg dem inn med bare navn og kalender; hvem som var der kommer fra hendelsene «Sted – Navn», og navnene plukkes opp fra hendelsene selv.

Rollen *Hjemme* eller *Hytte* handler nå bare om farger og helgeoversikten. Registreringen styres av om stedet har brytere.

Har et hjem uten egne hendelser i kalenderen, regnes oppholdene der fortsatt ut som dagene ingen hytte dekker – som reserve.

## Oppsett med flere instanser

| | Oslo | Strömstad | Toten |
|---|---|---|---|
| **Oslo-instansen** | egne brytere, registrerer | tomt, leser | tomt, leser |
| **Strömstad-instansen** | tomt, leser | egne brytere, registrerer | tomt, leser |
| **Toten-instansen** | tomt, leser | tomt, leser | egne brytere, registrerer |
