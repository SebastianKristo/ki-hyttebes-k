## Nytt

**Hjemme og hytte.** Hvert sted merkes nå som *Hjemme* eller *Hytte* i oppsettet. Den som ikke er registrert på en hytte, regnes som hjemme – så Oslo, Strömstad og Toten henger sammen i én oversikt.

**Helgeoversikt.** `sensor.<hjemsted>_helger` viser de siste 16 helgene med hvem som var hvor, lørdag og søndag sett under ett. Dro noen hjem søndag, står det «Strömstad → Oslo». Attributtet `hvor_er_vi_naa` svarer for i dag.

**Ny tjeneste `ki_hyttebesok.hvor_var_vi`** – spør med `uke: 32`, en `dato:`, eller uten noe for de siste helgene. Svaret kommer som `response_variable`.

## Merk

Eksisterende oppføringer står som «Hytte» til du endrer dem. Gå inn på Oslo-oppføringen og sett den til *Hjemme*, ellers får du ingen helgeoversikt.
