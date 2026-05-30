---
name: belgische-jobsites
description: |
  Volledige, gecureerde lijst van Belgische job-websites voor the candidate's
  sollicitatieproces. Georganiseerd per categorie en prioriteit.
  ALTIJD EERST DEZE SKILL RAADPLEGEN bij het zoeken naar jobs.
  Geen Nederlandse websites — uitsluitend Belgische focus.
---

# Belgische Jobsites — Masterlijst

> **Raadpleeg deze skill altijd EERST** wanneer er jobs gezocht, gescraped
> of gemonitord moeten worden. Deze lijst is de single source of truth.

---

## 1. Must-Have Platforms (dagelijks monitoren — 80% van alle relevante jobs)

| Platform        | URL                                   | Scraper key    | Status    |
|-----------------|---------------------------------------|----------------|-----------|
| LinkedIn Jobs   | https://www.linkedin.com/jobs         | `linkedin`     | ⚠ 403 blok |
| VDAB            | https://www.vdab.be/jobs              | `vdab`         | ✅ actief   |
| Indeed België   | https://be.indeed.com                 | `indeed`       | ✅ actief   |
| Jobat           | https://www.jobat.be                  | `jobat`        | ✅ actief   |
| StepStone BE    | https://www.stepstone.be              | `stepstone`    | ✅ actief   |

> **Let op:** LinkedIn blokkeert scrapers (403). Gebruik LinkedIn
> handmatig via de browser of via de LinkedIn API als die beschikbaar is.

---

## 2. Senior, Management & Directiefuncties

Relevant voor: Marketing Director, Head of Marketing, Sponsoring Director,
Fractional CMO, Business Development, Partnerships.

| Platform                    | URL                                              | Scraper key         |
|-----------------------------|--------------------------------------------------|---------------------|
| Experteer                   | https://www.experteer.be                         | `experteer`         |
| Michael Page                | https://www.michaelpage.be                       | `michaelpage`       |
| Robert Walters              | https://www.robertwalters.be                     | `robertwalters`     |
| Hudson Belgium              | https://www.hudsonsolutions.com/be-nl            | `hudson`            |
| Korn Ferry                  | https://www.kornferry.com                        | `kornferry`         |
| Egon Zehnder                | https://www.egonzehnder.com                      | `egonzehnder`       |
| Russell Reynolds Associates | https://www.russellreynolds.com                  | `russellreynolds`   |

---

## 3. Interim Management & Freelance Opdrachten

Extra aandacht — zeer relevant voor the candidate's ervaring.

| Platform             | URL                                        | Scraper key          |
|----------------------|--------------------------------------------|----------------------|
| Minds&More           | https://www.mindsandmore.be                | `mindsandmore`       |
| ClearXperts          | https://www.clearxperts.com                | `clearxperts`        |
| Robert Half          | https://www.roberthalf.com/be/en           | `roberthalf`         |
| HeadCount            | https://www.headcount.be                   | `headcount`          |
| Brainbridge          | https://www.brainbridge.be                 | `brainbridge`        |
| Connecting Expertise | https://www.connecting-expertise.com       | `connectingexpertise`|

---

## 4. Marketing, Communicatie & Digitale Profielen

Specifiek relevant voor the candidate's profiel.

| Platform           | URL                                    | Scraper key      |
|--------------------|----------------------------------------|------------------|
| Bloovi Jobs        | https://www.bloovi.be/jobs             | `bloovi`         |
| PUB Jobs           | https://www.pub.be/jobs                | `pub`            |
| Media Marketing    | https://www.mediamarketing.com         | `mediamarketing` |
| Bright Plus Jobs   | https://www.brightplus.be              | `brightplus`     |

---

## 5. Sport, Sponsoring, Events & Entertainment

Sterk profiel van the candidate — zeker monitoren.

| Platform                  | URL                                        | Scraper key          |
|---------------------------|--------------------------------------------|----------------------|
| Sportcareers Belgium      | https://www.sportcareers.be                | `sportcareers`       |
| Golazo Careers            | https://www.golazo.com                     | `golazo`             |
| House of Entertainment    | https://www.houseofentertainment.be        | `houseofentertainment` |
| Live Nation Belgium       | https://www.livenation.be                  | `livenation`         |

