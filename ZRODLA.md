# Źródła parametrów modelu

Każda liczba, która wchodzi do modelu, ma tu wpis: skąd pochodzi, jak została
przeliczona i jak bardzo można jej ufać. Wartości bez źródła są oznaczone
jawnie — nie po to, żeby je ukryć, tylko żeby było widać, gdzie model stoi na
danych, a gdzie na założeniu.

## Klasy wiarygodności

| klasa | co oznacza |
|---|---|
| **A** | badanie naukowe z pomiarem, najlepiej w tym samym regionie |
| **B** | kompilacja branżowa (tabele wydajności miodowych), wartość przeliczona z miodu na cukry |
| **C** | moje założenie, bez źródła |

## Jednostka: kilogramy cukrów, nie miodu

Model liczy w **kilogramach cukrów w nektarze na hektar**. Powód: badania podają
wydajność cukrową, a przelicznik na miód (ok. ×1,25, bo miód to ~80% cukrów)
różni się między źródłami i wprowadza błąd, którego da się uniknąć.

To rozróżnienie już raz uratowało wynik. Portale ogrodnicze podają dla fasoli
wielokwiatowej „200 kg/ha", a badanie mówi o 38–109 kg **cukrów**/ha. Gdyby wziąć
tę pierwszą liczbę bez sprawdzenia, fasola przebiłaby rzepak i cały wniosek
o strukturze pożytku byłby fałszywy.

Wartości klasy B pochodzą z tabel podających **miód** i są dzielone przez 1,25.

## Wydajności pożytkowe

| uprawa | kg cukrów/ha | źródło | klasa |
|---|---|---|---|
| rzepak ozimy | 88 | tabela 80–140 kg miodu/ha, środek 110, ÷1,25. **Podstawa ujednolicona z resztą gatunków** — patrz niżej | B |
| fasola wielokwiatowa | 73 | Kołtowski: **38–109 kg cukrów/ha**. *Pasieka* 3/2005 | **A** |
| gryka zwyczajna | 140 | 100–250 kg miodu/ha | B |
| malina | 160 | 150–250 kg miodu/ha | B |
| koniczyna czerwona | 80 | 50–150 kg miodu/ha (I pokos) | B |
| lucerna | 80 | 50–150 kg miodu/ha | B |
| gorczyca biała | 52 | 40–90 kg miodu/ha | B |
| porzeczka | 36 | 20–70 kg miodu/ha (czarna) | B |
| TUZ (I pokos) | 18 | łąka ok. 40 kg miodu/ha; pastwisko 6. **Wrażliwość zmierzona** — patrz niżej | B |
| TUZ (odrost) | 14 | jw., odrost 45–50 dni po I pokosie, niższa zawartość cukru | B |
| słonecznik | 32 | 30–50 kg miodu/ha | B |
| bobik | 20 | 20–30 kg miodu/ha | B |
| sad | 14 | jabłoń 15–20 kg miodu/ha | B |
| rzepak jary | 56 | **60–80 kg miodu/ha, dwa niezależne źródła** (polskieule, KPODR); kwitnie na przełomie VI/VII | B |
| gorczyca (zbiorcza) | 52 | przyjęto gorczycę białą — dominujący gatunek uprawny; 40–90 kg miodu/ha | B |

**Pożytek zerowy — udokumentowana nieobecność.** Soja zwyczajna, groch
siewny i fasola zwykła (wszystkie klasy deklaracji) są **nieobecne we
wszystkich przeszukanych krajowych kompilacjach wydajności miodowych**
(polskieule.pl, KPODR, kalendarzrolnikow.pl), co jest spójne z ich
samopylnością. Model przyjmuje dla nich pożytek zerowy — to udokumentowany
brak wartości pożytkowej, a nie wartość zmyślona ani luka w danych.
Wcześniejsze robocze oszacowania (4–8 kg, dawna klasa C) usunięto;
odpowiadały za mniej niż 1% cukrów województwa.

## Terminy kwitnienia

**Rzepak ozimy** jest jedyną pozycją, w której termin jest **liczony, a nie
wpisany**. Trzy niezależne przesłanki się zgadzają:

- model GDD (baza 1,0 °C, akumulacja od 1 lutego, próg 555) kalibrowany na
  52 obserwacjach Sentinel-2 z 7 obszarów i 9 sezonów, RMSE 3,5 dnia
- szerokość okna −10 / +12 dni z kształtu zmierzonej krzywej NDYI (2022)
- kontrola: badanie z Puław podaje ~20 dni kwitnienia z początkiem na przełomie
  kwietnia i maja

Pozostałe terminy pochodzą z tabeli branżowej (klasa B) albo są moim
założeniem (C). Zestawienie:

| uprawa | kwitnienie | klasa |
|---|---|---|
| rzepak ozimy | z modelu GDD, inne w każdym roku | **A** |
| sad (jabłoń) | **dynamiczne przez kotwiczenie**: baza 5 °C od 1 I (literatura sadownicza, 41 °F), próg = mediana GDD w dniu literaturowej pełni (5 V) po 27 sezonach; jedyne liczby wejściowe to baza (literatura) i okno z tabeli (B). Kontrola wiarygodności: model daje 11 IV w 2024 (rok rekordowo wczesnego kwitnienia i strat przymrozkowych) i 16 V w zimnym 2021 | B |
| fasola wielokwiatowa | koniec VI – VII, 30–50 dni | **A** |
| porzeczka | 15–30 IV | B |
| malina | 19 V – 8 VI | B |
| gorczyca biała | 1–25 VI | B |
| koniczyna czerwona | 15–28 VI | B |
| bobik | 15 VI – 10 VII | B |
| lucerna | 25 VI – 25 VII | B |
| gryka | 5 VII – 5 VIII | B |
| słonecznik | 10 VII – 20 VIII | B |
| TUZ | V – VIII, założenie własne — ruń jest mieszanką | C |

## Ile wyniku stoi na czym

W najlepszym punkcie sezonowym udziały wynoszą:

| gatunek | kg cukrów/ha | udział w cukrach | klasa źródła |
|---|---|---|---|
| rzepak ozimy | 88 | **50,9%** | B (walidowany badaniem A) |
| TUZ łącznie (2 pokosy) | 18 + 14 | 21,4% | B (wrażliwość zmierzona) |
| malina | 160 | 7,3% | B |
| gryka zwyczajna | 140 | 7,1% | B |
| fasola wielokwiatowa | 73 | 5,9% | **A** |
| porzeczka | 36 | 3,0% | B |
| pozostałe 10 klas | — | 4,4% | B |

Razem **26,0 mln kg cukrów** w skali województwa.

**Udziały wg klasy źródła: A — 5,9%, B — 94,1%, C — 0%.**

Ta proporcja wygląda gorzej niż poprzednia (A — 63,0%) i wymaga wyjaśnienia,
bo zmiana jest **wyłącznie skutkiem ujednolicenia podstawy**, nie utraty
danych. Rzepak — 51% bilansu — miał wcześniej etykietę A, bo brano dla niego
wynik badania nektarowego. Po przeliczeniu na podstawę tabelaryczną nosi
etykietę B, mimo że **badanie nadal istnieje i nadal się z nim zgadza** —
przeszło tylko z roli źródła wartości do roli walidacji.

Innymi słowy: poprzednie 63,0% klasy A było **artefaktem mieszania dwóch
różnych wielkości fizycznych**. Wynik z ujednoliconą podstawą jest słabiej
oznakowany, ale wewnętrznie porównywalny — a mapa służy porównywaniu.

Klasa C zniknęła całkowicie z wydajności. Pozostałe elementy klasy C to
konstrukcje modelowe (rozkład kwitnienia w oknie, kształt indeksu lotności)
— założenia zadeklarowane jawnie, nie liczby udające dane.

## Ujednolicenie podstawy wydajności (rzepak)

Do wersji z sierpnia 2026 rzepak miał wydajność **115 kg cukrów/ha** wziętą
z badania nektarowego spod Puław (12 plantacji, 8 odmian, 80–150 kg cukrów/ha,
*Pasieka* 2/2003). To była jedyna wartość klasy A w całej tabeli — i właśnie
dlatego stanowiła problem.

**Badanie z Puław mierzy PRODUKCJĘ nektaru przez roślinę. Tabele branżowe,
z których pochodzi pozostałe 14 gatunków, podają WYDAJNOŚĆ MIODOWĄ — czyli
to, co pszczelarz realnie odbiera.** Te dwie wielkości nie są tym samym:
druga jest mniejsza o straty odparowania, konkurencję innych zapylaczy
i nektar niezebrany. Mieszanie ich w jednej tabeli zawyżało rzepak o ok. 30%
względem wszystkich pozostałych upraw.

Ponieważ mapa służy **porównywaniu miejsc i gatunków między sobą**, spójność
podstawy jest ważniejsza niż posiadanie jednej wartości klasy A. Przeliczono
więc rzepak na podstawę tabelaryczną: 80–140 kg miodu/ha → środek 110 →
÷1,25 = **88 kg cukrów/ha**.

Badanie z Puław nie znika — **przechodzi z roli źródła do roli walidacji**.
Mierzone 80–150 kg cukrów/ha produkcji pokrywa się z tabelarycznym 64–112
odbioru, co jest zgodne w oczekiwanym kierunku (produkcja > odbiór).

Skutek: udział rzepaku w cukrach województwa spada z **57,6% na 50,9%**.
Wynik jest przez to mniej zdominowany przez jeden gatunek, ale — co ważniejsze
— **ranking miejsc przestaje zależeć od tego, którą uprawę zmierzono lepszą
metodą.**

## Czego nie da się uźródłowić — i co z tym zrobiono

**TUZ** to nie gatunek, tylko klasa użytkowania. Wartość pożytkowa runi zależy
w całości od składu — mniszek, koniczyna biała, chaber — a ten różni się między
działkami i latami. Rozpiętość jest ogromna: **łąka kośna ok. 40 kg miodu/ha,
pastwisko tylko 6**. Żadna pojedyncza liczba nie opisze tego uczciwie, a TUZ
to 21,4% cukrów województwa — czyli druga pozycja w bilansie.

**Zamiast szukać lepszej liczby, zmierzono skutek jej niepewności.** Mapa
została przeliczona dla wartości od pastwiskowej do łąkowej i porównana
z wersją bazową:

