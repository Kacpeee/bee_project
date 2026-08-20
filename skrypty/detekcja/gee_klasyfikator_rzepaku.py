"""
ETAP 2 - klasyfikator rzepaku ozimego z Sentinel-2, z walidacja przestrzenna
i miedzyroczna.

Konstrukcja cech wynika wprost z profili policzonych w gee_profil_rzepaku.py:

  1. ANOMALIA, NIE WARTOSC BEZWZGLEDNA.
     Caly wiersz profilu skacze miedzy sasiednimi scenami (DOY 139 wszystkie
     uprawy wysoko, DOY 141 wszystkie nisko) - to efekt atmosfery, nie biologii.
     Pasmo niebieskie jest na to najczulsze, wiec NDYI bezwzgledne jest
     bezuzyteczne. Kazdy piksel opisujemy odchyleniem od MEDIANY GRUNTOW ORNYCH
     Z TEJ SAMEJ SCENY. Dopiero to jest porownywalne miedzy datami i latami.

  2. SYGNATURA JEST DWUSKLADNIKOWA.
     W szczycie kwitnienia (DOY 139-141) NDYI rzepaku przewyzsza kazda inna
     uprawe o +0.15, a JEDNOCZESNIE jego NDVI spada z 0.755 do 0.622, podczas
     gdy pszenica w tych samych dniach rosnie do 0.797. Dwa ruchy w przeciwnych
     kierunkach - stad osobna cecha kwit_ndvi_min.

  3. SYGNAL MARCOWY JEST SLABSZY, NIZ SIE WYDAJE.
     W polowie marca rzepak ma NDVI ok. 0.38-0.41 przy 0.31-0.34 dla pszenicy,
     czyli +0.07. Wystarczy na wskazanie pol przed kwitnieniem, ale scenariusz
     "przed_kwitnieniem" placi za to spadkiem F1 z 0.82 do 0.60.
     (Wczesniejsza wersja podawala tu +0.14 - to byl profil LASU, patrz nizej.)

Etykiety: EUCROPMAP (JRC), klasa 232 - patrz KOD_RZEPAKU. Kod 300 to
"Woodland and Shrubland"; policzony na nim profil byl profilem lasu.
Dokladnosc mapy ok. 70%, wiec wyniki
ponizej to DOLNE oszacowanie - czesc "bledow" klasyfikatora to bledy etykiet.
Docelowo podmieniamy na poligony GSA z ARiMR.

Walidacja:
  - przestrzenna: bloki ok. 2.5 km, rozlaczne miedzy treningiem a testem
    (podzial losowy po pikselach przeciekaby informacje i dal falszywe 98%)
  - miedzyroczna: trening na 2022, test na 2018, niezalezne etykiety

Uruchomienie:
    python gee_klasyfikator_rzepaku.py
"""

from __future__ import annotations

import ee

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

from gee_ndyi_przeglad import (MAX_CHMUR, PROMIEN_M, SRODEK_LAT, SRODEK_LON,
                               pobierz_png, przygotuj, start)

# ---------------------------------------------------------------- konfiguracja
ROK_TRENINGU = 2022
ROK_TESTU = 2018            # EUCROPMAP ma tylko te dwa roczniki

KOD_RZEPAKU = 232          # wg classification_class_values zasobu; 300 to LAS
LICZBA_DRZEW = 150
PROBEK_NA_KLASE = 3000
SKALA_PROBY = 20            # m - powyzej rozdzielczosci S2, zeby ograniczyc autokorelacje
BLOK_STOPNIE = 1 / 40       # ok. 2.5 km - rozmiar bloku walidacji przestrzennej
UDZIAL_TESTU = 0.3

AOI = None


# ---------------------------------------------------------------- cechy
def orne_maska() -> ee.Image:
    return ee.Image("ESA/WorldCover/v200/2021").select("Map").eq(40)


