# Haka-O365-Integraatio
Integraatiotoiminto HAKA - Turvallisuusosaamisen hallinointikannan ja Microsoft Office 365:n välillä.

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

## Tarvittavat komponentit
- Palvelin:
-- SQL-palvelin ja Python3

#### SQL-palvelin


>MariaDB [haka_integ]> describe users;
>+----------------------+------------------+------+-----+---------+-------+
>| Field                | Type             | Null | Key | Default | Extra |
>+----------------------+------------------+------+-----+---------+-------+
>| haka_uid             | int(10) unsigned | NO   | PRI | NULL    |       |
>| aad_uuid             | varchar(36)      | YES  |     | NULL    |       |
>| username             | varchar(40)      | YES  |     | NULL    |       |
>| lastname             | varchar(20)      | NO   |     | NULL    |       |
>| firstname            | varchar(20)      | NO   |     | NULL    |       |
>| hireDate             | datetime         | YES  |     | NULL    |       |
>| mail                 | varchar(320)     | NO   |     | NULL    |       |
>| phone                | varchar(22)      | NO   |     | NULL    |       |
>| onedrive_id          | varchar(40)      | YES  |     | NULL    |       |
>| onedrive_shared_flag | tinyint(1)       | YES  |     | NULL    |       |
>| exists_haka_flag     | tinyint(1)       | YES  |     | NULL    |       |
>| updated_flag         | tinyint(1)       | YES  |     | NULL    |       |
>| new_user_flag        | tinyint(1)       | YES  |     | NULL    |       |
>+----------------------+------------------+------+-----+---------+-------+

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
{code}

#### Users-taulu
Toimii päätauluna kannassa. HAKA:sta tuodaan käyttäjän HAKA:ssa oleva ID-tietue, etu- ja sukunimi, sähköpostiosoite, puhelinnumero ja jäsenyyden alkamisaika. Etu- ja sukunimestä muodostetaan kantaan käyttäjätunnus muodossa etu.sukunimi. Kun Azure Active Directoryyn on luotu käyttäjä, sen UUID-tietue tallennetaan kantaan, jotta osataan myöhemmässä vaiheessa päivittää ja poistaa oikea käyttäjä. Samoin taulussa on muutama erillinen lippu, joilla ohjaillaan sovelluksen toimintaa eri vaiheissa.

#### Groups-taulu
Pitää sisällään tiedot HAKA:sta tuodun jäsenen osastosta, sekä tälle merkityistä rooleista. Taulussa on myös lippuja, joilla ohjaillaan sovelluksen toimintaa eri vaiheissa.

#### Groupmap-taulu
Tällä ohjataan AAD:ssa olevien ryhmien ja HAKA:n kautta tuotujen roolien yhdistämistä. Samassa taulussa on myös Mode-sarake, joka on joko Member tai Owner, riippuen siitä, että halutaanko tietylle HAKA:n roolille antaa AAD:ssa omistajuus vai pelkkä jäsenyys. Tämä taulu täytyy muodostaa kokonaisuudessaan itse sen perusteella, miten ryhmien haluaa muodostuvan.

Esimerkki Groupmap-taulun sisällöstä:
+----------------------------------+--------------------------------------+--------+
| haka_group                       | aad_gid                              | mode   |
+----------------------------------+--------------------------------------+--------+
| 1. varapäällikkö                 | bee143d8-xxxx-47df-abb3-720a51c27c7a | owner  |
| 2. varapäällikkö                 | bee143d8-xxxx-47df-abb3-720a51c27c7a | owner  |
| Koulutuspäällikkö                | bee143d8-xxxx-47df-abb3-720a51c27c7a | owner  |
| Hälytysosasto                    | bee143d8-xxxx-47df-abb3-720a51c27c7a | member |
| 1. varapäällikkö                 | 6e19028b-zzzz-4c5b-b55a-44091d38a5a5 | owner  |
| 2. varapäällikkö                 | 6e19028b-zzzz-4c5b-b55a-44091d38a5a5 | member |
| Koulutuspäällikkö                | 6e19028b-zzzz-4c5b-b55a-44091d38a5a5 | member |
| Hälytysosasto                    | 6e19028b-zzzz-4c5b-b55a-44091d38a5a5 | member |
| Puheenjohtaja                    | 4a121162-yyyy-4b28-97eb-9bea09138f1f | owner  |
| Hallituksen jäsen                | 4a121162-yyyy-4b28-97eb-9bea09138f1f | member |
| Sihteeri                         | 4a121162-yyyy-4b28-97eb-9bea09138f1f | member |
| Puheenjohtaja                    | f4511972-aaaa-46b7-bb33-4eabfbae17f6 | owner  |
| Hallituksen jäsen                | f4511972-aaaa-46b7-bb33-4eabfbae17f6 | member |
| Sihteeri                         | f4511972-aaaa-46b7-bb33-4eabfbae17f6 | member |
+----------------------------------+--------------------------------------+--------+