---

## 6. Overheid & Semi-Overheid

Vaak onderschat, maar sterke kansen.

| Platform                      | URL                                                           | Scraper key           |
|-------------------------------|---------------------------------------------------------------|-----------------------|
| Werkenvoor.be (federaal)      | https://www.werkenvoor.be                                     | `werkenvoor`          |
| Vlaamse Overheid              | https://www.vlaanderen.be/vacatures-bij-de-vlaamse-overheid   | `vlaamseoverheid`     |
| Provincie Oost-Vlaanderen     | https://www.oost-vlaanderen.be/vacatures                      | `oost-vlaanderen`     |
| Stad Gent                     | https://jobs.stad.gent                                        | `stadgent`            |
| Port of Antwerp-Bruges        | https://www.portofantwerpbruges.com                           | `portofantwerpbruges` |

---

## 7. Interimkantoren (ook vaste jobs)

| Platform       | URL                              | Scraper key    |
|----------------|----------------------------------|----------------|
| Randstad       | https://www.randstad.be          | `randstad`     |
| Start People   | https://www.startpeople.be       | `startpeople`  |
| Manpower       | https://www.manpower.be          | `manpower`     |
| Unique         | https://www.unique.be            | `unique`       |
| Hays Belgium   | https://www.hays.be              | `hays`         |
| Adecco Belgium | https://www.adecco.be            | `adecco`       |

---

## 8. Bedrijven Rechtstreeks

Voor senior marketingrollen verschijnen vacatures eerst op de bedrijfssite.

| Bedrijf             | URL                                          | Scraper key    |
|---------------------|----------------------------------------------|----------------|
| Belfius             | https://jobs.belfius.be                      | `belfius`      |
| Telenet             | https://jobs.telenet.be                      | `telenet`      |
| Proximus            | https://jobs.proximus.com                    | `proximus`     |
| Colruyt Group       | https://jobs.colruytgroup.com                | `colruyt`      |
| NMBS                | https://www.belgiantrain.be/jobs             | `nmbs`         |
| KBC                 | https://www.kbc.com/en/careers.html          | `kbc`          |

---

## Zoekwoorden per profiel

Bij het scrapen van deze sites, gebruik deze zoektermen (combinaties):

**Primaire titels:**
- marketing manager
- brand manager
- marketing director
- head of marketing
- sponsorship manager
- CMO / chief marketing officer

**Secundaire titels:**
- communications manager
- business development manager
- partnership manager
- fractional CMO
- interim marketing director

**Locatiefilters:**
- België / Belgium / Belgique
- Vlaanderen
- West-Vlaanderen
- Oost-Vlaanderen
- Gent / Brussel / Antwerpen

---

## Gebruik in de applicatie

### In `src/scraper.py`

De `SITE_URLS` dict bevat de actieve scrape-configuratie.
Elke key in die dict komt overeen met een scraper key uit deze tabel.

### Prioriteit bij scraping

1. **Dagelijks**: VDAB, Indeed, Jobat, StepStone (must-haves)
2. **Wekelijks**: Senior platforms + interim + marketing-specifiek
3. **Maandelijks**: Overheid + bedrijven rechtstreeks

### Sites toevoegen of verwijderen

1. Pas deze skill-tabel aan
2. Voeg de URL-patronen toe aan `SITE_URLS` in `src/scraper.py`
3. Test met `python main.py run --site <key> -v`

---

## ⚠ Uitgesloten

De volgende sites zijn **bewust niet opgenomen** (geen Belgische focus):

- ~~werk.nl~~ (Nederland)
- ~~nationalevacaturebank.nl~~ (Nederland)
- ~~indeed.nl~~ (Nederland)
- ~~intermediair.nl~~ (Nederland)

Enkel **be.indeed.com** (België) is opgenomen, niet indeed.nl.
