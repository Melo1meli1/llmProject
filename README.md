# Identifisering av kontraktsklausuler med språkmodeller

Prosjektet undersøker hvordan en språkmodell kan identifisere seks utvalgte klausultyper og hente ut tilhørende tekstpassasjer fra kommersielle kontrakter. Språkmodellen sammenlignes med en søkebasert metode, med annotasjoner fra CUAD som fasit.

## Hovedanalyse

`kontraktsanalyse.ipynb` inneholder hovedanalysen, inkludert metodeoppsett, evaluering og feilanalyse.

Notebooken er kjørt og skal inneholde lagrede tabeller og figurer, slik at resultatene kan leses uten å kjøre analysen på nytt. Full ny kjøring krever datasettet og en egen API-nøkkel, og medfører API-kostnader.

## Kjøring av demo

Demoen demonstrerer metodene med medfølgende kontrakter og ferdige innstillinger. Hovedanalysen trenger ikke kjøres først.

1. Pakk ut hele ZIP-filen og behold mappestrukturen.
2. Åpne `demo/demo.ipynb` i et miljø som støtter Jupyter-notebooker.
3. Sørg for at notebookens arbeidsmappe er `demo`, der `demo_core.py` ligger.
4. Behold `MODE = "api"` i oppsettcellen.
5. Kjør cellene ovenfra og ned. Skriv inn egen OpenAI API-nøkkel når inntastingsfeltet vises.

Kjøringen krever internettilgang og medfører API-kostnader. API-nøkkelen skrives ikke til fil, men brukes av API-klienten i minnet mens kernelen kjører. Ved ny kjøring av oppsettcellen må nøkkelen oppgis på nytt.

## Hva demoen viser

Del 1–6 sammenligner språkmodellen og søkemetoden på to forhåndsvalgte testkontrakter. Utdragene sammenlignes med CUAD-fasiten. Eksemplene illustrerer både styrker og feil, og er ikke et representativt utvalg for å måle generell ytelse.

Del 7 analyserer én tilfeldig valgt reservekontrakt i alle seks klausulkategorier. Først vises en kontraktsoversikt med korte norske forklaringer og originalutdrag. Deretter sammenlignes funnene fra begge metodene med fasiten.

Reservekontrakten trekkes blant kontrakter med annotasjoner i minst to kategorier. Kontrakter brukt som few-shot-eksempler er utelatt. Fasiten brukes til utvalg og etterkontroll, men gis ikke til modellen for kontrakten som analyseres.

For å prøve et nytt eksempel kjøres del 7.1–7.5 på nytt. Kontraktsvalget og modellsvarene kan variere mellom kjøringer. Det kan derfor være nyttig å prøve flere eksempler. Hver ny analyse medfører nye API-kall.

## Filer som brukes av demoen

- `demo/demo.ipynb`: demonstrasjon og visning av resultater.
- `demo/demo_core.py`: funksjoner for søk, modellkall og evaluering.
- `demo/data/demo_kontrakter.json`: de forhåndsvalgte kontraktene.
- `demo/data/demo_oppsett.json`: innstillinger for del 1–6.
- `demo/data/demo_reserve.json`: reservekontrakter til del 7.
- `demo/data/reserve_oppsett.json`: innstillinger for del 7.

Resultattabellen og prediksjonene fra del 1–6 lagres i `demo/output/`. Rå modellsvar fra uttrekkskallene lagres i `demo/output/api_svar/`.

## Tolkning av resultater

Evalueringen skiller mellom forekomst av klausultyper og tekstoverlapp mellom returnerte utdrag og fasit. Et riktig treff på klausulforekomst betyr ikke nødvendigvis at hele den riktige tekstpassasjen er hentet ut.

De norske forklaringene i del 7 er en ekstra presentasjonsdel som ikke er evaluert i hovedforsøket. Kontraktsoversikten dekker seks utvalgte klausultyper og erstatter ikke en fullstendig gjennomgang av kontrakten.

Datakilde: CUAD / The Atticus Project.