| TUZ kg cukrów/ha | udział TUZ w cukrach | korelacja z bazową | wspólne top-10% miejsc |
|---|---|---|---|
| 6 (czyste pastwisko) | 4,8% | **0,966** | **93%** |
| 12 | 9,2% | 0,980 | 94% |
| 20 | 14,5% | 0,993 | 95% |
| 26 | 18,1% | 0,998 | 97% |
| 32 (bazowa) | 21,4% | 1,000 | 100% |
| 40 (czysta łąka) | 25,4% | 0,997 | 95% |

**Nawet pięciokrotna zmiana wartości TUZ — z 32 na 6 — zostawia 93%
najlepszych rejonów tam, gdzie były, przy korelacji map 0,966.**

Odtwarzalne: `python skrypty/potencjal/wrazliwosc_tuz.py`

Powód jest geometryczny: łąki są rozłożone po województwie stosunkowo
równomiernie, więc zmiana ich wydajności **przesuwa całe tło w górę albo
w dół, nie tworząc ani nie likwidując żadnego zagłębia pożytkowego**.
Bezwzględne kilogramy zależą od tej liczby silnie; ranking miejsc — prawie
wcale.

Dlatego TUZ raportujemy **jako zakres z wykazaną odpornością rankingu**,
a nie jako parametr o udawanej precyzji. To jest właściwa odpowiedź na
wielkość, której posiadanymi danymi uściślić się nie da.

## Pozostałe parametry modelu

| parametr | wartość | źródło | klasa |
|---|---|---|---|
| baza GDD | 1,0 °C | **kalibracja łączna bazy i progu** na 52 obserwacjach z 7 obszarów; literaturowa baza 4 °C daje RMSE o 38% gorsze | **A** |
| próg GDD | 555 | jw. — minimalizacja RMSE po siatce baza × próg | **A** |
| λ zaniku odległościowego | 1000 m | Couvillon i in. (PLOS ONE 2014), odczyt 5 tys. tańców pszczelich: średni dystans lotu **wiosną 493 m**, latem 2156 m, jesienią 1275 m | B |
| zasięg lotu | 3000 m | jw.; Beekman i Ratnieks (Functional Ecology 2000) notują medianę **6,1 km** przy wrzosie w sierpniu | B |
| bazy temperaturowe GDD | patrz niżej | osobna tabela — każda z odsyłaczem | B |

**Zasięg lotu: jądro jest dobrane pod wiosnę i zaniża lato.** Zmierzone
średnie dystanse lotu są silnie sezonowe: wiosną 493 m, latem **2156 m**.
Nasze λ = 1 km z obcięciem na 3 km dobrze opisuje wiosnę, czyli okres
rzepaku (57% cukrów) — ale dla pożytków lipcowych i sierpniowych **obcina
realny zasięg zbioru**. Pszczoły latem latają dalej, bo w krajobrazie jest
mniej kwiatów. Poprawne rozwiązanie to jądro zmienne sezonowo; obecna wersja
jest uproszczeniem na korzyść wiosny i tak należy ją opisać.

### Bazy temperaturowe modeli fenologicznych

| gatunek | baza | źródło |
|---|---|---|
| rzepak ozimy | **1,0 °C** | **kalibracja własna** na 52 obserwacjach Sentinel-2 | 
| gryka | 5,0 °C | modele fenologiczne *Fagopyrum esculentum*, *Agricultural Systems* 1998 |
| słonecznik | 6,7 °C | NDAWN/NDSU, *Sunflower Growing Degree Days* (44 °F) |
| pozostałe (malina, porzeczka, sad, TUZ, motylkowe, gorczyca, bobik, fasola) | 5,0 °C | badania nad bazą termiczną roślin sadowniczych strefy umiarkowanej: **Tb zależy od genotypu i mieści się w 2,1–8,2 °C** (odmiany wczesne 2,1–4,4, późne 4,3–8,2); modele kwitnienia jabłoni używają 4,5 i 6,11 °C. Przyjęto 5,0 °C jako środek udokumentowanego zakresu |

**Uwaga metodyczna do bazy 5 °C.** Literatura nie podaje jednej wartości dla
tych gatunków, bo **baza termiczna zależy od odmiany** — im wyższe wymagania
chłodowe, tym wyższa Tb. Nie istnieje więc „prawidłowa" liczba do znalezienia;
istnieje udokumentowany przedział, a każdy wybór wewnątrz niego jest
przybliżeniem. Dlatego zamiast szukać dalej zmierzono, ile ten wybór kosztuje
(niżej).

**Ile kosztuje ta niepewność — pomiar, nie przypuszczenie.** Dla ośmiu
gatunków bez źródła gatunkowego przeliczono model przy bazie 3, 5 i 7 °C.
Terminy różnią się **średnio o 2,7 dnia, maksymalnie o 10**, a rozrzut
międzyroczny o 3–4 dni. Powód jest strukturalny: przy kotwiczeniu podniesienie
bazy obniża próg, więc obie zmiany prawie się znoszą, a mediana pozostaje
poprawna z definicji. Baza wpływa wyłącznie na amplitudę wahań. Niepewność
z tego tytułu jest więc porównywalna z błędem najlepszego modelu w projekcie
(rzepak, 3,5 dnia) — istotna, ale nie podważająca wyniku.

**Ostrzeżenie z własnego doświadczenia.** Pierwsza wersja tego modelu miała
bazy 10 °C dla „ciepłolubnych" i 5 °C dla reszty, opatrzone komentarzem
„wartości standardowe w agrometeo" — bez odsyłacza. Sprawdzenie w literaturze
obaliło obie: gryka ma 5 °C, słonecznik 6,7 °C. Zawyżona baza sztucznie
wyolbrzymiała wahania międzyroczne gryki (39 dni zamiast 28). To jest wprost
argument za tym, żeby żadnej liczby nie przyjmować „bo brzmi rozsądnie".
| kształt kwitnienia | −10 / +12 dni | pomiar własny z Sentinel-2 | **A** |

## Detekcja rzepaku (Sentinel-2)

| parametr | wartość | źródło | klasa |
|---|---|---|---|
| etykiety treningowe | ARiMR GSA 2025, działki z buforem −10 m | rejestr administracyjny — rolnik wie, co posiał | **A** |
| cechy (8 okien anomalii) | jesień/marzec/kwitnienie/czerwiec | dobór z **własnych profili spektralnych** upraw (`json/profil_2022.json`) | **A** |
| klasyfikator | Random Forest, 150 drzew | wybór standardowy; bez strojenia hiperparametrów | B |
| walidacja przestrzenna | bloki 2,5 km, test ważony powierzchnią | pomiar własny: F1 0,90 (pełny), 0,84 (przedkwitnieniowy) | **A** |
| próg decyzji | 0,53 (pełny) / 0,65 (przedkwit.) | **kalibracja arealna** do 150,6 tys. ha GSA 2025 | **A** |
| przenośność międzyroczna | r = 0,95 z EUCROPMAP 2022; r = 0,97 z GSA 2025 (po splocie 3 km) | pomiar własny | **A** |

Trening jest zrównoważony 50/50, więc surowe prawdopodobieństwa są zawyżone —
dlatego próg musi być kalibrowany arealnie, a nie brany jako 0,5. Pierwsza
wersja bez tej kalibracji wykrywała 9× za dużo rzepaku.

## Detekcja wielogatunkowa (Sentinel-1 + Sentinel-2)

| parametr | wartość | źródło / uzasadnienie | klasa |
|---|---|---|---|
| etykiety | GSA 2025, 21 tys. działek, 12 klas | rejestr ARiMR | **A** |
| cechy | kompozyty półmiesięczne IX→IX: NDVI i NDYI (anomalie) + VV, VH, VH−VV (dB) | konstrukcja własna; dobór 40 z 130 wg ważności | **A** |
| Sentinel-1 | tryb IW, orbita zstępująca | mieszanie orbit wprowadza sztuczną zmienność kąta padania | B |
| las losowy | 200 drzew, maks. 500 liści | limit wymuszony pamięcią GEE; koszt zmierzony: −0,005 w średnim r | **A** |

**Co wnosi radar (pomiar własny).** Sam Sentinel-2 daje F1-makro 0,683, sam
Sentinel-1 0,585, oba razem **0,718**. Cechy radarowe odpowiadają za **52,9%**
ważności modelu. Kluczowa przewaga: **0 pustych okien** wobec 8 u optyki — nad
Lubelszczyzną w I połowie stycznia 100% punktów nie ma ani jednej bezchmurnej
sceny, w II połowie lutego 59%. Największy zysk na użytkach zielonych
(r 0,658 → 0,850), bo radar widzi pokosy i strukturę runi.

**Przenoszenie na inny rok** (ucz 2025 → sprawdź 2026, `transfer_s1s2.json`).
Miarą jest korelacja po splocie jądrem 3 km, porównana z odniesieniem
„rosło tam, gdzie rok temu":

| gatunek | model | odniesienie | wniosek |
|---|---|---|---|
| rzepak ozimy | **0,958** | 0,338 | detekcja niezbędna — rzepak wędruje w płodozmianie |
| gryka | 0,859 | 0,750 | detekcja wnosi |
| malina | 0,878 | 0,847 | detekcja wnosi nieznacznie |
| słonecznik | 0,850 | 0,814 | detekcja wnosi nieznacznie |
| fasola wielokwiatowa | 0,880 | **0,949** | pamięć lepsza — uprawa specjalistyczna, te same pola |
| użytki zielone, porzeczka, motylkowe, sad | < próg | wyższe | uprawy trwałe: pamięć jest metodą **poprawną** |

Stąd podział warstw: cztery pierwsze gatunki (70,4% cukrów) odtwarzane są ze
zdjęć wstecz, reszta brana z deklaracji. Każda warstwa ma więc uzasadnienie
pomiarowe, a nie założeniowe.

**Ograniczenie.** Test przenoszenia oparty jest na jednej parze lat, przy tym
2025 i 2026 różnią się fenologicznie tylko o 3 dni, a sezon 2026 jest niepełny
(brak września — wypadło 24 z 52 okien optycznych). Po żniwach 2026 test należy
powtórzyć na pełnym zestawie.

## Założenia konstrukcyjne modeli — audyt

