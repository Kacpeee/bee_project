"""
Detekcja fasoli wielokwiatowej z Sentinel-2, na etykietach ARiMR GSA 2025.

PO CO
Fasola daje 15% potencjalu sezonowego i CALY pozytek lipcowy, ale w modelu
siedzi na stalej dacie z literatury, podczas gdy rzepak dostaje termin z GDD.
Kalendarz jest przez to dynamiczny w jednej polowie i zamrozony w drugiej,
a szerokosc czerwcowej przerwy zmienia sie miedzy latami tylko dlatego, ze
rusza sie rzepak. Zeby to naprawic, trzeba najpierw umiec znalezc pola fasoli
w kazdym roku - GSA jest tylko za 2025 i 2026.

SYGNATURA - ODWROTNA NIZ RZEPAKOWA
Rzepak wykrywamy po tym, ze wchodzi w zime z duza biomasa i kwitnie na zolto.
Fasola jest roslina cieplolubna sianą w maju, wiec:
  - w kwietniu pole jest golą glebą, gdy rzepak i zboza sa juz zielone
  - w lipcu fasola jest w pelni zieleni, gdy zboza zsychaja i sa zbierane
Te dwa kontrasty maja przeciwne znaki i razem sa mocniejsze niz kazdy osobno,
dlatego wsrod cech jest ich roznica.

CZEGO TU NIE MA
Detekcji KWITNIENIA. Kwiaty fasoli sa czerwone albo biale i drobne wzgledem
lanu - NDYI ich nie zobaczy. Termin kwitnienia trzeba bedzie wyprowadzic
inaczej: z daty wschodow (doskonale widocznej w NDVI, bo pole przechodzi od
golej gleby do pelnego lanu) plus sumy temperatur z baza ok. 10 °C.

Uruchomienie:
    python klasyfikator_fasoli.py
"""

from __future__ import annotations

import json
from pathlib import Path

import ee

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import gee_klasyfikator_rzepaku as K
import klasyfikator_gsa as G
from gee_klasyfikator_rzepaku import (LICZBA_DRZEW, MAX_CHMUR, orne_maska,
                                      przygotuj)
from gee_ndyi_przeglad import start

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

UPRAWA = "fasola wielokwiatowa"
ROK = 2025
SRODEK_LAT, SRODEK_LON = 50.755, 23.600
PROMIEN_M = 15_000

# okna dobrane pod cykl fasoli, nie rzepaku: siew w maju, pelnia lata w lipcu,
# zbior we wrzesniu. Wszystkie na NDVI - zoltosc tu nic nie wnosi.
OKNA = [
    ("kwiecien", "04-05", "05-05"),   # gola gleba, gdy inne uprawy zielone
    ("maj",      "05-05", "06-05"),   # siew i wschody
    ("czerwiec", "06-05", "07-05"),   # narastanie lanu
    ("lipiec",   "07-05", "08-05"),   # pelnia, gdy zboza juz zzete
    ("sierpien", "08-05", "09-05"),   # nadal zielona
    ("wrzesien", "09-05", "10-05"),   # zasychanie
]


def cechy_lata(rok: int, aoi: ee.Geometry) -> ee.Image:
    """Anomalie NDVI wzgledem mediany gruntow ornych z tej samej sceny."""
    orne = orne_maska()
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi).filterDate(f"{rok}-04-01", f"{rok}-10-10")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
           .map(przygotuj))

    def anom(img: ee.Image) -> ee.Image:
        med = (img.select("NDVI").updateMask(orne)
               .reduceRegion(ee.Reducer.median(), aoi, 200,
                             maxPixels=1e9, bestEffort=True).get("NDVI"))
        m = ee.Number(ee.Algorithms.If(med, med, 0))
        # copyProperties konieczne: subtract/rename/toFloat tworza NOWY obraz
        # bez wlasciwosci zrodla, wiec bez system:time_start kolejny filterDate
        # nie znajduje niczego i wszystkie okna wychodza puste
        return (img.select("NDVI").subtract(m).rename("A").toFloat()
                .copyProperties(img, ["system:time_start"]))

    col = col.map(anom)
    pasma = []
    for nazwa, od, do in OKNA:
        okno = col.filterDate(f"{rok}-{od}", f"{rok}-{do}")
        n = okno.size().getInfo()
        print(f"    {nazwa:10s} scen={n:3d}")
        pasma.append((ee.Image.constant(0) if n == 0 else okno.mean())
                     .rename(nazwa).toFloat().unmask(0))
    x = ee.Image.cat(pasma)
    # kluczowa cecha: odwrocenie sie kontrastu miedzy wiosna a latem
    return x.addBands(x.select("lipiec").subtract(x.select("kwiecien"))
                      .rename("odwrocenie"))


if __name__ == "__main__":
    print(f"Detekcja: {UPRAWA}, sezon {ROK}\n")
    df = G.punkty(SRODEK_LAT, SRODEK_LON, PROMIEN_M, uprawa=UPRAWA)

    start()
    aoi = ee.Geometry.Point([SRODEK_LON, SRODEK_LAT]).buffer(PROMIEN_M).bounds()
    K.AOI = aoi
    print(f"\nCechy letnie dla {ROK}:")
    x = cechy_lata(ROK, aoi).updateMask(orne_maska())
    nazwy = [o[0] for o in OKNA] + ["odwrocenie"]

    print("\nProbkowanie...")
    proba = x.sampleRegions(collection=G.kolekcja(df), scale=10,
                            geometries=False, tileScale=4)
    print(f"  punktow z kompletem cech: {proba.size().getInfo():,} z {len(df):,}")

    las = ee.Classifier.smileRandomForest(LICZBA_DRZEW).train(
        features=proba.filter(ee.Filter.eq("test", 0)),
        classProperty="rzepak", inputProperties=nazwy)
    wynik = G.macierz(
        proba.filter(ee.Filter.eq("test", 1)).classify(las)
        .errorMatrix("rzepak", "classification").array().getInfo(),
        f"WALIDACJA PRZESTRZENNA - {UPRAWA} ({ROK}, bloki 2,5 km, "
        "proba wazona powierzchnia)")

    pred = x.classify(las).rename("f").selfMask()
    ha = (pred.multiply(ee.Image.pixelArea()).divide(10_000)
          .reduceRegion(ee.Reducer.sum(), aoi, 20, maxPixels=1e10,
                        bestEffort=True).get("f").getInfo())
    print(f"\nAREAL w obszarze 30 x 30 km")
    print(f"  deklaracje ARiMR GSA {ROK}    4 202 ha")
    print(f"  model                      {ha:8,.0f} ha")

    print("\nWaznosc cech:")
    waga = las.explain().getInfo().get("importance", {})
    for k, v in sorted(waga.items(), key=lambda kv: -kv[1]):
        print(f"  {k:12s} {v:8.1f}")

    WYNIKI.mkdir(exist_ok=True)
    (WYNIKI / "json" / "klasyfikator_fasoli.json").write_text(json.dumps({
        "uprawa": UPRAWA, "rok": ROK, "okna": [list(o) for o in OKNA],
        "przestrzenna": wynik, "areal_model_ha": ha, "areal_gsa_ha": 4202,
        "waznosc_cech": waga,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'klasyfikator_fasoli.json'}")
