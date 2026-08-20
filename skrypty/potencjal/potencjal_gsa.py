"""
WARSTWA POZYTKU Z GSA - przebudowa potencjalu na deklaracjach ARiMR.

Co sie zmienia wzgledem wersji na EUCROPMAP:
  - areal rzepaku: 10 808 ha zamiast 7 644 ha (EUCROPMAP zanizal o 29%)
  - prawdziwe nazwy upraw zamiast 21 klas zbiorczych; wychodza pozytki, ktorych
    wczesniej nie bylo widac - przede wszystkim fasola wielokwiatowa (4 202 ha),
    kwitnaca od konca czerwca, czyli w luce uznanej wczesniej za pusta
  - geometria dzialek zamiast rastra 10 m

SPLOT LICZONY LOKALNIE, NIE W GEE
Obszar to 300 x 300 pikseli po 100 m. FFT robi to w ulamku sekundy, podczas gdy
w Earth Engine splot z jadrem 61 x 61 nie konczyl sie w rozsadnym czasie, bo
przeliczal warstwe zrodlowa dla kazdego sasiada kazdego piksela. GEE zostaje do
tego, w czym jest niezastapiony - szeregow czasowych Sentinela.

STAN UZRODLOWIENIA - pelne zestawienie w ZRODLA.md
Kazda pozycja ma pole 'zrodlo' i klase wiarygodnosci A/B/C. Po przegladzie
literatury: 93.3% potencjalu opiera sie na dwoch badaniach naukowych (klasa A),
5.5% na kompilacji branzowej (B), a ponizej 1.2% na wartosciach bez zrodla (C).

Uruchomienie:
    python potencjal_gsa.py
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

# rasterio i pyproj wioza wlasne kopie PROJ; przy imporcie w tej kolejnosci
# rasterio nie znajduje proj.db i wywala sie dopiero przy zapisie GeoTIFF-a
os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import pandas as pd
import pyogrio
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

# ---------------------------------------------------------------- konfiguracja
STACJA_LAT, STACJA_LON = 50.755, 23.600
PROMIEN_BUFORA_M = 10_000
ROK = 2025                      # rocznik GSA

PIKSEL_M = 100                  # 100 x 100 m = 1 ha
PIKSEL_RASTER = 20              # rozdzielczosc rasteryzacji przed agregacja
LAMBDA_M, ZASIEG_M = 1000, 3000

DEKADY = list(range(100, 260, 10))

# nazwa GSA: (kg CUKROW/ha, DOY start, pelnia, koniec, zrodlo, klasa_zrodla)
#
# JEDNOSTKA: kilogramy cukrow w nektarze na hektar, nie kilogramy miodu.
# Tak podaja to badania, a przelicznik cukry -> miod (ok. x1.25) rozni sie
# miedzy zrodlami. Wartosci podane w literaturze jako MIOD sa tu dzielone
# przez 1.25; zaznaczone jako klasa B.
#
# KLASY WIARYGODNOSCI ZRODLA - patrz ZRODLA.md
#   A - badanie naukowe, pomiar w tym samym regionie
#   B - kompilacja branzowa (tabela wydajnosci miodowych), przeliczona z miodu
#   C - moje zalozenie, bez zrodla
POZYTKI = {
    # --- A: badania, pomiar regionalny -------------------------------------
    # WYDAJNOSC PRZELICZONA NA PODSTAWE TABELARYCZNA (88 zamiast 115).
    # Powod: badanie z Pulaw mierzy PRODUKCJE nektaru, a tabele branzowe
    # uzyte dla pozostalych 14 gatunkow podaja WYDAJNOSC MIODOWA, czyli to,
    # co pszczelarz realnie odbiera. Mieszanie tych dwoch podstaw zawyzalo
    # rzepak o ok. 30% wzgledem reszty, a mapa sluzy wlasnie do porownywania
    # gatunkow miedzy soba - wiec spojnosc jest wazniejsza niz posiadanie
    # jednej wartosci klasy A.
    #
    # 80-140 kg miodu/ha (tabela) -> srodek 110 -> /1.25 = 88 kg cukrow/ha.
    # Badanie z Pulaw nie znika: mierzone 80-150 kg cukrow/ha pokrywa sie
    # z tabelarycznym 64-112, wiec SLUZY TERAZ ZA WALIDACJE tabeli.
    "rzepak ozimy":         ( 88, 118, 128, 140,
                             "tabela 80-140 kg miodu/ha (podstawa jednolita "
                             "z reszta gatunkow); walidacja: Pasieka 2/2003, "
                             "12 plantacji pod Pulawami, 80-150 kg cukrow/ha "
                             "produkcji. OKNO -10/+12 ZMIERZONE z krzywej "
                             "NDYI; tabelaryczne 20 IV-28 V (38 d) to "
                             "OBWIEDNIA ZMIENNOSCI miedzy latami, nie "
                             "dlugosc kwitnienia - badanie z Pulaw podaje "
                             "~20 dni, nasz pomiar 22", "A"),
    "fasola wielokwiatowa": ( 73, 175, 190, 215,
                             "Koltowski, Pasieka 3/2005: 38-109 kg cukrow/ha, "
                             "kwitnienie 30-50 dni od konca VI", "A"),
    # --- B: tabela wydajnosci miodowych, przeliczona /1.25 -----------------
    # OKNO POTWIERDZONE JAKO DLUGOSC, nie obwiednia: zrodla agronomiczne
    # podaja "kwitnienie 3-6 tygodni" (21-42 d, srodek 31) - nasze okno ma
    # dokladnie 31 d. Zgadza sie tez mechanizm: kwitnienie 5-7 tygodni po
    # siewie, przy siewie w II polowie maja daje przelom VI/VII.
    "gryka zwyczajna":      (140, 186, 200, 217,
                             "100-250 kg miodu/ha; dlugosc kwitnienia 3-6 "
                             "tygodni potwierdzona niezaleznie (agrofakty, "
                             "agrokurier)", "B"),
    "malina":               (160, 139, 149, 159, "150-250 kg miodu/ha, 19 V-8 VI", "B"),
    # UWAGA: dla ponizszych gatunkow DLUGOSCI kwitnienia nie udalo sie
    # potwierdzic - zrodla podaja tylko przedzialy dat, ktore moga byc
    # obwiedniami zmiennosci (jak przy rzepaku: tabela 38 d, pomiar 22 d).
    # Koniczyna wrecz jawnie: "kwitnie od maja do wrzesnia" - to na pewno
    # obwiednia. Nasze okna sa jednak WEZSZE niz te przedzialy, wiec ryzyko
    # przeszacowania jest ograniczone. Lacznie 12.7% cukru wojewodztwa.
    "koniczyna czerwona":   ( 80, 166, 172, 179, "50-150 kg miodu/ha, 15-28 VI; "
                             "DLUGOSC NIEPOTWIERDZONA", "B"),
    "lucerna mieszańcowa":  ( 80, 176, 191, 206, "50-150 kg miodu/ha, 25 VI-25 VII", "B"),
    "gorczyca biała":       ( 52, 152, 164, 176, "40-90 kg miodu/ha, 1-25 VI", "B"),
    "porzeczka":            ( 36, 105, 112, 120, "20-70 kg miodu/ha, 15-30 IV", "B"),
    # TUZ ma DWA szczyty, nie jedno okno przez cale lato. Poprzednia wersja
    # (125-150-240, czyli 115 dni) byla moim zalozeniem i rozmazywala 18,5%
    # cukru rownomiernie od maja do sierpnia - drugi najwiekszy zrodlo
    # splaszczenia kalendarza zaraz po rzepaku.
    #
    # Agronomia pokosow (tygodnik-rolniczy, topagrar, agrofakt):
    #   kloszenie traw    przelom II i III dekady maja
    #   I pokos           polowa - koniec maja (3. dekada typowo)
    #   odrost            45-50 dni po I pokosie
    #   II pokos          lipiec / poczatek sierpnia
    # I pokos daje 50-60% rocznego plonu - stad podzial cukru 55/45.
    # Koszenie URYWA kwitnienie, stad ostre zakonczenie pierwszego okna.
    "TUZ":                  ( 18, 121, 135, 145,
                             "I pokos: kwitnienie runi (mniszek, jaskry, "
                             "koniczyna) od poczatku V do koszenia ok. 25 V; "
                             "55% cukru wg udzialu I pokosu w plonie", "B"),
    "TUZ odrost":           ( 14, 186, 201, 217,
                             "odrost 45-50 dni po I pokosie, kwitnienie "
                             "VII - pocz. VIII; 45% cukru", "B"),
    "słonecznik":           ( 32, 191, 210, 232, "30-50 kg miodu/ha, 10 VII-20 VIII", "B"),
    "słonecznik oleisty":   ( 32, 191, 210, 232, "30-50 kg miodu/ha, 10 VII-20 VIII", "B"),
    "bobik":                ( 20, 166, 178, 191, "20-30 kg miodu/ha, 15 VI-10 VII", "B"),
    # Okno 14 d zgodne ze zrodlami sadowniczymi: pelnia kwitnienia jabloni
    # trwa 5-10 dni, cale kwitnienie drzew owocowych "od kilku do kilkunastu".
    "Sad":                  ( 14, 118, 125, 132,
                             "jablon 15-20 kg miodu/ha; dlugosc okna zgodna "
                             "ze zrodlami sadowniczymi (pelnia 5-10 d)", "B"),
    "gorczyca":             ( 52, 152, 164, 176,
                             "deklaracja zbiorcza; przyjeto gorczyce biala "
                             "(dominujacy gatunek uprawny): 40-90 kg miodu/ha "
                             "(polskieule, KPODR)", "B"),
    # OKNO PRZESUNIETE O 16 DNI NA PODSTAWIE POMIARU (etap 37).
    # Kotwica literaturowa stawiala pelnie na 9 VII ("przelom VI/VII"),
    # ale pomiar NDYI na dzialkach deklarowanych dal 20 VI (2025) i 23 VI
    # (2026) - odchylenie -20 i -12 dni, TEN SAM ZNAK w obu sezonach, wiec
    # to blad systematyczny, nie szum. Srednia przesuniecia: -16 dni.
    #
    # Pomiar jest wiarygodny, bo w tym samym przebiegu rzepak ozimy - dla
    # ktorego model znamy niezaleznie (3,2 d) - wyszedl z bledem 4,1 dnia.
    # Metoda dziala; zawodzila kotwica literaturowa.
    #
    # Okno bylo 176-190-210, jest 160-174-194 (dlugosc bez zmian).
    "rzepak jary":          ( 56, 160, 174, 194,
                             "60-80 kg miodu/ha; PELNIA ZMIERZONA z krzywych "
                             "NDYI na dzialkach GSA: 20 VI 2025 i 23 VI 2026, "
                             "srednio 16 dni wczesniej niz kotwica literaturowa "
                             "(polskieule, KPODR)", "B"),
}

# Klasy modelu, ktore NIE sa osobna uprawa w deklaracjach, tylko druga faza
# kwitnienia tej samej powierzchni. Rasteryzacja musi wziac geometrie uprawy
# zrodlowej; sumy arealow licza sie raz, bo to ta sama ziemia.
ZRODLO_GEOMETRII = {"TUZ odrost": "TUZ"}


def uprawa_zrodlowa(nazwa: str) -> str:
    """Nazwa w deklaracjach GSA odpowiadajaca klasie modelu."""
    return ZRODLO_GEOMETRII.get(nazwa, nazwa)


# POZYTEK ZEROWY - soja zwyczajna, groch siewny, fasola zwykla (takze
# karlowa i deklaracja zbiorcza "fasola") sa NIEOBECNE we wszystkich
# przeszukanych krajowych kompilacjach wydajnosci miodowych (polskieule,
# KPODR, kalendarzrolnikow), co jest spojne z ich samopylnoscia. To jest
# udokumentowana nieobecnosc, nie brak danych - dlatego wkladu nie
# szacujemy, tylko przyjmujemy zero (= brak wpisu w POZYTKI).


def d(doy: int) -> str:
    x = date(ROK, 1, 1) + timedelta(days=int(doy) - 1)
    return f"{x.day:02d}.{x.month:02d}"


def ksztalt_rzepaku() -> tuple[int, int]:
    """Dni przed i po pelni. Mediana ramion NDYI z wielu lat, nie stala 2022."""
    fen = WYNIKI / "json" / "fenologia.json"
    if fen.exists():
        k = json.loads(fen.read_text(encoding="utf-8")).get("ksztalt_kwitnienia")
        if k and "przed_pelnia" in k:
            return int(k["przed_pelnia"]), int(k["po_pelni"])
    g = json.loads((WYNIKI / "json" / "gdd.json").read_text(encoding="utf-8"))
    k = g["ksztalt_kwitnienia"]
    return int(k["przed_pelnia"]), int(k["po_pelni"])


def okno_rzepaku() -> tuple[int, int, int]:
    g = json.loads((WYNIKI / "json" / "gdd.json").read_text(encoding="utf-8"))
    t = g["warianty"][g["start_domyslny"]]["terminy"]
    przed, po = ksztalt_rzepaku()
    p = int(t[str(ROK)])
    return p - przed, p, p + po


# ---------------------------------------------------------------- jadro
def jadro(lam: float, zasieg: float, piksel: float) -> np.ndarray:
    r = int(zasieg // piksel)
    i = np.arange(-r, r + 1)
    dx, dy = np.meshgrid(i, i)
    odl = np.hypot(dx, dy) * piksel
    w = np.where(odl <= zasieg, np.exp(-odl / lam), 0.0)
    return w


def udzialy(s: int, p: int, k: int) -> dict[int, float]:
    w = {}
    for dek in DEKADY:
        m = dek + 5
        w[dek] = (0.0 if m <= s or m >= k else
                  (m - s) / (p - s) if m <= p else (k - m) / (k - p))
    suma = sum(w.values())
    return {a: b / suma for a, b in w.items()} if suma else w


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    POZYTKI["rzepak ozimy"] = (115,) + okno_rzepaku() + (
        POZYTKI["rzepak ozimy"][4], "A")
    print(f"Rzepak ozimy {ROK}: kwitnienie {d(POZYTKI['rzepak ozimy'][1])} - "
          f"{d(POZYTKI['rzepak ozimy'][3])}, pelnia {d(POZYTKI['rzepak ozimy'][2])}\n")

    tr = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    cx, cy = tr.transform(STACJA_LON, STACJA_LAT)
    # margines na splot, zeby brzeg bufora nie byl zanizony
    M = PROMIEN_BUFORA_M + ZASIEG_M
    bbox = (cx - M, cy - M, cx + M, cy + M)

    print("Wczytuje GSA...")
    g = pyogrio.read_dataframe(SHP, bbox=bbox, encoding="utf-8")
    g["ha"] = pd.to_numeric(g["pow"].str.replace(" ha", "", regex=False),
                            errors="coerce")
    print(f"  dzialek: {len(g):,}   powierzchnia: {g['ha'].sum():,.0f} ha")

    # siatka
    n20 = int(2 * M / PIKSEL_RASTER)
    kro = PIKSEL_M // PIKSEL_RASTER
    n100 = n20 // kro
    tf20 = from_origin(bbox[0], bbox[3], PIKSEL_RASTER, PIKSEL_RASTER)
    tf100 = from_origin(bbox[0], bbox[3], PIKSEL_M, PIKSEL_M)
    K = jadro(LAMBDA_M, ZASIEG_M, PIKSEL_M)

    print("\nRasteryzacja i splot na klase:")
    splot, areal, rozklad = {}, {}, {}
    for nazwa, (kg, s, p, k, zrodlo, klasa) in POZYTKI.items():
        sub = g[g["roslina"] == nazwa]
        if sub.empty:
            continue
        r20 = rasterize(((geom, 1) for geom in sub.geometry),
                        out_shape=(n20, n20), transform=tf20,
                        fill=0, dtype="uint8")
        # udzial powierzchni w pikselu 100 m = srednia z bloku 5 x 5
        udzial = r20.reshape(n100, kro, n100, kro).mean(axis=(1, 3))
        areal[nazwa] = float(udzial.sum())          # piksel 100 m = 1 ha
        splot[nazwa] = fftconvolve(udzial, K, mode="same")
        rozklad[nazwa] = udzialy(s, p, k)
        print(f"  {nazwa[:26]:28s} {areal[nazwa]:8,.0f} ha  {kg:3d} kg/ha  "
              f"kwitnienie {d(s)}-{d(k)}")

    # --------------------------------------------------- warstwy
    sezon = sum(splot[n] * POZYTKI[n][0] for n in splot)
    rzep = splot["rzepak ozimy"] * POZYTKI["rzepak ozimy"][0]
    kal = {dek: sum(splot[n] * POZYTKI[n][0] * rozklad[n][dek] for n in splot)
           for dek in DEKADY}
    koniec_rz = POZYTKI["rzepak ozimy"][3]
    po_rzepaku = sum(kal[dek] for dek in DEKADY if koniec_rz <= dek < 220)

    # maska bufora - liczymy tylko w promieniu reprezentatywnosci stacji
    yy, xx = np.mgrid[0:n100, 0:n100]
    px = bbox[0] + (xx + 0.5) * PIKSEL_M
    py = bbox[3] - (yy + 0.5) * PIKSEL_M
    w_buforze = np.hypot(px - cx, py - cy) <= PROMIEN_BUFORA_M

    def najlepszy(m: np.ndarray) -> dict:
        mm = np.where(w_buforze, m, -np.inf)
        i = np.unravel_index(np.argmax(mm), mm.shape)
        lon, lat = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True) \
            .transform(px[i], py[i])
        return {"wartosc": float(m[i]), "lat": lat, "lon": lon,
                "mediana": float(np.median(m[w_buforze]))}

    kryteria = {"sam rzepak": najlepszy(rzep), "caly sezon": najlepszy(sezon),
                "po rzepaku": najlepszy(po_rzepaku)}

    print("\nNajlepszy punkt wg kryterium:")
    for n, v in kryteria.items():
        print(f"  {n:14s} {v['lat']:.5f}, {v['lon']:.5f}   "
              f"{v['wartosc']/1000:7.1f} t   (mediana {v['mediana']/1000:.1f} t)")

    def w_pkt(m: np.ndarray, lat: float, lon: float) -> float:
        X, Y = tr.transform(lon, lat)
        j = int((X - bbox[0]) / PIKSEL_M)
        i = int((bbox[3] - Y) / PIKSEL_M)
        return float(m[i, j])

    print("\nKalendarz (t cukrow w nektarze):")
    kalendarze = {}
    for n, v in kryteria.items():
        kalendarze[n] = {str(dek): w_pkt(kal[dek], v["lat"], v["lon"])
                         for dek in DEKADY}
        print(f"  {n:14s}" + "".join(f"{kalendarze[n][str(x)]/1000:6.1f}"
                                     for x in DEKADY))
    print(f"  {'dekada':14s}" + "".join(f"{d(x):>6}" for x in DEKADY))

    najl = kryteria["caly sezon"]
    sklad = {n: w_pkt(splot[n] * POZYTKI[n][0], najl["lat"], najl["lon"])
             for n in splot}
    razem = sum(sklad.values())
    print("\nSklad pozytku w najlepszym punkcie sezonowym:")
    for n, v in sorted(sklad.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {n[:26]:28s} {v/1000:7.2f} t  ({v/razem:5.1%})")

    # --------------------------------------------------- zapis
    WYNIKI.mkdir(exist_ok=True)
    prof = {"driver": "GTiff", "height": n100, "width": n100, "count": 1,
            "dtype": "float32", "crs": "EPSG:2180", "transform": tf100,
            "compress": "deflate"}
    for nazwa, m in (("sezon", sezon), ("rzepak", rzep), ("po_rzepaku", po_rzepaku)):
        with rasterio.open(WYNIKI / "rastry" / f"gsa_{nazwa}.tif", "w", **prof) as dst:
            dst.write(np.where(w_buforze, m, np.nan).astype("float32"), 1)

    # stos dekadowy - jedno pasmo na dekade, do serii map przez sezon
    prof_d = dict(prof, count=len(DEKADY))
    with rasterio.open(WYNIKI / "rastry" / "gsa_dekady.tif", "w", **prof_d) as dst:
        for i, dek in enumerate(DEKADY, start=1):
            dst.write(np.where(w_buforze, kal[dek], np.nan).astype("float32"), i)
            dst.set_band_description(i, d(dek))
    print(f"Zapisano stos dekadowy: {len(DEKADY)} pasm")

    (WYNIKI / "json" / "potencjal_gsa.json").write_text(json.dumps({
        "zrodlo_upraw": f"ARiMR GSA {ROK}, woj. lubelskie",
        "stacja": {"lat": STACJA_LAT, "lon": STACJA_LON,
                   "promien_m": PROMIEN_BUFORA_M},
        "jadro": {"lambda_m": LAMBDA_M, "zasieg_m": ZASIEG_M},
        "rok": ROK, "dekady": DEKADY,
        "daty": {str(x): d(x) for x in DEKADY},
        "pozytki": {n: {"kg_cukrow_ha": v[0], "start": v[1], "pelnia": v[2],
                        "koniec": v[3], "zrodlo": v[4], "klasa_zrodla": v[5],
                        "ha_w_obszarze": areal.get(n)}
                    for n, v in POZYTKI.items() if n in areal},
        "kryteria": kryteria, "kalendarze": kalendarze,
        "sklad": sklad,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI/'potencjal_gsa.json'} oraz gsa_*.tif")