Dotąd dokumentowane były **liczby**. Poniżej założenia wbudowane w samą
budowę modeli. Są istotniejsze, bo liczbę da się poprawić, a założenie
przenika cały wynik.

### 1–2. Jarowizacja i górny próg — SPRAWDZONE, nie założone

Model termiczny jest jednofazowy (samo ciepło, bez fazy chłodowej) i nie ma
górnego ograniczenia temperatury. Oba uproszczenia **przetestowano na 52
zmierzonych datach kwitnienia**, z osobną kalibracją progu dla każdego
wariantu (`fenologia_warianty.py`):

| wariant | RMSE | zmiana |
|---|---|---|
| **podstawowy** | **3,48 d** | — |
| + górny próg 25 / 28 / 30 °C | 3,48 d | **0,00** |
| + jarowizacja, 20 dni chłodu | 3,96 d | +0,49 |
| + jarowizacja, 40 dni chłodu | 6,09 d | +2,61 |

**Górny próg nie zmienia nic**, bo rzepak kwitnie przed falami upałów —
średnie dobowe przed kwitnieniem rzadko przekraczają 25 °C, więc ścinanie
dotyczy wartości, których nie ma.

**Jarowizacja pogarsza wynik.** Przy wymaganiu 40 dni chłodu siedem z 52
sezonów nie dostaje prognozy w ogóle, choć rzepak w nich kwitł normalnie:
zimy w Lubelskiem spełniają wymaganie chłodowe z dużym zapasem, więc faza
chłodowa nic nie wnosi, a wprowadza sztuczne opóźnienie startu.

**Zastrzeżenie:** wynik obowiązuje dla obecnego klimatu Lubelszczyzny.
W cieplejszym klimacie lub regionie o łagodniejszych zimach jarowizacja
zacznie mieć znaczenie i test należy powtórzyć. Górny próg warto sprawdzić
osobno dla gryki i słonecznika, które kwitną w lipcu i sierpniu.

### 3. Jądro zasięgu lotu jest izotropowe i stałe

Zakładamy, że pszczoła lata jednakowo we wszystkich kierunkach i że zasięg
jest ten sam przez cały sezon. Oba założenia są fałszywe:
- **kierunek** — rzeki, lasy i zabudowa zmieniają rozkład lotów
- **sezon** — zmierzone średnie dystanse to 493 m wiosną i 2156 m latem
  (Couvillon i in. 2014), czyli czterokrotna różnica

### 4. Brak nasycenia — najważniejsze założenie całej mapy

Mapa sumuje cukier liniowo: 20 ton w zasięgu lotu to dwa razy więcej niż
10 ton. **Ale jedna rodzina pszczela zbierze najwyżej kilkadziesiąt
kilogramów miodu**, niezależnie od tego, czy w zasięgu jest 10 czy 20 ton.

Skutek: **mapa poprawnie porządkuje miejsca słabe i średnie, ale w górnym
zakresie różnice przestają mieć znaczenie praktyczne.** Powyżej pewnego
poziomu ograniczeniem jest siła rodziny, a nie pożytek.

### 5. Potencjał to nie jest nektar zebrany

Harris i in. (*Ecology and Evolution* 2024) wykazali, że **większość nektaru
wytworzonego przez rzepak pozostaje niezebrana** przez owady. Nasza mapa
liczy produkcję rośliny, nie pobór — a między nimi jest duża i zmienna
strata. To kolejny powód, by traktować wynik jako ranking miejsc, a nie
prognozę kilogramów.

### 6. Kalibracja arealna zakłada równomierność błędu

Współczynniki korekty wyliczone na 2025 nakładamy na wszystkie lata,
zakładając, że model myli się tak samo w całym województwie i w każdym
sezonie. Uzasadnienie: korelacja układu przestrzennego 0,85–0,96 w teście
przenoszenia. Wykryta granica tego założenia: **malina**, gdzie areał po
korekcie skacze siedmiokrotnie między latami — dlatego została przeniesiona
do warstwy deklaracyjnej.

## Walidacja fenologii na obserwacjach polowych IMGW

Czternaście z piętnastu modeli fenologicznych było **kotwiczonych** — mediana
trafiała w datę z tabeli z definicji, ale amplituda wahań międzyrocznych
pozostawała założeniem bez pokrycia.

IMGW-PIB prowadzi od 2007 roku obserwacje fitofenologiczne na **51 stacjach
synoptycznych** i publikuje mapy dat początku fenologicznych pór roku. Pora
**„lato" jest zdefiniowana zakwitaniem lipy drobnolistnej** (*Tilia cordata*
Mill.) — czyli dokładnie gatunku, który modelujemy dla warstwy leśnej.

Odczytano pasma dla Lubelszczyzny z pięciu roczników:

| rok | model | IMGW | różnica |
|---|---|---|---|
| 2010 | 30 VI | 21–30 VI | +5 d |
| 2018 | 13 VI | 11–20 VI | −2 d |
| 2019 | 22 VI | 21–30 VI | −3 d |
| 2021 | 6 VII | 1–10 VII | **+1 d** |
| 2024 | 18 VI | 11–20 VI | +3 d |

**Błąd średni +0,8 d, bezwzględny 2,8 d** — lepiej niż model rzepaku (3,5 d),
i to wobec obserwacji polowych, a nie własnych pomiarów satelitarnych.

**Korekta wykonana na podstawie tej walidacji.** Pierwotna kotwica (25 VI,
środek pasma mapy średniej) dawała systematyczne wyprzedzenie o **−6,2 dnia**
na wszystkich pięciu rocznikach. Przesunięto ją o zmierzony błąd na 2 VII,
po czym obciążenie spadło do +0,8 d. To jest zamiana założenia na wartość
wyznaczoną pomiarem.

**Co to potwierdza poza samą lipą:** kolejność lat i amplituda zgadzały się
już przed korektą (model 24 dni rozpiętości, obserwacje 20). Metoda
kotwiczenia poprawnie odtwarza **reakcję rośliny na pogodę** — myliła się
tylko o stałą. To uwiarygadnia pozostałe modele kotwiczone, choć nie zastępuje
ich walidacji.

**Ograniczenie:** daty odczytywane wzrokowo z map rastrowych o legendzie
dziesięciodniowej, przyjmowano środek pasma — stąd nieusuwalna niepewność
±5 dni. Pozostałe 14 roczników leży w `dane/imgw_fenologia/` i czeka na
odczytanie. Mapy pobiera `walidacja_imgw_pory.py`.

## Zewnętrzne potwierdzenie czerwcowej przerwy

Kalendarz pożytku pokazuje wyraźny niedobór na przełomie maja i czerwca,
po przekwitnięciu rzepaku. Podejrzewaliśmy, że jego szerokość jest częściowo
artefaktem sztywnych dat pozostałych gatunków.

**Timberlake i in.** (*Journal of Applied Ecology* 2019), na podstawie
pomiarów terenowych nektarowania w krajobrazie rolniczym, opisują dokładnie
ten sam wzór: **dwa szczyty — maj i lipiec — a między nimi „June Gap"**,
oraz dodatkowe niedobory w marcu i na przełomie sierpnia i września.

To jest niezależne potwierdzenie z innych danych, innej metody (GAM na
pomiarach polowych) i innego kraju. Zjawisko jest realne, a nie wytworzone
przez nasze uproszczenia. Praca ta podaje też, że **trwałe użytki zielone
i lasy dają największy udział nektaru ze względu na powierzchnię** — co
zgadza się z pozycją TUZ w naszym bilansie (18,4% cukrów).

## Zewnętrzne mapy referencyjne

