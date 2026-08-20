# Model lokalizacji pasiek — województwo lubelskie

Wskazuje, gdzie postawić ul, na podstawie deklaracji upraw ARiMR, detekcji
rzepaku z Sentinel-2, modelu terminu kwitnienia i warunków lotu pszczół.
Zasięg: całe województwo lubelskie, siatka 100 m (1 px = 1 ha).

Pochodzenie każdego parametru: [ZRODLA.md](ZRODLA.md).

## Jak to otworzyć

**Otwórz `index.html`.** Nic nie trzeba instalować — cztery strony działają
z dysku, dwuklikiem, także po skopiowaniu katalogu na pendrive.

| strona | co pokazuje | potrzebuje internetu |
|---|---|---|
| `index.html` | punkt wejścia | nie |
| `prognoza.html` | kiedy zakwitnie rzepak w wybranym miejscu | **tak** (pogoda z Open-Meteo) |
| `kalendarz.html` | co i kiedy kwitnie w każdym powiecie | nie |
| `raport.html` | pełne wyniki, walidacje, zastrzeżenia | nie |
| `mechanika.html` | krok po kroku, skąd biorą się liczby | nie |

Mapy i wykresy są wtopione w pliki, więc nie ma czego zgubić przy wysyłaniu.

**Prognoza liczy się w przeglądarce.** Model termiczny jest przepisany
z Pythona na JavaScript, a pogodę strona pobiera wprost z Open-Meteo — dlatego
działa bez serwera. Zgodność obu wersji nie jest założona, tylko sprawdzana:
`skrypty/serwis/test_rownowaznosc.py` przepuszcza te same punkty przez Pythona
i przez przeglądarkę i porównuje 11 pól. Test wykrył już jedną realną
rozbieżność (patrz ZRODLA.md, „Zaokrąglanie połówek").

### Przebudowa stron

```
python skrypty/serwis/eksport_paczka.py     # buduje prognoze + nawigacje + index
python skrypty/serwis/test_strony.py        # czy otwieraja sie z dysku bez bledu JS
python skrypty/serwis/test_rownowaznosc.py  # czy JS liczy to samo, co Python
```

### Wersja serwerowa (opcjonalna)

`bash skrypty/serwis/restart.sh` uruchamia mikroserwis Flask na
http://127.0.0.1:8000 — to samo, plus API `/prognoza?lat=&lon=`.
**Wymaga pełnych danych** (`dane/`, `wyniki/cache/`, `wyniki/rastry/` — 4,6 GB),
których repozytorium nie zawiera. Po samym pobraniu projektu nie ruszy;
strony statyczne owszem.

## Co ten model liczy, a czego nie

**Liczy** potencjał pożytkowy — ile cukrów w nektarze pszczoła z danego punktu
realnie dosięgnie, ważone odległością (jądro wykładnicze, λ = 1 km, zasięg 3 km).

**Nie jest** prognozą plonu miodu. Między potencjałem a zbiorem stoi siła
rodziny, konkurencja innych pasiek i to, czy w danym miejscu wolno ul postawić —
żadnej z tych rzeczy model nie ma. Potencjał nie został zwalidowany ani jednym
rzeczywistym zbiorem pasieki.

**Zakres komponentów uczonych:** klasyfikacja z Sentinel-2 i model fenologiczny
opracowano wyłącznie dla rzepaku ozimego (57% cukrów w województwie). Warstwa
potencjału obejmuje 13 zadeklarowanych upraw pożytkowych — wyłącznie te
z udokumentowaną wydajnością (klasa A/B w ZRODLA.md); uprawy bez źródła
(1,1% cukrów) są wykluczone, nie oszacowane. Terminy kwitnienia gatunków
innych niż rzepak pochodzą ze stałych dat literaturowych, nie z modelu.

## Główne produkty

| mapa | plik | treść |
|---|---|---|
| kalendarz interaktywny | `kalendarz.html` | rolnicy: pełne uprawy 2025/26; satelita: sam rzepak 2019–2025 |
| przeciętny rok + niezawodność | `mapy/mapa_sredni_rok.png` | średnia 8 sezonów 2019–2026 i liczba sezonów w top-20% |
| potencjał, średnia 2 sezonów deklaracji | `mapy/mapa_sezonow.png` | 2025/2026 + mapa zmian między nimi |
| kalendarz: KIEDY + GDZIE | `mapy/mapa_woj_czas.png` | dekada szczytu + suma sezonowa |
| wersja czysto teledetekcyjna | `mapy/mapa_teledetekcja.png` | rzepak + łąki WorldCover; nie jest to zakładka satelity w kalendarzu |
| detekcja vs deklaracje | `mapy/mapa_detekcji.png` | dowód: r = 0,94 po rozmyciu zasięgiem lotu |
| sam model fenologiczny | `mapy/mapa_modelu.png` | mapa terminu kwitnienia + szereg 2000–2026 |
| prognoza w trakcie sezonu | `mapy/wykres_prognoza.png` | błąd vs wyprzedzenie (hindcast) |

## Wyniki liczbowe

| element | miara |
|---|---|
| klasyfikator rzepaku (8 cech) | F1 0,90 na punktach; po rozmyciu 3 km r = 0,97 z GSA 2025, r = 0,95 z EUCROPMAP 2022 |
| klasyfikator przedkwitnieniowy (3 cechy) | F1 0,84 — wskazuje pola 6 tygodni przed kwitnieniem |
| **klasyfikator wieloklasowy S1+S2** | 12 klas pożytkowych, 21 tys. działek; F1-makro 0,718 (sama optyka 0,683) |
| **wkład radaru** | 52,9% ważności modelu; 0 pustych okien wobec 8 u optyki |
| **przenoszenie na inny rok** (ucz 2025 → sprawdź 2026) | detekcja bije odniesienie „rosło tam, gdzie rok temu" dla 4 gatunków = 70,4% cukru |
| model fenologiczny GDD | RMSE 3,5 dnia (rekonstrukcja, 52 obs. z 7 obszarów); prognoza: 4,4 d na 2 tyg. przed, ~7 d wcześniej |
| stabilność rejonów rzepakowych | r = 0,95 rok-do-roku (GSA), r = 0,89 na 8 lat (EUCROPMAP 2018 ↔ GSA 2026) |
| stabilność pełnej mapy potencjału | r = 0,945 (2025 ↔ 2026), top-10% utrzymane w 71% |
| warstwa lotności | w sezonie 2025 pogoda zabrała 61% potencjału |

## Kolejność uruchamiania

Skrypty zapisują wyniki do `wyniki/*.json`, `*.tif`, `*.npy|npz`; kolejne
czytają z tych plików.

Rdzeń (obszar pilotażowy):

```
python skrypty/fenologia/meteo_gdd.py            # meteo 2000-2026 + wstępna kalibracja progu GDD
python skrypty/detekcja/klasyfikator_gsa.py     # klasyfikator rzepaku na etykietach ARiMR
python skrypty/fenologia/fenologia_gsa.py        # daty kwitnienia z 9 sezonów
python skrypty/fenologia/fenologia_wielo.py      # to samo w 7 obszarach (długie; wznawialne)
python skrypty/fenologia/fenologia_kalibracja.py # wspólna kalibracja bazy i progu GDD
python skrypty/fenologia/fenologia_final.py      # złożenie modelu: baza 1.0, od 1 II, próg 555
python skrypty/potencjal/potencjal_gsa.py        # mapa potencjału pilotażu, kalendarz, dekady
python skrypty/potencjal/lotnosc.py              # warstwa lotności, modulacja pogodowa
```

Województwo:

```
python skrypty/potencjal/wojewodztwo.py            # siatka 100 m, meteo 63 punkty, splot 2025
python skrypty/potencjal/wojewodztwo_sezony.py     # sezon 2026 + średnia + porównanie
python skrypty/kalendarz/wojewodztwo_kalendarz.py  # mapa KIEDY + GDZIE i krzywe kalendarza
python skrypty/potencjal/mapa_wojewodztwa.py       # mapa główna z podkładem OSM
python skrypty/potencjal/mapa_sezonow.py           # średnia dwóch sezonów + mapa zmian
python skrypty/fenologia/mapa_modelu.py            # rysunek samego modelu fenologicznego
python skrypty/fenologia/prognoza_w_sezonie.py     # hindcast prognozy terminu
python skrypty/fenologia/imgw_walidacja.py         # ERA5 vs stacja IMGW Zamość
python skrypty/fenologia/fenologia_sadu.py         # dynamiczne okno jabłoni (kotwiczenie)
```

Teledetekcja (kolejność ważna — każdy czyta wyniki poprzedniego):

```
python skrypty/detekcja/detekcja_wojewodztwo.py   # przedkwitnieniowa detekcja 2025, ~1.5 h GEE
python skrypty/detekcja/teledetekcja_mapy.py      # stara mapa rzepak+łąki (nie kalendarz)
python skrypty/detekcja/mapa_detekcji.py          # detekcja obok deklaracji
python skrypty/detekcja/stabilnosc_rzepaku.py     # EUCROPMAP 2018/2022 + GSA: 8 lat
python skrypty/detekcja/detekcja_lata.py          # pełny klasyfikator na 2019-2025, ~10 h GEE
python skrypty/potencjal/sredni_rok.py             # finał: przeciętny rok + niezawodność
```

Detekcja wielogatunkowa (Sentinel-1 + Sentinel-2) — kolejność obowiązkowa,
każdy krok czyta cache poprzedniego:

```
python skrypty/detekcja/klasyfikator_wielo.py   # próbka 21 tys. działek + cechy S2, ~70 min GEE
python skrypty/detekcja/wielo_diagnoza.py       # scalenie etykiet, miara po agregacji
python skrypty/detekcja/wielo_transfer.py       # ucz 2025 → sprawdź 2026 (sama optyka)
python skrypty/detekcja/wielo_s1s2.py           # czy radar pomaga: S2 vs S1 vs S1+S2
python skrypty/detekcja/transfer_s1s2.py        # przenoszenie z radarem, wybór gatunków
python skrypty/detekcja/wielo_lata.py           # mapy 2019-2024, trening jako zasób GEE
```

Uwaga: `wielo_lata.py` zapisuje model do zasobu
`projects/<projekt>/assets/modele/` — ten katalog trzeba raz utworzyć ręcznie
w Code Editorze (zakładka Assets → NEW → Folder), bo świeży projekt GEE go
nie ma i eksport kończy się błędem „Asset does not exist".

Raport i diagnostyka:

```
python skrypty/raport/raport_buduj.py              # raport.html
python skrypty/kalendarz/eksport_interaktywny.py   # kalendarz.html (satelita = sam rzepak)
python skrypty/detekcja/gee_profil_rzepaku.py   # profile spektralne upraw (Etap 0b)
python skrypty/detekcja/gee_ndyi_przeglad.py    # przegląd diagnostyczny (Etap 0)
python skrypty/detekcja/klasyfikator_fasoli.py  # wynik negatywny: fasola F1 0,69
python skrypty/detekcja/wybor_stacji_rzepak.py  # wybór obszaru pilotażowego (Etap 1)
```

## Wymagania

Środowisko: `C:/Users/kacpe/miniconda3/python.exe` — tam siedzi Earth Engine
razem z geopandas. Domyślny `python` w PATH to inny interpreter i nie ma `ee`.

```
pip install earthengine-api geopandas pyogrio rasterio scipy matplotlib requests
earthengine authenticate
```

ID projektu Earth Engine w pliku `.ee_projekt` obok skryptów.

## Dane wejściowe

| źródło | zakres | skąd |
|---|---|---|
| ARiMR GSA — uprawy | 2025, 2026 | `dane/gsa_lubelskie_*/` — geoportal ARiMR publikuje wyłącznie te dwa roczniki |
| Sentinel-2 | 2018–2026 | Earth Engine; lokalnie tylko wyniki klasyfikacji |
| Sentinel-1 GRD (radar) | 2018–2026 | Earth Engine; tryb IW, orbita zstępująca, VV+VH |
| EUCROPMAP (JRC) | 2018, 2022 | Earth Engine, klasa 232 = rzepak |
| ERA5 przez Open-Meteo | 2000–2026 | pobierane przez `meteo_gdd.py` / `wojewodztwo.py` |
| ESA WorldCover | 2021 | maska gruntów ornych przy klasyfikatorze; łąki nie wchodzą na kalendarz satelitarny |
| OSM (Overpass) | — | podkład kartograficzny, cache `dane/osm_podklad.json` |

Katalog `dane/` (~2 GB po sprzątnięciu zipów) nie jest wersjonowany; shapefile
GSA pobiera się z geoportalu ARiMR („Deklaracje rolne … — uprawy, woj.
lubelskie"). Kosztowne wyniki pośrednie (7 sezonów detekcji `woj_prawd_*.npy`,
~10 h GEE) leżą w `wyniki/` — nie kasować.

## Ograniczenia, o których trzeba pamiętać

- **Deklaracje istnieją tylko za 2025 i 2026** — wieloletniość mapy stoi na
  detekcji satelitarnej rzepaku. W kalendarzu zakładka satelity to sam rzepak
  (łąk WorldCover tam nie ma). Pozostałe gatunki są tylko u rolników.
- **Fenologia jest dynamiczna dla rzepaku (kalibrowana pomiarem) i sadu
  (kotwiczona w literaturze).** Rośliny jare (gryka, słonecznik, fasola…)
  mają stałe daty z konieczności — ich termin zależy od nieznanej daty
  siewu, więc sztywne okno literaturowe jest jedyną uczciwą opcją;
  szerokość czerwcowej przerwy jest przez to częściowo artefaktem.
- **Prognoza terminu ma sens od ~3 tygodni przed kwitnieniem.** Wcześniej model
  nie bije zwykłej średniej wieloletniej — o terminie decyduje kwiecień.
- **Szereg fenologiczny zaczyna się w 2018** (start Sentinela-2); lata
  2000–2017 to ekstrapolacja bez możliwości weryfikacji. MODIS za gruby
  (500 m vs mediana działki 1,16 ha), Landsat za rzadki — sprawdzone oba.
- **„Obserwacje" fenologiczne pochodzą z satelity**, nie z obserwacji BBCH
  w polu. RMSE mierzy zgodność z fenologią teledetekcyjną.
- **Detekcja na pikselach jest słabsza niż na rejonach** (precyzja ~0,7 na
  pikselu 100 m); mapy używają jej wyłącznie po rozmyciu zasięgiem lotu.

## Czego brakuje

Walidacji rzeczywistym zbiorem miodu (największa dziura), konkurencji
istniejących pasiek, detekcji fasoli wielokwiatowej wraz z jej własnym modelem
GDD (wynik negatywny: F1 0,69, myli się z soją i dynią)