def kolekcja_anomalii(rok: int) -> ee.ImageCollection:
    """Sezon od jesieni poprzedniego roku; kazdy piksel jako odchylenie od
    mediany gruntow ornych z tej samej sceny."""
    orne = orne_maska()
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(AOI)
           .filterDate(f"{rok - 1}-09-15", f"{rok}-07-15")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
           .map(przygotuj))

    def anom(img: ee.Image) -> ee.Image:
        med = (img.select(["NDYI", "NDVI"]).updateMask(orne)
               .reduceRegion(ee.Reducer.median(), AOI, 200,
                             maxPixels=1e9, bestEffort=True))
        # scena moze byc calkiem zachmurzona nad AOI - wtedy zero zamiast bledu
        my = ee.Number(ee.Algorithms.If(med.get("NDYI"), med.get("NDYI"), 0))
        mv = ee.Number(ee.Algorithms.If(med.get("NDVI"), med.get("NDVI"), 0))
        # toFloat() konieczne: odjecie skalara zmienia DEKLAROWANY zakres pasma,
        # przez co GEE uznaje kolekcje za niejednorodna i odmawia redukcji
        return img.addBands([
            img.select("NDYI").subtract(my).rename("NDYI_A").toFloat(),
            img.select("NDVI").subtract(mv).rename("NDVI_A").toFloat(),
        ])

    return col.map(anom)


# nazwa, od, do, pasmo, reduktor - daty wzgledem roku sezonu.
# Okna szerokie celowo: przy waskich oknach (kwiecien mial 1 scene) maski chmur
# z osmiu kompozytow mnoza sie przez siebie i wycinaja prawie caly obszar -
# proba testowa spadla wtedy do 16 punktow.
OKNA = [
    ("jesien_ndvi",   (-1, "10-01"), (-1, "11-30"), "NDVI_A", "mean"),
    ("marzec_ndvi",   (0, "03-01"),  (0, "04-10"),  "NDVI_A", "mean"),
    ("marzec_ndyi",   (0, "03-01"),  (0, "04-10"),  "NDYI_A", "mean"),
    # szczyt zoltosci: +0.15 nad najlepsza inna uprawa w DOY 139-141
    ("kwit_ndyi_max", (0, "04-20"),  (0, "06-01"),  "NDYI_A", "max"),
    ("kwit_ndyi_sr",  (0, "04-20"),  (0, "06-01"),  "NDYI_A", "mean"),
    # dolek NDVI w tych samych datach: -0.13 wzgledem wlasnego przebiegu,
    # podczas gdy zboza rosna. To druga polowa sygnatury kwitnienia.
    ("kwit_ndvi_min", (0, "04-20"),  (0, "06-01"),  "NDVI_A", "min"),
    ("kwit_ndvi_sr",  (0, "04-20"),  (0, "06-01"),  "NDVI_A", "mean"),
    ("czerwiec_ndvi", (0, "06-01"),  (0, "07-10"),  "NDVI_A", "mean"),
]


def cechy(rok: int) -> ee.Image:
    col = kolekcja_anomalii(rok)
    pasma = []
    for nazwa, (do_r, od_d), (dd_r, do_d), pasmo, red in OKNA:
        okno = col.filterDate(f"{rok + do_r}-{od_d}", f"{rok + dd_r}-{do_d}")
        n = okno.size().getInfo()
        if n == 0:
            print(f"    UWAGA: okno {nazwa} puste - zeruje")
            pasma.append(ee.Image.constant(0).rename(nazwa).toFloat())
            continue
        wybor = {"max": okno.select(pasmo).max,
                 "min": okno.select(pasmo).min,
                 "mean": okno.select(pasmo).mean}[red]
        # unmask(0) dopiero na kompozycie okna: cechy sa ANOMALIAMI wzgledem
        # mediany gruntow ornych, wiec 0 znaczy "typowe pole" - neutralne
        # wypelnienie tam, gdzie okno bylo caly czas zachmurzone. Piksele takie
        # beda ciazyly ku klasie negatywnej i to jest swiadomy kompromis.
        pasma.append(wybor().rename(nazwa).toFloat().unmask(0))
        print(f"    {nazwa:14s} scen={n:3d}")
    return ee.Image.cat(pasma)


