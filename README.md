# Haka-O365-Integraatio
Integraatiotoiminto HAKA - Turvallisuusosaamisen hallinointikannan ja Microsoft Office 365:n välillä.
```
usage: CreateUsers.py [-h] -c CONFIG [-v] [-d]

This Python script is used to export users from HAKA - Turvallisuusosaamisen
hallinnointikanta and import them to Azure Active Directory.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Parameters.json file containing credentials.
  -v, --verbose         Run verbosely. Print only on errors and when users
                        modified.
  -d, --debug           Run in debug mode. Print me everything, EVERYTHING!
```
## Tarvittavat komponentit
- Palvelin:
-- SQL-palvelin ja Python3

#### SQL-palvelin
Tietokannalle kannattanee luoda käyttäjä, jolla on SELECT, UPDATE, INSERT, DELETE, LOCK TABLES -grantit ko. kantaan.
```
MariaDB [haka_integ]> describe users;
+----------------------+------------------+------+-----+---------+-------+
| Field                | Type             | Null | Key | Default | Extra |
+----------------------+------------------+------+-----+---------+-------+
| haka_uid             | int(10) unsigned | NO   | PRI | NULL    |       |
| aad_uuid             | varchar(36)      | YES  |     | NULL    |       |
| username             | varchar(40)      | YES  |     | NULL    |       |
| lastname             | varchar(20)      | NO   |     | NULL    |       |
| firstname            | varchar(20)      | NO   |     | NULL    |       |
| title                | varchar(50)      | YES  |     | NULL    |       |
| education            | varchar(50)      | YES  |     | NULL    |       |
| hireDate             | datetime         | YES  |     | NULL    |       |
| mail                 | varchar(320)     | NO   |     | NULL    |       |
| phone                | varchar(22)      | NO   |     | NULL    |       |
| onedrive_id          | varchar(40)      | YES  |     | NULL    |       |
| onedrive_shared_flag | tinyint(1)       | YES  |     | NULL    |       |
| disabled_date        | timestamp        | YES  |     | NULL    |       |
+----------------------+------------------+------+-----+---------+-------+

MariaDB [haka_integ]> describe groups;
+------------------+------------------+------+-----+---------+-------+
| Field            | Type             | Null | Key | Default | Extra |
+------------------+------------------+------+-----+---------+-------+
| haka_uid         | int(10) unsigned | NO   |     | NULL    |       |
| haka_group       | varchar(40)      | NO   |     | NULL    |       |
| exists_haka_flag | tinyint(1)       | YES  |     | NULL    |       |
| updated_flag     | tinyint(1)       | YES  |     | NULL    |       |
+------------------+------------------+------+-----+---------+-------+

MariaDB [haka_integ]> describe groupmap;
+------------+-------------+------+-----+---------+-------+
| Field      | Type        | Null | Key | Default | Extra |
+------------+-------------+------+-----+---------+-------+
| haka_group | varchar(40) | YES  |     | NULL    |       |
| aad_gid    | varchar(36) | YES  |     | NULL    |       |
| mode       | varchar(10) | YES  |     | NULL    |       |
+------------+-------------+------+-----+---------+-------+

MariaDB [haka_integ_dev]> describe status;
+--------------+------------------+------+-----+---------+-------+
| Field        | Type             | Null | Key | Default | Extra |
+--------------+------------------+------+-----+---------+-------+
| haka_uid     | int(10) unsigned | NO   |     | NULL    |       |
| modified_key | varchar(50)      | YES  |     | NULL    |       |
| status       | varchar(10)      | YES  |     | NULL    |       |
+--------------+------------------+------+-----+---------+-------+
```
#### Users-taulu
Toimii päätauluna kannassa. HAKA:sta tuodaan käyttäjän HAKA:ssa oleva ID-tietue, etu- ja sukunimi, sähköpostiosoite, puhelinnumero ja jäsenyyden alkamisaika. Etu- ja sukunimestä muodostetaan kantaan käyttäjätunnus muodossa etu.sukunimi. Kun Azure Active Directoryyn on luotu käyttäjä, sen UUID-tietue tallennetaan kantaan, jotta osataan myöhemmässä vaiheessa päivittää ja poistaa oikea käyttäjä. Samoin taulussa on muutama erillinen lippu, joilla ohjaillaan sovelluksen toimintaa eri vaiheissa.

