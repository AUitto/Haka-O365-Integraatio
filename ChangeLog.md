# ChangeLog

## 16.4.2020 v. 2.1.0
- Lisätty ominaisuus, joka seuraa paremmin käyttäjiin kohdistuneita muutoksia.
- Lisätty ominaisuus, joka lähettää sähköpostia, kun uusi käyttäjä luodaan, olemassaolevaa muokataan, jäsen poistetaan käytöstä tai kun jäsen poistetaan kokonaan.
- Ylläolevat ominaisuudet vaativat merkittäviä muutoksia tietokantaan. Tietokantaan luodaan kokonaisuudessaan uusi taulu ´´´status´´´ ja ´´´users´´´ -taulusta poistetaan tietyt sarakkeet.
- Edellä mainitun lisäksi parameters.json-asetustiedostoon tulee listätä osoitteet josta ja johon lähetetään sähköposti-ilmoitukset.

## 14.4.2020 v. 2.0.6
- Bugikorjaus

## 13.4.2020 v. 2.0.5
- Lisätty rooliin tai koulutustasoon perustuva "titteli", joka näkyy O365:ssä jobTitle-arvona. Tätä varten lisättävä users-tauluun sarakkeet title ja education:
```ALTER TABLE users ADD title varchar (50) AFTER firstname;```
```ALTER TABLE users ADD education varchar (50) AFTER title;```

## 8.4.2020 v. 2.0.004
- Taulut lukitaan ennen, kuin niihin lähdetään kirjoittamaan. Ennen lukitsemista varmistetaan, että taulut eivät jo ole lukossa, ja jos ovat, niin suorittaminen keskeytetään virheeseen. Tällä vältetään päällekkäinen kirjoittaminen tilanteessa, jossa suoritus on jäänyt silmukkaan, jos Exchange Online ei kykene provisioimaan käyttäjätilejä.

## 8.4.2020 v. 2.0.003
- Sen sijaan, että käyttäjä poistettaisiin suoraan, se disabloidaan 30 päivän ajaksi ennen poistamista. Tällä tarkoituksena taklata ongelmat, joita voi esiintyä HAKA:ssa tapahtuvien yllättävien muutoksien johdosta.
- Tätä varten users-tauluun on lisättävä sarake disabled_date:
```ALTER TABLE users ADD disabled_date timestamp AFTER new_user_flag;```

## 4.4.2020 v. 2.0.002 
- Vaihdettu roolien haku vastaamaan HAKA:an yllättäen tehtyä päivitystä.
- Lisätty toiminnallisuus, joka varmistaa, että tietokannassa on HAKA:n jäsennumeron mukainen tietue ennen kuin sille lisätään ryhmiä.