def etykiety(rok: int) -> ee.Image:
    indeks = "EU27_2022" if rok >= 2022 else "EU28_2018"
    klasy = (ee.ImageCollection("JRC/D5/EUCROPMAP/V1")
             .filter(ee.Filter.eq("system:index", indeks))
             .first().select("classification"))
    return klasy.eq(KOD_RZEPAKU).rename("rzepak")


def bloki() -> ee.Image:
    """Ukosne pasy blokow ~2.5 km; deterministyczny podzial trening/test.

    Bez duzych mnoznikow w hashu - pasma GEE sa float32, wiec 'bx*7919 + by*104729'
    traci precyzje przy ~2e8 i mod 1000 zwraca kilka powtarzajacych sie wartosci.
    Konsekwencja byl zdegenerowany podzial: 114 punktow testowych, zero rzepaku.
    """
    ll = ee.Image.pixelLonLat()
    bx = ll.select("longitude").divide(BLOK_STOPNIE).floor()
    by = ll.select("latitude").divide(BLOK_STOPNIE).floor()
    return bx.add(by).mod(10).lt(UDZIAL_TESTU * 10).rename("test")


# ---------------------------------------------------------------- ocena
def macierz(pomylki: ee.ConfusionMatrix, opis: str) -> dict:
    m = pomylki.array().getInfo()
    # errorMatrix zwraca macierz o rozmiarze wg faktycznie wystepujacych klas -
    # przy braku pozytywow w probie bywa 1x1, wiec dopelniamy do 2x2
    m = [(w + [0, 0])[:2] for w in m] + [[0, 0]] * (2 - len(m))
    (tn, fp), (fn, tp) = m[0], m[1]
    prec = tp / (tp + fp) if tp + fp else 0.0
    czul = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * czul / (prec + czul) if prec + czul else 0.0
    print(f"\n{opis}")
    print(f"  macierz [[TN={tn:5d} FP={fp:5d}] [FN={fn:5d} TP={tp:5d}]]")
    n = sum(map(sum, m))
    print(f"  precyzja={prec:.3f}  czulosc={czul:.3f}  F1={f1:.3f}  "
          f"OA={(tp + tn) / max(n, 1):.3f}  n={n}")
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp, "precyzja": prec,
            "czulosc": czul, "f1": f1, "oa": (tp + tn) / max(n, 1), "n": n}


def areal(maska: ee.Image, opis: str) -> float:
    ha = (maska.multiply(ee.Image.pixelArea()).divide(10_000)
          .reduceRegion(ee.Reducer.sum(), AOI, 20, maxPixels=1e10,
                        bestEffort=True).get("rzepak").getInfo())
    print(f"  {opis:34s} {ha:8,.0f} ha")
    return ha