#### Groups-taulu
Pitää sisällään tiedot HAKA:sta tuodun jäsenen osastosta, sekä tälle merkityistä rooleista. Taulussa on myös lippuja, joilla ohjaillaan sovelluksen toimintaa eri vaiheissa.

#### Groupmap-taulu
Tällä ohjataan AAD:ssa olevien ryhmien ja HAKA:n kautta tuotujen roolien yhdistämistä. Samassa taulussa on myös Mode-sarake, joka on joko Member tai Owner, riippuen siitä, että halutaanko tietylle HAKA:n roolille antaa AAD:ssa omistajuus vai pelkkä jäsenyys. Tämä taulu täytyy muodostaa kokonaisuudessaan itse sen perusteella, miten ryhmien haluaa muodostuvan. Taulussa oleva aad_gid arvo on haettava Azure AD:sta.

#### Status-taulu
Tällä ohjataan suorituksen aikana muutoksia ja niiden tilaa. Tämän tulisi olla suorituksen alkaessa tyhjä; mikäli näin ei ole, on edellinen suoritus jäänyt kesken.

Esimerkki Groupmap-taulun sisällöstä:
```
+----------------------------------+--------------------------------------+--------+
| haka_group                       | aad_gid                              | mode   |
+----------------------------------+--------------------------------------+--------+
| 1. varapäällikkö                 | bee143d8-xxxx-47df-abb3-bbbbbbbbbbbb | owner  |
| 2. varapäällikkö                 | bee143d8-xxxx-47df-abb3-bbbbbbbbbbbb | owner  |
| Koulutuspäällikkö                | bee143d8-xxxx-47df-abb3-bbbbbbbbbbbb | owner  |
| Hälytysosasto                    | bee143d8-xxxx-47df-abb3-bbbbbbbbbbbb | member |
| 1. varapäällikkö                 | 6e19028b-zzzz-4c5b-b55a-bbbbbbbbbbbb | owner  |
| 2. varapäällikkö                 | 6e19028b-zzzz-4c5b-b55a-bbbbbbbbbbbb | member |
| Koulutuspäällikkö                | 6e19028b-zzzz-4c5b-b55a-bbbbbbbbbbbb | member |
| Hälytysosasto                    | 6e19028b-zzzz-4c5b-b55a-bbbbbbbbbbbb | member |
| Puheenjohtaja                    | 4a121162-yyyy-4b28-97eb-bbbbbbbbbbbb | owner  |
| Hallituksen jäsen                | 4a121162-yyyy-4b28-97eb-bbbbbbbbbbbb | member |
| Sihteeri                         | 4a121162-yyyy-4b28-97eb-bbbbbbbbbbbb | member |
| Puheenjohtaja                    | f4511972-aaaa-46b7-bb33-bbbbbbbbbbbb | owner  |
| Hallituksen jäsen                | f4511972-aaaa-46b7-bb33-bbbbbbbbbbbb | member |
| Sihteeri                         | f4511972-aaaa-46b7-bb33-bbbbbbbbbbbb | member |
+----------------------------------+--------------------------------------+--------+
```
## Esimerkki:
```
python3 CreateUsers.py -v -c parameters.json
```
Suorittaa skriptin siten, että tulostetaan käyttäjiin kohdistuvat muutokset ja virheilmoitukset. Käytetään samassa hakemistossa olevaa parameters.json-tiedostoa. Tämä voitaisiin ajaa myös Crontabilla siten, että tuloste tulee sähköpostilla, jolloin pysytään tietoisina muokatuista ja uusista jäsenistä.

## Linkkejä
Microsoft Graph API Reference: https://docs.microsoft.com/en-us/graph/api/overview?toc=./ref/toc.json&view=graph-rest-1.0
MS Identity Python Daemon: https://github.com/Azure-Samples/ms-identity-python-daemon

## To Do:
Päivitetään viestinvälitystä siten, että se lähettää tervetuliaisviestin uudelle käyttäjälle, mutta myös ilmoitukset virhetilanteista ym.

aad_user_management ja db_manager funktioiden siivoaminen. Väitän, että tuolta saisi varmaan jonkun 500 riviä siivottua, kun vaan ymmärtäisi mitä tekee.

Päivitystoiminto sähköpostien edelleenvälitykselle, ts. toiminnallisuus joka tarkastaa, onko edelleenvälitys yhä olemassa ja käytössä; jos kyllä: vaihda kohdesähköpostiosoite, jos se on muuttunut HAKA:ssa.