| mapa | rola w projekcie | wiarygodność | klasa |
|---|---|---|---|
| ARiMR GSA 2025, 2026 | etykiety treningu, prawda dla walidacji, warstwa upraw | rejestr dopłat; publikowane są wyłącznie te dwa roczniki | **A** |
| EUCROPMAP 2018, 2022 (JRC) | stabilność rejonów na 8 lat, walidacja międzyroczna | mapa z Sentinela-1, 10 m; dokładność dla rzepaku ok. 80% (d'Andrimont i in. 2021) | B |
| ESA WorldCover v200 (2021) | maska gruntów ornych (kl. 40) przy klasyfikatorze; użytki zielone (kl. 30) tylko na starej mapie teledetekcyjnej — nie na kalendarzu satelitarnym | dokładność globalna ~76% | B |

Korelacje liczone względem EUCROPMAP mieszają realną zmianę z błędem tej mapy —
są **dolnym oszacowaniem** zgodności.

## Meteo

| parametr | wartość | źródło | klasa |
|---|---|---|---|
| dane dobowe i godzinowe | ERA5 (reanaliza ~10 km) przez Open-Meteo | 2000–2026; dla województwa siatka 63 punktów co 25 km | B |
| GDD | max((Tmax+Tmin)/2 − baza, 0) | definicja standardowa | — |

**Walidacja wobec stacji IMGW Zamość (kod 595), 2018–2025, II–V, 962 dni:**
błąd średni **+0,10 K**, RMSE dobowe 1,13 K, r = 0,986. Termin kwitnienia
liczony z obu źródeł różni się średnio o −0,5 dnia; w 6 z 8 lat o ≤1 dzień
(maks. 5 dni w 2020 — płaski przebieg akumulacji przy progu). Różnice są
wyraźnie poniżej błędu modelu (3,5 dnia) — reanaliza jest równoważnym
źródłem temperatur dla tego zastosowania. Skrypt: `imgw_walidacja.py`,
wynik: `json/imgw_walidacja.json`, wykres: `mapy/wykres_imgw.png`.

## Warunki lotu pszczół

| parametr | wartość | źródło | klasa |
|---|---|---|---|
| temperatura startu lotów | 10 °C | **Woyke (2003)**: przy 10 °C najczęściej zaczyna się zbieranie pokarmu; liczba zbieraczek rośnie **dziesięciokrotnie przy 12 °C** | B |
| optimum aktywności | 20 °C | Woyke (2003): największa aktywność lotna | B |
| wiatr: ograniczenie / stop | 5 / 8,3 m/s (30 km/h) | jw. | B |
| opad, noc | wykluczają loty | jw. | B |
| indeks efektywności (ważenie godzin) | pełna przy 20 °C i bezwietrznie, malejąca ku progom | metoda zgodna z **BEEHAVE** (Becher i in. 2014) — kanonicznym modelem rodziny pszczelej: godzinowa pogoda → godziny lotne wg progów → agregacja dobowa | B |

**Progi wiatru — poprawione na wartości z BEEHAVE.** Pierwotnie stało tu
8,3 m/s (30 km/h) z opracowań wtórnych, czyli dwukrotnie liberalniej niż
w modelu źródłowym. Po zmianie na **4,2 m/s (15 km/h)** średnia sprawność
lotna sezonu 2025 spadła z 0,390 na **0,370** — zmiana o 5%, mniejsza niż
się spodziewano, bo wiatr powyżej tego progu nie jest nad Lubelszczyzną
częsty.

Pozostaje jedna drobna rozbieżność: BEEHAVE podaje optimum termiczne jako
**plateau 20–30 °C**, u nas jest to punkt 20 °C z opadaniem powyżej. Wpływ
jest mały, bo temperatur powyżej 25 °C w godzinach lotnych jest niewiele,
ale wart odnotowania.

Progi cytowane z opracowań wtórnych — bez odsyłacza do pracy pierwotnej Woykego.

## Prognoza terminu w trakcie sezonu

Hindcast: do dnia decyzji rzeczywiste GDD, dalej średnia wieloletnia dobowa.
Pomiar własny na 52 obserwacjach (klasa **A**): RMSE 6,9–7,4 dnia przy decyzji
przed 15 IV, 6,0 przy 15 IV, 4,4 przy 1 V; odniesienie „zawsze średnia" 7,3.
Wniosek: model prognostycznie użyteczny od ~3 tygodni przed kwitnieniem.

## Kalendarz dekadowy i mapa przeciętnego roku

| element | konstrukcja | klasa |
|---|---|---|
| rozkład cukru w oknie kwitnienia | trójkątny: narastanie do pełni, spadek do końca | **B — sprawdzony na zmierzonej krzywej NDYI rzepaku** (patrz niżej); opisaną alternatywą są uogólnione modele addytywne (GAM) dopasowane do pomiarów terenowych (Timberlake i in. 2019) |

**Kontrola kształtu trójkąta na pomiarze.** Krzywe NDYI z 9 sezonów
wyrównano względem własnego szczytu i porównano z trójkątem −10/+12:

| dni od szczytu | zmierzony | trójkąt |
|---|---|---|
| −12 | 0,00 | 0,00 |
| −5 | **0,49** | **0,50** |
| 0 | 1,00 | 1,00 |
| +13 | 0,45 | 0,00 |
| +15 | 0,40 | 0,00 |

**Narastanie odtworzone niemal dokładnie.** Ogon po szczycie jest w pomiarze
dłuższy, ale najprawdopodobniej nie są to kwiaty: po opadnięciu płatków łan
pozostaje żółtozielony, więc NDYI opada powoli — mierzymy resztkowy kolor.
Rozstrzyga literatura: badanie z Puław podaje ~20 dni kwitnienia, a nasze
okno ma 22 dni; dłuższy ogon (28 dni) przekraczałby pomiar polowy. Przy
+13 i +15 dniu dostępne są zresztą tylko 3–4 obserwacje.
| szerokość okna rzepaku | mediana połowy szczytu NDYI 2018–2026; ramie bez przelotu (luka >12 dni) odpada | A — ten sam sygnał co data pełni, wiele lat zamiast 2022 |
| termin rzepaku na mapie | grupy po 4 dni wg lokalnej daty GDD | techniczne |
| przeciętny rok | rzepak z 8 sezonów (detekcja 2019–24 + GSA 2025–26); pozostałe gatunki jako warstwa stała ze średniej deklaracji | uzasadnienie: pełne mapy 2025/2026 korelują r = 0,945 |
| niezawodność | liczba sezonów w najlepszych 20% warstwy rzepakowej | definicja własna |

## Odsyłacze

- Obfitość nektarowania rzepaku ozimego, *Pasieka* 2/2003 —
  https://pasieka24.pl/index.php/pl-pl/pasieka-czasopismo-dla-pszczelarzy/104-pasieka-2-2003/1258-pszszczoy-na-rzepaku-obfito-nektarowania-rzepaku-ozimego
- Kołtowski, wartość fasoli wielokwiatowej dla pszczół, *Pasieka* 3/2005 —
  https://pasieka24.pl/index.php/pl-pl/pasieka-czasopismo-dla-pszczelarzy/86-pasieka-3-2005/914-jaka-wartosc-dla-pszczol-ma-fasola-wielokwiatowa-phaseolus-coccineus-l
- Tabela wydajności miodowych roślin — https://polskieule.pl/wydajnosc-miodowa-roslin/
- Miododajne rośliny rolnicze, KPODR Minikowo —
  https://technologia.kpodr.pl/index.php/2012/04/06/miododajne-rosliny-rolnicze/
- Łąki i pastwiska jako pożytki pszczele — https://ekobartnik.pl/ekologiczne-pozytki-pszczele
- Rzepak jako roślina miododajna, Portal Pszczelarski —
  https://www.portalpszczelarski.pl/artykul/384-rzepak-roslina-miododajna
- d'Andrimont R. i in., *From parcel to continental scale — a first European
  crop type map based on Sentinel-1* (EUCROPMAP), Remote Sensing of
  Environment 266, 2021 — https://doi.org/10.1016/j.rse.2021.112708
- ESA WorldCover v200 —
  https://esa-worldcover.org / zbiór GEE `ESA/WorldCover/v200`
- Sentinel-1 GRD (radar C-band) — zbiór GEE `COPERNICUS/S1_GRD`;
  dokumentacja misji: https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-1
- Open-Meteo (ERA5, archiwum + prognoza) — https://open-meteo.com/
- Geoportal ARiMR, deklaracje GSA —
  https://geoportal.arimr.gov.pl/ (pozycje „Deklaracje rolne … — uprawy")
- Bank Danych o Lasach (skład gatunkowy wydzieleń) —
  https://www.bdl.lasy.gov.pl/
- Couvillon M.J., Schürch R., Ratnieks F.L.W., *Waggle Dance Distances as
  Integrative Indicators of Seasonal Foraging Challenges*, PLOS ONE 9(4),
  2014 — https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0093495
- Beekman M., Ratnieks F.L.W., *Long-range foraging by the honey-bee,
  Apis mellifera L.*, Functional Ecology 14, 2000 —
  https://besjournals.onlinelibrary.wiley.com/doi/10.1046/j.1365-2435.2000.00443.x
- NDAWN/NDSU, *Sunflower Development and Growing Degree Days* —
  https://ndawn.ndsu.nodak.edu/help-sunflower-growing-degree-days.html
- Model fenologiczny gryki (*Fagopyrum esculentum*), Agricultural Systems
  59(2), 1998 — https://www.sciencedirect.com/science/article/abs/pii/S0308521X98000079
- **Kołtowski Z., Miśkiewicz I., *Wielki atlas roślin miododajnych*,
  Przedsiębiorstwo Wydawnicze Rzeczpospolita, Warszawa 2006** — źródło
  pierwotne wydajności miodowych klasy B; katalog:
  https://biblioteka.botany.pl/bib/572
- Woyke J. (2003), badania nad temperaturą a aktywnością lotną pszczół —
  omówienie: https://www.pasieka24.pl/index.php/pl-pl/pasieka-czasopismo-dla-pszczelarzy/155-pasieka-6-2017/1737-10-temperatura-a-rozwoj-pszczol
- Baza termiczna roślin sadowniczych strefy umiarkowanej (zależność od
  genotypu, zakres 2,1–8,2 °C), Semina: Ciências Agrárias —
  https://ojs.uel.br/revistas/uel/index.php/semagrarias/article/view/21946
- **Becher M.A. i in., *BEEHAVE: a systems model of honeybee colony dynamics
  and foraging***, Journal of Applied Ecology 51, 2014 — kanoniczny model
  rodziny pszczelej; źródło metody liczenia godzin lotnych —
  https://besjournals.onlinelibrary.wiley.com/doi/10.1111/1365-2664.12222
- **Harris C. i in., *Floral resource wastage: Most nectar produced by the
  mass-flowering crop oilseed rape (Brassica napus) is uncollected by
  flower-visiting insects***, Ecology and Evolution 14, 2024 — podstawa
  zastrzeżenia, że potencjal to nie jest nektar zebrany —
  https://onlinelibrary.wiley.com/doi/10.1002/ece3.11453
- **Timberlake T.P., Vaughan I.P., Memmott J., *Phenology of farmland floral
  resources reveals seasonal gaps in nectar availability for bumblebees***,
  Journal of Applied Ecology 56, 2019 — pomiary terenowe nektarowania,
  metoda GAM, niezależne potwierdzenie „June Gap" —
  https://besjournals.onlinelibrary.wiley.com/doi/10.1111/1365-2664.13403

**Źródło pierwotne wartości klasy B — zidentyfikowane.** Tabele branżowe, z
których korzystamy, wywodzą się z: **Kołtowski Z., Miśkiewicz I., *Wielki
atlas roślin miododajnych*, Przedsiębiorstwo Wydawnicze Rzeczpospolita,
Warszawa 2006.** Kontrola zgodności na malinie: atlas podaje ~200 kg miodu/ha,
co po przeliczeniu (÷1,25) daje 160 kg cukrów/ha — **dokładnie wartość użytą
w modelu**. To potwierdza, że tabele wtórne wiernie oddają atlas.

Pozostaje zastrzeżenie formalne: wartości odczytano z kompilacji, nie wprost
z atlasu. Do pracy dyplomowej należy zacytować atlas jako źródło i — jeśli
jest dostępny — zweryfikować w nim pozostałe gatunki, tak jak zrobiono to
z maliną.


## Normalizacja jądra zasięgu lotu — zastrzeżenie znalezione i zamknięte

Po wprowadzeniu jąder sezonowych (dystanse lotu z Couvillon i in. 2014)
okazało się, że jądra **nie były normalizowane**, a ich sumy różnią się
drastycznie, bo szersze jądro obejmuje po prostu więcej pikseli:

| pora | λ | zasięg | suma jądra | względem wiosny |
|---|---|---|---|---|
| wiosna | 294 m | 1178 m | 50 | 1,0× |
| lato | 1285 m | 5142 m | 943 | **19,0×** |
| jesień | 760 m | 3041 m | 330 | 6,7× |

Splot nienormalizowany przenosił tę różnicę wprost do wyniku: **hektar
pożytku letniego wchodził do sumy 19 razy mocniej niż hektar wiosennego** —
z geometrii, nie z biologii.

**Dowód, że to błąd, a nie kwestia interpretacji.** Przy surowym jądrze
rzepak (150 626 ha, największa pozycja bilansu, 50,9% cukrów województwa)
dawał na mapie **8,8%**, a gryka — mająca **jedenaście razy mniej
powierzchni** — dawała **23,5%**. Po normalizacji udziały odtwarzają bilans
z hektarów i wydajności co do dziesiątej części punktu:

| gatunek | z hektarów × wydajność | mapa surowa | mapa znormalizowana |
|---|---|---|---|
| rzepak ozimy | 50,9% | 8,8% | **51,0%** |
| TUZ (I pokos) | 12,0% | 2,1% | **12,0%** |
| TUZ (odrost) | 9,4% | 30,9% | **9,3%** |
| malina | 7,3% | 1,3% | **7,3%** |
| gryka zwyczajna | 7,1% | 23,5% | **7,1%** |
| fasola wielokwiatowa | 5,9% | 19,5% | **5,9%** |

Rzecz jest tym bardziej odwrotna, że **pszczoły latają latem dalej właśnie
dlatego, że kwiatów jest mniej** — to jest wniosek samego badania Couvillon.
Surowe jądro premiowało więc niedobór: im rzadszy pożytek, tym szersze
jądro, tym wyższy wynik. Błędne koło.

Skala rozjazdu między wariantami: **korelacja 0,612, wspólne tylko 37%
najlepszych miejsc** — czyli była to różnica przestawiająca ranking, a nie
kosmetyka. Dla porównania: niepewność TUZ, opisana wyżej, daje korelację
0,966.

**Przyjęto wariant znormalizowany** (suma jądra = 1), przeskalowany przez
stałą sumę jądra odniesienia (λ = 1000 m, zasięg 3000 m — jądro używane
w projekcie wcześniej), żeby jednostki i rzędy wielkości pozostały zgodne
z wcześniejszymi etapami, w tym ze sprawdzianem GUS. Zmierzony dystans lotu
nadal steruje **szerokością** rozmycia pożytku; traci wyłącznie
nieuzasadnioną premię za samą szerokość.

Odtwarzalne: `python skrypty/potencjal/wrazliwosc_jadra.py`

**Uwaga metodyczna.** Błąd był niewidoczny gołym okiem — mapa wyglądała
sensownie w obu wariantach. Wykrył go dopiero pomiar zażądany zamiast
przyjęcia założenia. To samo dotyczy zgubionego drugiego pokosu TUZ (9,4%
cukrów znikało po cichu, bo pętla sumująca szła po cache zamiast po liście
pożytków). W obu miejscach dodano strażniki, które teraz przerywają
liczenie zamiast produkować wiarygodnie wyglądający wynik.

## Co seria wieloletnia 2019–2025 może twierdzić, a czego nie

Detekcja policzyła się dla siedmiu sezonów (2019–2025), bez restartu.
Po kalibracji areałowej wyniki wyglądają tak:

| gatunek | min ha | max ha | rozpiętość | zmienność | typ rośliny |
|---|---|---|---|---|---|
| rzepak ozimy | 133 178 | 150 649 | 1,1× | **5%** | jednoroczna |
| słonecznik | 2 416 | 8 829 | 3,7× | 38% | jednoroczna |
| gryka zwyczajna | 2 333 | 28 757 | 12,3× | 59% | jednoroczna |
| malina | 1 537 | 23 252 | **15,1×** | **95%** | **WIELOLETNIA** |

**Malina rozstrzyga sprawę i nie potrzeba do tego żadnego źródła
zewnętrznego.** Malina to krzew wieloletni: plantacja wchodzi w pełnię
owocowania po 2–3 latach i użytkuje się ją około dekady. Areał maliny
**fizycznie nie może** zmienić się piętnastokrotnie z roku na rok. Skoro
wykryty się zmienia, to znaczy, że **międzyroczna zmienność w tej serii
jest szumem klasyfikacji, a nie rolnictwem.**

Ten test jest samowystarczalny — nie opiera się na porównaniu z niczym,
tylko na biologii gatunku. A ponieważ malina wykrywana jest tą samą metodą
co gryka i słonecznik, ogranicza zaufanie także do ich serii rocznych.

**Wniosek dla pracy — deklarowany wprost:**

- **Rzepak: seria wieloletnia jest wiarygodna.** 5% zmienności, rozpiętość
  1,1×, a do tego niezależne potwierdzenie: EUCROPMAP dla 2022 podaje
  147 701 ha wobec naszych 138 518 ha (**−6%**). To jedyny gatunek, dla
  którego wolno pokazywać wykres „areał w latach".
- **Pozostałe gatunki: wolno podawać wyłącznie rozkład przestrzenny
  w sezonie 2025**, gdzie mamy deklaracje GSA jako wzorzec. Ich areałów
  rocznych dla lat 2019–2024 **nie wolno przedstawiać jako pomiaru zmian
  w rolnictwie.**

To ograniczenie jest zgodne z wcześniejszym testem przenoszenia
(rozdział o transferze S1+S2): korelacja układu przestrzennego wychodziła
0,85–0,96, czyli model trafia GDZIE rośnie dany gatunek, a myli się ILE
go jest. Kalibracja areałowa naprawia poziom w roku wzorcowym, ale nie
tworzy informacji o latach, w których wzorca nie ma.

## Sprawdzian GUS — poprawiony i domknięty przedziałem

Łańcuch od mapy do miodu zaczyna się od nektaru **wytworzonego** i mnoży
przez 31% faktycznie zebranego (Harris i in. 2024). Było to poprawne,
dopóki rzepak miał wydajność z badania nektarowego (115 kg/ha), bo tamta
liczba mierzy produkcję rośliny.

Po ujednoliceniu podstawy (115 → 88 kg/ha) mapa stoi na tabelach
branżowych, a te podają **wydajność miodową — już po stratach**. Mnożenie
przez 0,31 odejmowałoby straty drugi raz.

**Ale odwrotne założenie też nie jest pewne**: polskie tabele „wydajności
miodowej" opisują raczej potencjał hektara przy dobrej obsadzie rodzin niż
średni realny zbiór. Posiadanymi danymi nie da się tego rozstrzygnąć,
więc skrypt **nie wybiera wygodnego odczytu, tylko liczy oba**:

| odczyt | założenie | wynik |
|---|---|---|
| A | mapa = produkcja nektaru, ×31% (Harris) | 6,5 tys. ton miodu |
| B | mapa = wydajność odbierana, bez mnożnika | 20,8 tys. ton miodu |

**Przedział mapy: 6,5 – 20,8 tys. ton miodu.**

Po stronie GUS też są dwa scenariusze, bo wydajność na rodzinę różni się
2,6-krotnie między pasiekami zawodowymi a resztą:

| scenariusz GUS | razem zebrane | w przedziale mapy |
|---|---|---|
| zawodowe (>80 pni), 26 kg/rodzinę | 10,4 tys. ton | **TAK** |
| pozostałe, 10 kg/rodzinę | 23,2 tys. ton | nie — 11% nad górnym końcem |

Sprawdzian kontroluje **rząd wielkości, nie precyzję** — łańcuch ma cztery
ogniwa i każde ma własną niepewność. Przy tym zastrzeżeniu wynik jest
zgodny: jeden scenariusz wpada do środka, drugi leży tuż obok, a nie o rząd
wielkości.

Poprzednia wersja podawała **−27% i była nieprawdziwa** — stała
`CUKRY_MAPA_KG` była wpisana na sztywno (30,3 mln kg), więc po zmianie
podstawy rzepaku i po normalizacji jądra skrypt dalej drukował stary wynik.
Wyglądał na zaliczony, nie sprawdzając niczego. Teraz liczy sumę z cache
przy każdym uruchomieniu (kontrola: 150 623 ha rzepaku wobec 150 626 ha
w shapefile — różnica to strata na brzegu splotu).

## Dezaktualizacja mapy między sezonami

Porównanie map zbudowanych na deklaracjach 2025 i 2026:

- korelacja map **r = 0,774**
- z najlepszych 10% miejsc w 2025 **w 2026 zostaje tylko 50%**

Powierzchnie upraw są przy tym niemal identyczne (rzepak −2%, TUZ −1%,
gryka −0%). Zmienia się więc nie *ile* czego jest, tylko **gdzie** —
rzepak wędruje w płodozmianie.

To jest ilościowe uzasadnienie całego projektu: **mapa sprzed roku traci
połowę trafności co do najlepszych miejsc**, więc pszczelarz nie może
oprzeć decyzji na pamięci ani na jednorazowym opracowaniu. Zgadza się to
z testem przenoszenia, gdzie odniesienie „rosło tam, gdzie rok temu" dawało
dla rzepaku zaledwie r = 0,338.

## Przegląd kontrolny całości — co znalazł

Po złożeniu projektu przeprowadzono systematyczny przegląd pod kątem trzech
klas błędów, które wcześniej wyszły pojedynczo. Znalazł kolejne cztery.

**1. Produkt końcowy mieszał dwie konwencje jądra.** `zloz_calosc.py`
i `sredni_rok.py` splatały gatunki wędrujące starym stałym jądrem
(λ = 1000 m, zasięg 3000 m), podczas gdy warstwa stała szła już z jąder
sezonowych znormalizowanych. Suma się zgadzała (oba sumują się do 502,89),
więc bilans cukru był poprawny i błąd nie rzucał się w oczy — ale **kształt
był zły**: rzepak kwitnie w maju, kiedy pszczoły latają średnio 493 m, więc
jego zasięg to 1178 m, a nie 3000 m. Warstwa zmienna rozmywała go **2,5×
za szeroko**.

**2. Raport podawał liczbę bez sensu fizycznego.** „Cukier razem
w województwie: 11 252 mln kg" to była surowa suma po splocie, w której
każdy kilogram policzony jest tyle razy, ile wynosi suma jądra (~503).
Po poprawce: **22,4 mln kg** dla przeciętnego roku, wobec 26,0 mln kg dla
deklaracji 2025 — różnica jest zgodna z kierunkiem, bo lata 2019–2024 mają
mniej wykrytego rzepaku niż rekordowy 2025.

**3. Stała `SUMA_ODNIESIENIA` była wpisana ręcznie** (502,89) zamiast
liczona. Dokładnie ten sam wzorzec, który wcześniej unieważnił sprawdzian
GUS. Teraz liczy się z `jadro(1000, 3000).sum()`.

**4. Brakujące strażniki kompletności** dopisano w `zloz_calosc.py`
i `wojewodztwo_kalendarz.py` — oba iterowały po cache, więc gatunek dodany
później wypadałby bez śladu.

### Kontrola spójności po poprawkach

| sprawdzenie | wynik |
|---|---|
| cukier z hektarów × wydajność (GSA 2025) | 26,0 mln kg |
| cukier policzony z mapy | **26,0 mln kg** |
| kalibracja areałowa, rzepak 2025 | 150 649 ha wobec 150 649 ha GSA |
| udział rzepaku w cukrach | 50,9% |
| udział TUZ (dwa pokosy) | 21,4% |

Wszystkie siedem skryptów łańcucha przelicza się bez błędu.

**Wniosek metodyczny.** Sześć z siedmiu znalezionych dziś błędów było
**cichych** — nie rzucały wyjątku, a wyniki wyglądały wiarygodnie.
Wykrył je dopiero pomiar albo systematyczny przegląd, nigdy samo
uruchomienie. Dlatego w kodzie zostały strażniki, które przerywają
liczenie, zamiast produkować sensownie wyglądającą liczbę.

## Podział warstw — luka, przez którą wypadało 12,4% cukrów

`zloz_calosc.py` buduje mapę końcową, iterując po dwóch listach:
`WEDRUJACE` (z detekcji satelitarnej) i `NIEWEDRUJACE` (z deklaracji).
Gatunek nieobecny w **żadnej** z nich wypadał z produktu końcowego —
bez wyjątku, bez ostrzeżenia, suma liczyła się poprawnie.

Nieprzypisanych było sześć:

| gatunek | udział w cukrach | dlaczego nie miał testu przenoszenia |
|---|---|---|
| **TUZ odrost** | **9,4%** | drugi pokos tej samej łąki, nie osobna uprawa |
| lucerna mieszańcowa | 1,1% | roślina wieloletnia, mało działek |
| koniczyna czerwona | 1,0% | roślina wieloletnia, mało działek |
| gorczyca biała | 0,4% | wchodzi w klasę zbiorczą „gorczyca" |
| rzepak jary | 0,3% | odrzucony z klasyfikatora — mylił się z ozimym |
| słonecznik oleisty | 0,2% | wchodzi w klasę zbiorczą „słonecznik" |

Razem **12,4% cukrów województwa nie trafiało do mapy końcowej.**

Wszystkie sześć przypisano do warstwy deklaracji — bo dla żadnego z nich
nie ma szeregu satelitarnego, a bez pomiaru przenoszenia nie wolno ich
umieszczać w warstwie satelitarnej.

Dopisano funkcję `sprawdz_kompletnosc()`, wywoływaną na starcie składania:
każdy pożytek musi należeć do **dokładnie jednej** warstwy, inaczej
liczenie się przerywa.

### Zakres warstw po poprawce

| warstwa | gatunki | udział w cukrach |
|---|---|---|
| satelitarna (`WEDRUJACE`) | rzepak ozimy, gryka, słonecznik | **58,8%** |
| deklaracje (`NIEWEDRUJACE`) | pozostałe 13 | 41,2% |

Kryterium przydziału jest pomiarowe, nie uznaniowe: do warstwy satelitarnej
trafia gatunek, dla którego **detekcja bije odniesienie „rosło tam, gdzie
rok temu"**. Malina jest wykrywana (r = 0,878), ale jako krzew wieloletni
ma pamięć na poziomie 0,847 przy stabilnej plantacji — detekcja nic tam nie
wnosi, więc idzie z deklaracji.

## Zakładka satelitarna w kalendarzu

Pokazywała wyłącznie rzepak ze **starego, jednogatunkowego** klasyfikatora
(`woj_prawd_*.npy`), splatanego stałym jądrem 3 km — cała praca nad
klasyfikatorem wielogatunkowym do niej nie docierała. Podpis wprost mówił
„satelita nie widzi fasoli, **gryki** ani łąk", choć grykę wykrywamy.

Teraz warstwa idzie z `wielo_klasy_*.npz`: trzy gatunki wędrujące, po
kalibracji areałowej, z jądrami sezonowymi — tą samą metodą co reszta
projektu.

## Walidacja krzyżowa modelu fenologicznego — zastrzeżenie sprawdzone

Podawany błąd modelu (3,5 dnia dla pełnego sezonu, 4,4 dnia dla prognozy
na 1 V) był liczony **na tych samych 52 obserwacjach, na których dobrano
bazę termiczną i próg GDD**. Model był więc sprawdzany na danych, które go
stworzyły — to jest błąd dopasowania, z definicji optymistyczny.

Przeprowadzono walidację **leave-one-out**: dla każdej obserwacji parametry
dobierane są na pozostałych 51, a błąd liczony na odłożonej.

| zbiór | n | RMSE dopasowania | **RMSE walidacji** | optymizm |
|---|---|---|---|---|
| obserwacje czyste | 52 | 3,48 d | **3,48 d** | **+0,00 d** |
| pełny, z odrzuconymi | 59 | 6,23 d | 6,31 d | +0,08 d |

**Optymizmu nie ma.** Powód jest widoczny w stabilności parametrów: przy
usuwaniu dowolnego pojedynczego punktu dopasowanie wypada **za każdym razem
identycznie** — baza 1,0 °C i próg 555 w każdym z 52 przebiegów. Pięćdziesiąt
dwie obserwacje wielokrotnie przewyższają dwa dopasowywane parametry, więc
model nie ma z czego się przeuczyć.

Liczbę 3,5 dnia (i wynikające z niej 4,4 dnia prognozy) można więc podawać —
ale **jako wynik walidacji krzyżowej**, a nie dopasowania, bo dopiero to
czyni ją odporną na zarzut.

### Koszt odrzucenia obserwacji odstających

Siedem obserwacji odrzucono jako odstające i te same siedem było wykluczonych
z liczenia błędu. To nie jest neutralne:

| | RMSE | błąd najgorszego przypadku |
|---|---|---|
| bez odrzuconych (n=52) | 3,48 d | 7,8 d |
| z odrzuconymi (n=59) | **6,31 d** | **26,1 d** |

Uczciwe sformułowanie: **3,5 dnia na obserwacjach czystych, 6,3 dnia na
pełnym zbiorze.** Podawanie wyłącznie pierwszej liczby bez tej informacji
byłoby przemilczeniem.

### Czego walidacja krzyżowa NIE naprawia

Wartości odniesienia to daty odczytane z krzywych NDYI Sentinel-2, a nie
obserwacje polowe — model porównywany jest z inną estymacją satelitarną.
Niezależną walidację polową mamy tylko dla lipy (2,8 dnia) i robinii
(−1 dzień) wobec map fitofenologicznych IMGW z 51 stacji.

## Odrzucanie danych: od progu dobranego po fakcie do reguły odpornej

Kalibracja odrzucała **pojedyncze obserwacje** odstające od mediany roku
o więcej niż 8 dni. Próg 8 dni dobrano po fakcie i usuwał on punkty,
a nie przyczynę — to wygląda na dobieranie danych pod wynik.

Diagnoza pokazała, że odrzucenia **nie są rozłożone równomiernie, tylko
skupione w konkretnych sezonach**:

| rok | rozrzut obserwacji | × mediany | werdykt |
|---|---|---|---|
| 2018 | 8 d | 0,9 | ok |
| 2019 | 9 d | 1,0 | ok |
| **2020** | **25 d** | **2,8** | **odrzucony** |
| 2021 | 13 d | 1,5 | ok |
| 2022 | 9 d | 1,0 | ok |
| 2023 | 6 d | 0,6 | ok |
| 2024 | 7 d | 0,8 | ok |
| 2025 | 6 d | 0,7 | ok |
| **2026** | **40 d** | **4,6** | **odrzucony** |

Rzepak nie kwitnie w jednym województwie z rozrzutem 40 dni. To nie jest
zmienność zjawiska, tylko **awaria odczytu krzywych NDYI** — 2026 to sezon
bieżący, więc archiwum Sentinel-2 jest rzadsze (przy teście przenoszenia
ten sam rok miał 24 z 52 okien puste).

**Nowe kryterium, zapisane z góry:** sezon odrzuca się w całości, gdy
rozrzut jego obserwacji przekracza **dwukrotność mediany rozrzutów**
wszystkich sezonów. To standardowa reguła odstających oparta na medianie —
odporna na same odstające i nieodwołująca się do tego, jaki RMSE chcemy
otrzymać.

### Wynik

| podejście | n | RMSE (walidacja krzyżowa) |
|---|---|---|
| odrzut 7 punktów, próg 8 d dobrany po fakcie | 52 | 3,48 d |
| **odrzut 2 sezonów, reguła medianowa** | **45** | **4,17 d** |
| bez żadnego odrzutu | 59 | 6,31 d |

**Parametry modelu nie zmieniły się: baza 1,0 °C, próg 555** — te same,
co przy poprzednim sposobie odrzucania. Model jest więc ten sam; uczciwsza
jest wyłącznie ocena jego błędu.

Optymizm dopasowania wynosi tu **+0,28 d** (przy poprzednim zbiorze był
zerowy), więc walidacja krzyżowa okazała się potrzebna.

**Do raportowania: 4,2 dnia**, błąd bezwzględny 3,2 dnia, najgorszy
przypadek 11,7 dnia, na 45 obserwacjach z 7 sezonów.

**Do przeliczenia zostaje błąd prognozy w sezonie** (podawany dotąd jako
4,4 dnia na 1 V) — liczono go na zbiorze 52 obserwacji, więc wymaga
powtórzenia na nowym zbiorze 45.

## Walidacja kotwiczonych modeli fenologicznych pomiarem satelitarnym

Model GDD kalibrowany jest **pomiarowo tylko dla rzepaku**. Pozostałe
gatunki mają model **kotwiczony**: baza z literatury, próg dobrany tak, by
mediana wieloletnia trafiała w tabelaryczną datę. Mediana jest więc
poprawna z definicji, a amplituda wahań pozostawała założeniem.

Zmierzono daty kwitnienia z Sentinela-2 na **działkach deklarowanych ARiMR**
(2025 i 2026), dla gatunków, których kwitnienie w ogóle daje sygnał optyczny.

**Kontrola metody.** Rzepak wchodzi do tego zestawienia jako punkt
odniesienia — jego model znamy niezależnie (błąd 3,2 dnia). Pomiar dał
**4,1 dnia**, czyli metoda działa. Pierwsza wersja, bez normalizacji sceny,
dawała dla rzepaku 9,5 dnia — mierzyła zmienność atmosferyczną, nie
kwitnienie. Odejmowanie mediany gruntów ornych z **tej samej sceny** jest
więc warunkiem koniecznym, nie kosmetyką.

| gatunek | indeks | 2025 | 2026 | średni błąd | ocena |
|---|---|---|---|---|---|
| **rzepak ozimy** | NDYI | +6 d | −2 d | **4,1 d** | kontrola — zgodne |
| gorczyca | NDYI | −17 d | +2 d | 9,5 d | rozbieżność niespójna |
| gorczyca biała | NDYI | −18 d | +7 d | 12,2 d | rozbieżność niespójna |
| słonecznik | NDYI | +4 d | +18 d | 10,8 d | rozbieżność niespójna |
| **rzepak jary** | NDYI | **−20 d** | **−12 d** | 15,9 d | **błąd systematyczny** |
| gryka zwyczajna | JASN | **−26 d** | **−26 d** | 25,9 d | patrz zastrzeżenie |
| malina | JASN | −30 d | +1 d | 14,8 d | patrz zastrzeżenie |
| porzeczka | JASN | +13 d | −26 d | 36,0 d | patrz zastrzeżenie |

### Co z tego wynika

**Rzepak jary — model jest za późny.** Odchylenie ma ten sam znak w obu
sezonach (−20 i −12 dni), więc to nie jest szum. Kotwica przyjmowała
kwitnienie na przełomie VI/VII, a pomiar wskazuje trzecią dekadę czerwca.
Udział w cukrach jest wprawdzie niewielki (0,3%), ale poprawka jest
uzasadniona pomiarem.

**Gorczyca i słonecznik — rozbieżność niespójna.** Odchylenia mają
przeciwne znaki w kolejnych latach, a liczba scen jest mała (11–20). To
wygląda na szum pomiaru, nie na błąd modelu — dwa sezony nie wystarczą,
żeby rozstrzygnąć.

### Zastrzeżenie do gatunków o kwiatach białych

Dla gryki, maliny i porzeczki użyto indeksu **jasności** (zielony +
czerwony), bo NDYI wykrywa wyłącznie żółć. **Ten indeks nie został
zwalidowany** — nie mamy gatunku o białych kwiatach, którego termin
kwitnienia znalibyśmy niezależnie. Maksimum jasności może wypadać w szczycie
biomasy, a nie w pełni kwitnienia.

Konsekwentne −26 dni dla gryki w obu sezonach jest uderzające, ale
posiadanymi danymi **nie da się rozstrzygnąć**, czy to błąd modelu, czy
systematyczne przesunięcie indeksu. Wyniki dla tych trzech gatunków należy
traktować jako sygnał do zbadania, nie jako pomiar.

### Ograniczenie wspólne

Deklaracje ARiMR istnieją tylko dla 2025 i 2026, więc **na gatunek przypadają
dwa sezony**. To wystarcza, by wykryć błąd systematyczny (jak przy rzepaku
jarym), ale nie by skalibrować model GDD — do tego potrzeba rozpiętości
termicznej wielu lat. Jest to więc walidacja punktowa, nie kalibracja.

## Zmiana rewizyty Sentinela-1 — sprawdzona, bez wpływu

Sentinel-1B uległ awarii zasilania w grudniu 2021 (misję zamknięto
w sierpniu 2022), Sentinel-1C wystartował w grudniu 2024. Rewizyta wynosiła
więc 6 dni do końca 2021, **12 dni w latach 2022–2024** i znów 6 od 2025.
Ponieważ okna cech są półmiesięczne, a radar odpowiada za 52,9% ważności
klasyfikatora, powstało podejrzenie, że część niestabilności międzyrocznej
ma tę właśnie przyczynę.

**Fakt się potwierdza — liczba scen spadła o ponad połowę:**

| sezon | scen (IX–IX) | na okno | satelity |
|---|---|---|---|
| 2019 | 552 | 21,2 | A + B |
| 2021 | 456 | 17,5 | A + B |
| **2023** | **237** | **9,1** | **tylko A** |
| **2024** | **245** | **9,4** | **tylko A** |
| 2025 | 334 | 12,8 | A + C |
| 2026 | 463 | 17,8 | A + C + D |

**Ale skutku nie widać.** Korelacja liczby scen z odchyleniem areałowym od
średniej wieloletniej:

| gatunek | r |
|---|---|
| **rzepak ozimy** | **−0,076** |
| malina | +0,209 |
| słonecznik | +0,485 |
| gryka zwyczajna | +0,534 |

Dwa argumenty za odrzuceniem hipotezy:

1. **Znak jest odwrotny.** Gdyby niedobór scen powodował niestabilność,
   korelacja byłaby ujemna. Jest dodatnia — sezony z *większą* liczbą scen
   mają *większe* odchylenia, co wyklucza ten mechanizm.
2. **Przy siedmiu sezonach r = 0,53 jest nieistotne** (dla n = 7 próg
   istotności to około 0,75).

**Najważniejsze: dla rzepaku korelacja wynosi −0,076, czyli zero.** Rzepak
jest jedynym gatunkiem o wiarygodnej serii wieloletniej i niesie 51% cukrów
— dwukrotny spadek liczby scen w latach 2023–2024 **nie zaszkodził jego
detekcji**. Prawdopodobne wyjaśnienie: przebieg rzepaku jest bardzo
wyrazisty (zielony zimą, żółty w maju, ściernisko w lipcu), więc dziewięć
scen na okno wystarcza.

Niestabilności gatunków pobocznych **nie można więc przypisać Sentinelowi-1**.
Przyczyna leży w samym sygnale i w małej liczbie działek — co potwierdza
malina, wieloletni krzew o wahaniach areału 15-krotnych.

Odtwarzalne: `python skrypty/detekcja/rewizyta_s1.py`

## Sprostowanie: „model bije pamięć trzykrotnie" — tylko dla działek

Test przenoszenia podawał dla rzepaku **r = 0,958 wobec odniesienia 0,338**
i opisywaliśmy to jako trzykrotną przewagę detekcji nad pamięcią. **To jest
poprawne dla pytania o konkretną działkę, ale mylące dla mapy.**

Odniesienie 0,338 powstaje przez przypisanie każdej działce etykiety
**najbliższej działki z roku poprzedniego**. Odpowiada więc na pytanie
„czy to konkretne pole będzie rzepakiem" — i tam pamięć faktycznie zawodzi,
bo rzepak wraca na to samo pole co 3–4 lata.

Produktem projektu nie są jednak działki, tylko **mapa gęstości po splocie
jądrem zasięgu lotu**. Zmierzona na deklaracjach ARiMR, czyli na prawdzie
terenowej:

| porównanie | r |
|---|---|
| deklaracje rzepaku 2025 wobec 2026 | **0,795** |
| detekcja 2025 wobec deklaracji 2025 | 0,991 |
| mapy detekcji między różnymi sezonami (średnia z 21 par) | 0,794 |

**Mapa regionalna jest stabilna.** Rolnicy zmieniają konkretne pola, ale
w obrębie tych samych okolic — decyduje o tym gleba, tradycja płodozmianu
i rozmieszczenie skupów.

### Poprawne sformułowanie

| pytanie | pamięć „jak rok temu" | model |
|---|---|---|
| która konkretna działka to rzepak | 0,338 | 0,958 |
| jak wygląda mapa regionalna | **0,795** | 0,991 |

Dla mapy detekcja podnosi zgodność **z 0,795 na 0,991** — poprawa realna,
ale nie trzykrotna.

### Czego to nie podważa

Detekcja pozostaje niezbędna z innego powodu: **deklaracje istnieją tylko
dla 2025 i 2026**. Dla lat 2019–2024 nie ma czego pamiętać — bez detekcji
nie powstałby ani przeciętny rok, ani warstwa niezawodności, czyli dwa
główne produkty projektu.

Kryterium podziału warstw pozostaje w mocy, bo porównywało gatunki między
sobą tą samą miarą: dla upraw trwałych pamięć wygrywała także w mierze
działkowej (fasola 0,949 wobec 0,880), więc wnioski o tym, co brać
z detekcji, a co z deklaracji, się nie zmieniają.

Odtwarzalne: porównanie warstw w `wyniki/cache/kalendarz_dane.json`.

## Rozszerzenie próby: 7 → 19 obszarów, 45 → 145 obserwacji

Pierwotna kalibracja opierała się na **7 obszarach** wybranych jako rejony
o powierzchni rzepaku powyżej 2000 ha. Powstało pytanie, czy błąd 3,2 dnia
nie jest artefaktem korzystnego doboru miejsc. Próbę rozszerzono do
**19 obszarów** wyznaczonych z gęstości rzepaku w deklaracjach GSA 2025
(komórki 15 km powyżej 1500 ha, odstęp 20 km) — kryterium danymi, nie na oko.

### Reguła odrzucania musiała się zmienić

Pierwszy przebieg dał **RMSE 7,28 dnia**, czyli ponad dwukrotnie gorzej.
Diagnoza: przy 7 obszarach awarie odczytu skupiały się w całych sezonach
(2020, 2026) i reguła „odrzuć sezon o rozrzucie ponad dwukrotność mediany"
działała. Przy 19 obszarach okazały się **rozproszone** — w każdym sezonie
kilka pojedynczych odczytów leży skrajnie daleko, reszta jest dobra.
Mediana rozrzutów urosła wtedy z 9 na 30 dni i próg razem z nią, więc
reguła przestała cokolwiek odrzucać. **Miara względna zawodzi, gdy psuje
się cały rozkład.**

Wrócono do odrzutu pojedynczych obserwacji, ale z progiem wyprowadzonym
**z fizyki, przed spojrzeniem na błędy**: model przewiduje między tymi
obszarami rozrzut 2–5 dni, więc odchylenie od mediany sezonu może sięgać
~2,5 dnia z termiki; plus ~3 dni niepewności odczytu NDYI daje **około
6 dni**.

### Wynik jest na ten wybór odporny

| próg odrzutu | obserwacji | baza | próg GDD | RMSE walidacji | najgorszy |
|---|---|---|---|---|---|
| 6 d *(fizyczny)* | 141 | 1,0 | 465 | **3,17 d** | 11,9 d |
| **8 d** *(przyjęty)* | **145** | **1,5** | **430** | **3,21 d** | 11,9 d |
| 10 d | 148 | 1,0 | 460 | 3,50 d | 11,9 d |
| 12 d | 150 | 1,5 | 440 | 3,59 d | 11,9 d |
| 15 d | 153 | 1,5 | 430 | 3,96 d | 16,1 d |
| 20 d | 157 | 0,5 | 485 | 4,82 d | 21,2 d |
| **bez odrzutu** | 162 | 2,0 | 410 | **7,09 d** | 38,0 d |

Zależność jest **płynna i monotoniczna** — nie ma progu, przy którym wynik
nagle się poprawia. Bez odrzutu błąd rośnie ponad dwukrotnie, a najgorszy
przypadek z 12 na 38 dni, więc filtrowanie awarii odczytu jest konieczne.

### Dwa niezależne potwierdzenia

**Błąd się utrzymał.** 3,21 dnia na 145 obserwacjach z 19 obszarów wobec
3,19 dnia na 45 obserwacjach z 7. Poprzednia liczba **nie była artefaktem
doboru miejsc** — to było główne ryzyko tej części pracy.

**Parametry trafiły w te same.** Przy progu 8 dni przeszukanie siatki
wskazuje **bazę 1,5 °C i próg 430 GDD** — dokładnie te, które wyprowadzono
z trzykrotnie mniejszej próby i z innych obszarów. Dwa rozłączne zbiory
danych doprowadziły do tej samej pary parametrów.

### Prognoza w sezonie na nowej próbie

| dzień decyzji | wyprzedzenie | RMSE |
|---|---|---|
| 15 II | 88 dni | 6,8 d |
| 1 IV | 43 dni | 7,3 d |
| 15 IV | 29 dni | 4,5 d |
| **1 V** | **13 dni** | **3,4 d** |
| po sezonie | 0 | 3,2 d |

Prognoza wypadła **lepiej** niż na mniejszej próbie (3,4 wobec 3,9 dnia na
1 maja). Utrzymuje się wniosek, że do połowy kwietnia model niewiele wnosi
ponad średnią wieloletnią, a użyteczny staje się na przełomie kwietnia i maja.

---

## Porządki w repozytorium (20 VIII 2026)

Projekt zajmował **6,1 GB**. Po usunięciu nadmiaru: **4,7 GB** (−1,43 GB).
Nie usunięto ani jednego skryptu — spis, co zniknęło i jak to odtworzyć.

| co | ile | dlaczego bezpieczne | jak odtworzyć |
|---|---|---|---|
| `.git` — nieosiągalne blob-y | 530 MB | pozostałość po `git add` sprzed `.gitignore`; indeks (115 plików) nietknięty, lista blobów identyczna przed i po | — |
| `dane/*.zip` (GSA 2025, 2026) | 623 MB | zawartość rozpakowana obok i zgodna **co do bajta** (sprawdzone `zipfile`) | geoportal ARiMR |
| `wielo_cechy_2026_czesci/` | 17 MB | 19 części CSV scalonych w `wielo_cechy_2026.csv`; **22 667 = 22 667** wierszy | `wielo_s1s2.py` |
| `wielo_skalibrowane_*.npz` | 16 MB | zapisywane przez `kalibracja_arealowa.py`, **nieczytane przez nic** — kalibracja liczona w locie | `kalibracja_arealowa.py` |
| `__pycache__`, `potencjal.json` | <1 MB | produkty pośrednie bez odbiorcy | — |

### Czego NIE usunięto i dlaczego

**Żadnego skryptu.** Wszystkie 69 to razem **1,6 MB — 0,03% projektu**.
Kasowanie ich nie zwolniłoby miejsca, a zabrałoby odtwarzalność liczb
cytowanych w raporcie. Etapy zarzucone (klasyfikator fasoli, `mapa_ladna`,
warianty fenologii) są **wynikami negatywnymi** i mają wartość dokumentacyjną.

**`cache/woj_prawd_*.npy`** (113 MB) — 10 godzin liczenia w GEE, nie do
odtworzenia w rozsądnym czasie.

**`dane/gsa_lubelskie_2026/`** (1,9 GB) — mimo że etykiety biorą się z 2025,
rocznik 2026 służy za podstawę odniesienia „pamięć” (r = 0,795 dla mapy).

### Uwaga metodyczna

Pierwsze automatyczne szukanie sierot wskazało **23 pliki cache jako
nieużywane, w tym `woj_prawd_*`**. Były używane — nazwy powstają f-stringiem
(`f"woj_prawd_{rok}.npy"`), więc wyszukiwanie po dosłownej nazwie ich nie
widziało. Podobnie `mapa_dzialki_*.png`, serwowane przez `serwis.py:563`.
Gdyby usunąć je bez sprawdzenia wzorców, przepadłoby 10 godzin obliczeń.
**Automatyczna detekcja martwego kodu jest tu zawodna** i każde wskazanie
wymagało potwierdzenia przez `grep` po wzorcu, nie po nazwie.

---

## Strony działające z dysku (20 VIII 2026)

Mikroserwis Flask wymaga Pythona, Flaska i **4,6 GB danych, których nie ma
w repozytorium** (`dane/`, `wyniki/cache/`, `wyniki/rastry/` są w `.gitignore`).
Kto pobrał projekt, nie uruchomił go — brakowało `kalendarz_dane.json`
i rastrów. Sam katalog `skrypty/serwis/` też nie był śledzony.

Prognoza działa więc teraz także jako pojedynczy plik: mapa wtopiona w base64,
model wpisany do JS, pogoda pobierana wprost z Open-Meteo. API zwraca
`access-control-allow-origin: *` również dla `Origin: null`, czyli dla strony
otwartej przez `file://` — **sprawdzone nagłówkiem, nie założone**.

### Cena: model istnieje w dwóch językach

Nagłówek `model_fenologiczny.py` ostrzega wprost przed drugą kopią obliczeń.
Bez Pythona nie da się jej uniknąć, więc zamiast zakładać zgodność —
jest mierzona. `test_rownowaznosc.py` przepuszcza te same punkty przez
Pythona i przez JS w przeglądarce i porównuje 11 pól, które widzi użytkownik.
Parametry nie są w JS wpisane, tylko wstrzykiwane z `wyniki/json/`.

### Zaokrąglanie połówek — błąd, który złapał test

Pierwsze uruchomienie dało **rozbieżność w 1 z 5 punktów**: pełnia 15 V
w Pythonie, 14 V w JS.

Przyczyna: `round()` w Pythonie zaokrągla połówkę **do liczby parzystej**
(`round(512.5) = 512`), a `Math.round()` w JS **zawsze w górę**
(`Math.round(512.5) = 513`). Współrzędne są przycinane do siatki 0,1°, więc
punkt kończący się na `.x5` — np. **51,25** — trafiał w Pythonie do komórki
51,2, a w JS do 51,3. Inna komórka to inna pogoda i inna data.

Drugi punkt z tą samą wadą (długość 23,25) wypadł „zgodnie", bo różnica pogody
przypadkiem nie przesunęła daty o pełny dzień. **Błąd był tam, ale niewidoczny.**
Po dołożeniu czterech punktów celujących dokładnie w połowę komórki i po
przepisaniu zaokrąglenia na regułę Pythona: **9 punktów × 11 pól, zero różnic.**

To kolejny przypadek tej samej klasy co reszta projektu — nic nie rzucało
wyjątku, obie liczby wyglądały poprawnie, a różnica wyszła dopiero
z porównania dwóch niezależnych implementacji.

### Gotowe strony pod kontrolą wersji

Wbrew zwyczajowi `raport.html`, `kalendarz.html`, `mechanika.html`,
`prognoza.html` i `index.html` **są śledzone**. Nie da się ich odtworzyć po
pobraniu — wymagają 4,6 GB danych spoza repozytorium. To one są produktem
końcowym, więc bez nich klon nie pokazuje niczego. Repozytorium waży 19,6 MB.

### Statyczna strona pokazywała porzuconą mapę (poprawione)

Pierwsza wersja eksportu miała **własny szablon** z mapą PNG z
`warstwa_rzepak.py` i zaznaczaniem lassem. Był to renderer **już wcześniej
porzucony** — docstring trasy `/warstwa/rzepak.json` mówi wprost, że dawał
„ziarnistą, nieczytelną mapę" i został zastąpiony warstwami kalendarza.
Statyczna strona pokazywała więc mapę o pokolenie starszą niż serwis: bez
przełączników lat, bez legendy w tonach cukrów, w innym kluczu kolorów.

Poprawka nie polegała na odtworzeniu nowej mapy w drugim miejscu, tylko na
usunięciu drugiego miejsca. `eksport_statyczny.py` bierze teraz **dosłownie
`STRONA` z `serwis.py`** i podmienia w niej dokładnie dwie rzeczy, których
nie ma bez serwera:

| w serwisie | w pliku statycznym |
|---|---|
| `fetch("/warstwa/rzepak.json")` | dane wtopione w plik (0,46 MB) |
| `fetch("/prognoza_obszar")` | model policzony w przeglądarce |

Interfejs jest jeden, tak jak model jest jeden — ta sama zasada, którą
głosi nagłówek `model_fenologiczny.py`. Złamanie jej dało dokładnie skutek,
przed którym ostrzega: dwie strony pokazujące co innego.

### Przy okazji: sezony minione

Poza sezonem (czerwiec–marzec) model nie ma żadnej pogody najbliższego
kwitnienia i zwraca średnią wieloletnią, ±6,8 dnia. Strona przez większość
roku nie pokazywała nic poza klimatologią. Dodano przyciski lat: sezony
minione mają komplet pogody, więc dają termin z błędem **±3,2 dnia**.
Wielka data zawiera teraz **rok** — wcześniej brzmiała „15 V" i oglądana
w sierpniu czytała się jako maj, który już minął.