# Scenariusze roznia sie WYLACZNIE zestawem cech - dane, probkowanie i podzial
# przestrzenny sa te same, wiec roznica w metrykach jest czysta.
SCENARIUSZE = {
    "pelny_sezon": [o[0] for o in OKNA],
    "przed_kwitnieniem": ["jesien_ndvi", "marzec_ndvi", "marzec_ndyi"],
    "tylko_kwitnienie": ["kwit_ndyi_max", "kwit_ndyi_sr",
                         "kwit_ndvi_min", "kwit_ndvi_sr"],
}


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    import json
    from pathlib import Path

    start()
    AOI = ee.Geometry.Point([SRODEK_LON, SRODEK_LAT]).buffer(PROMIEN_M).bounds()
    orne = orne_maska()
    podzial = bloki()
    nazwy = [o[0] for o in OKNA]

    print(f"\nCechy dla sezonu {ROK_TRENINGU}:")
    x_tren = cechy(ROK_TRENINGU)
    y_tren = etykiety(ROK_TRENINGU)
    stos = x_tren.addBands(y_tren).addBands(podzial).updateMask(orne)

    print(f"\nCechy dla sezonu {ROK_TESTU}:")
    stos_18 = cechy(ROK_TESTU).addBands(etykiety(ROK_TESTU)).updateMask(orne)

    # Probkujemy RAZ, wszystkie cechy naraz. Scenariusze uzywaja tych samych
    # punktow, tylko z innym podzbiorem kolumn - inaczej roznice w metrykach
    # mieszalyby sie z losowoscia probkowania.
    proba_tr = (stos.updateMask(podzial.Not())
                .stratifiedSample(numPoints=PROBEK_NA_KLASE, classBand="rzepak",
                                  region=AOI, scale=SKALA_PROBY, seed=42,
                                  geometries=False, tileScale=4))
    proba_te = (stos.updateMask(podzial)
                .sample(region=AOI, scale=SKALA_PROBY, numPixels=40000,
                        seed=7, geometries=False, tileScale=8))
    proba_18 = stos_18.sample(region=AOI, scale=SKALA_PROBY, numPixels=40000,
                              seed=7, geometries=False, tileScale=8)
    print(f"\nProba treningowa: {proba_tr.size().getInfo()} punktow")

    ha_etykiet = {
        ROK_TRENINGU: areal(y_tren.updateMask(orne), f"etykiety {ROK_TRENINGU}"),
        ROK_TESTU: areal(etykiety(ROK_TESTU).updateMask(orne),
                         f"etykiety {ROK_TESTU}"),
    }

    wyniki = {}
    for nazwa, cechy_sc in SCENARIUSZE.items():
        print(f"\n{'=' * 68}\nSCENARIUSZ: {nazwa}  ({len(cechy_sc)} cech)")
        print("  " + ", ".join(cechy_sc))
        las = ee.Classifier.smileRandomForest(LICZBA_DRZEW).train(
            features=proba_tr, classProperty="rzepak", inputProperties=cechy_sc)

        przestrz = macierz(
            proba_te.classify(las).errorMatrix("rzepak", "classification"),
            f"walidacja przestrzenna ({ROK_TRENINGU}, rozlaczne bloki 2.5 km)")
        miedzyrocz = macierz(
            proba_18.classify(las).errorMatrix("rzepak", "classification"),
            f"walidacja miedzyroczna (model {ROK_TRENINGU} -> dane {ROK_TESTU})")

        print("  areal:")
        pred = x_tren.updateMask(orne).classify(las).rename("rzepak")
        ha22 = areal(pred, f"model {ROK_TRENINGU}")
        ha18 = areal(stos_18.select(nazwy).classify(las).rename("rzepak"),
                     f"model {ROK_TESTU}")

        url = pred.selfMask().getThumbURL({
            "region": AOI, "dimensions": 1100, "min": 0, "max": 1,
            "palette": ["ffd400"], "format": "png"})

        wyniki[nazwa] = {
            "cechy": cechy_sc, "przestrzenna": przestrz,
            "miedzyroczna": miedzyrocz,
            "areal": {str(ROK_TRENINGU): ha22, str(ROK_TESTU): ha18},
            "mapa": pobierz_png(url, f"mapa_{nazwa}.png"),
        }

    wyj = Path(__file__).resolve().parents[2] / "wyniki"
    wyj.mkdir(exist_ok=True)
    (wyj / "json" / "scenariusze.json").write_text(json.dumps({
        "rok_treningu": ROK_TRENINGU, "rok_testu": ROK_TESTU,
        "areal_etykiet": {str(k): v for k, v in ha_etykiet.items()},
        "scenariusze": wyniki,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {wyj / 'scenariusze.json'}")
