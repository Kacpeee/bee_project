"""
ETAP 2b - klasyfikator rzepaku na ETYKIETACH ARiMR, sezon 2025.

Roznica wzgledem wersji na EUCROPMAP jest zasadnicza: tamta mierzyla ZGODNOSC
z mapa o dokladnosci ok. 70%, ta mierzy DOKLADNOSC wzgledem deklaracji rolnika.
Dopiero te liczby mozna nazwac dokladnoscia klasyfikacji.

JAK ETYKIETY TRAFIAJA DO GEE
Shapefile ma 1,5 mln obiektow i 411 MB - nie ma sensu go wgrywac. Zamiast tego
losujemy punkty wewnatrz dzialek lokalnie i przekazujemy je do GEE inline jako
GeoJSON. Kilka tysiecy punktow to kilkaset kilobajtow.

BUFOR UJEMNY 10 m
Mediana dzialki rzepakowej w tym obszarze to 1,16 ha, a wiele z nich to waskie
zagony. Punkt wylosowany przy krawedzi trafia w piksel mieszany i psuje etykiete.
Dlatego kazda dzialka jest najpierw zwezana o 10 m; te, ktore po zwezeniu znikaja,
odpadaja z proby. To jednoczesnie filtr jakosci i filtr rozdrobnienia.

PODZIAL PRZESTRZENNY
Bloki 2,5 km liczone w EPSG:2180, rozlaczne miedzy treningiem a testem.

Uruchomienie:
    python klasyfikator_gsa.py
"""

from __future__ import annotations

import json
from pathlib import Path

import ee
import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import gee_klasyfikator_rzepaku as K
from gee_klasyfikator_rzepaku import LICZBA_DRZEW, OKNA, cechy, orne_maska
from gee_ndyi_przeglad import start

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

# ---------------------------------------------------------------- konfiguracja
SRODEK_LAT, SRODEK_LON = 50.755, 23.600
PROMIEN_M = 15_000
ROK = 2025

RZEPAK = "rzepak ozimy"
BUFOR_UJEMNY = -10          # m - odsuniecie od krawedzi dzialki
PROBEK_NA_KLASE = 3000
BLOK_M = 2500
UDZIAL_TESTU = 0.3
ZIARNO = 42


# ---------------------------------------------------------------- proba
def punkty(lat: float | None = None, lon: float | None = None,
           promien: float | None = None, cicho: bool = False,
           uprawa: str | None = None) -> pd.DataFrame:
    """Proba punktowa wokol zadanego srodka; domyslnie rzepak w obszarze
    pilotazowym. Parametr uprawa pozwala uzyc tego samego kodu dla fasoli."""
    lat = SRODEK_LAT if lat is None else lat
    lon = SRODEK_LON if lon is None else lon
    promien = PROMIEN_M if promien is None else promien
    p_ = (lambda *a, **k: None) if cicho else print

    tr = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    cx, cy = tr.transform(lon, lat)
    bbox = (cx - promien, cy - promien, cx + promien, cy + promien)

    g = pyogrio.read_dataframe(SHP, bbox=bbox, encoding="utf-8")
    p_(f"dzialek w obszarze: {len(g):,}")

    g["rzepak"] = (g["roslina"] == (uprawa or RZEPAK)).astype(int)
    g["ha"] = pd.to_numeric(g["pow"].str.replace(" ha", "", regex=False),
                            errors="coerce").fillna(0)

    # zwezenie o 10 m; puste geometrie = dzialka za waska na czysty piksel
    wnetrze = g.geometry.buffer(BUFOR_UJEMNY)
    g = g.loc[~wnetrze.is_empty].copy()
    g["geometry"] = wnetrze[~wnetrze.is_empty]
    p_(f"  po zwezeniu o {abs(BUFOR_UJEMNY)} m: {len(g):,} dzialek")

    # bloki przestrzenne wyznaczane na DZIALKACH, zanim cokolwiek losujemy
    sr = g.geometry.representative_point()
    g["x"], g["y"] = sr.x.values, sr.y.values
    bx = np.floor(g["x"] / BLOK_M).astype(int)
    by = np.floor(g["y"] / BLOK_M).astype(int)
    g["test"] = (((bx + by) % 10) < UDZIAL_TESTU * 10).astype(int)

    czesci = []
    # TRENING - zbalansowany, bo las uczy sie lepiej przy rownych klasach
    tren = g[g["test"] == 0]
    for klasa in (1, 0):
        sub = tren[tren["rzepak"] == klasa]
        n = min(PROBEK_NA_KLASE, len(sub))
        wyb = sub.sample(n=n, random_state=ZIARNO)
        czesci.append(wyb.assign(zbior="trening"))
        p_(f"  trening, klasa {klasa}: {n:,} punktow z {len(sub):,} dzialek")

    # TEST - wazony POWIERZCHNIA, zeby udzial rzepaku odpowiadal terenowi.
    # Proba zbalansowana dawalaby precyzje zawyzona: przy 56% rzepaku zamiast
    # rzeczywistych ~16% falszywe pozytywy rozkladaja sie na wiekszy mianownik.
    # Losowanie wazone bez zwracania metoda Gumbela: klucz = log(waga) + szum
    # Gumbela, bierzemy najwyzsze n. pandas.sample(weights=...) wywraca sie tu
    # na skrajnie nierownym rozkladzie powierzchni dzialek.
    te = g[(g["test"] == 1) & (g["ha"] > 0)].copy()
    n_te = min(PROBEK_NA_KLASE * 2, len(te))
    rng = np.random.default_rng(ZIARNO)
    klucz = np.log(te["ha"].to_numpy()) + rng.gumbel(size=len(te))
    wyb = te.iloc[np.argsort(-klucz)[:n_te]]
    czesci.append(wyb.assign(zbior="test"))
    p_(f"  test wazony powierzchnia: {n_te:,} punktow, "
          f"udzial rzepaku {wyb['rzepak'].mean():.1%}")

    df = pd.concat(czesci, ignore_index=True)[
        ["x", "y", "rzepak", "roslina", "test", "zbior"]]

    do4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    df["lon"], df["lat"] = do4326.transform(df["x"].values, df["y"].values)
    p_(f"razem punktow: {len(df):,}")
    return df


def kolekcja(df: pd.DataFrame) -> ee.FeatureCollection:
    """Punkty przekazane inline - bez wgrywania zasobu."""
    return ee.FeatureCollection({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
             "properties": {"rzepak": int(r.rzepak), "test": int(r.test)}}
            for r in df.itertuples()],
    })


# ---------------------------------------------------------------- ocena
def macierz(m: list[list[int]], opis: str) -> dict:
    m = [(w + [0, 0])[:2] for w in m] + [[0, 0]] * (2 - len(m))
    (tn, fp), (fn, tp) = m[0], m[1]
    prec = tp / (tp + fp) if tp + fp else 0.0
    czul = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * czul / (prec + czul) if prec + czul else 0.0
    n = tn + fp + fn + tp
    print(f"\n{opis}")
    print(f"  macierz [[TN={tn:5d} FP={fp:5d}] [FN={fn:5d} TP={tp:5d}]]")
    print(f"  precyzja={prec:.3f}  czulosc={czul:.3f}  F1={f1:.3f}  "
          f"OA={(tp + tn) / max(n, 1):.3f}  n={n}")
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp, "precyzja": prec,
            "czulosc": czul, "f1": f1, "oa": (tp + tn) / max(n, 1), "n": n}


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    df = punkty()

    start()
    K.AOI = ee.Geometry.Point([SRODEK_LON, SRODEK_LAT]).buffer(PROMIEN_M).bounds()
    print(f"\nCechy dla sezonu {ROK}:")
    x = cechy(ROK).updateMask(orne_maska())
    nazwy = [o[0] for o in OKNA]

    print("\nProbkowanie cech w punktach GSA...")
    proba = x.sampleRegions(collection=kolekcja(df), scale=10,
                            geometries=False, tileScale=4)
    n_proba = proba.size().getInfo()
    print(f"  punktow z kompletem cech: {n_proba:,} z {len(df):,}")

    tren = proba.filter(ee.Filter.eq("test", 0))
    test = proba.filter(ee.Filter.eq("test", 1))
    las = ee.Classifier.smileRandomForest(LICZBA_DRZEW).train(
        features=tren, classProperty="rzepak", inputProperties=nazwy)
    print(f"  trening: {tren.size().getInfo():,}   test: {test.size().getInfo():,}")

    wynik = macierz(
        test.classify(las).errorMatrix("rzepak", "classification").array().getInfo(),
        f"WALIDACJA PRZESTRZENNA na etykietach ARiMR ({ROK}, bloki 2,5 km)")

    # areal wg modelu vs deklaracje
    pred = x.classify(las).rename("rzepak").selfMask()
    ha = (pred.multiply(ee.Image.pixelArea()).divide(10_000)
          .reduceRegion(ee.Reducer.sum(), K.AOI, 20, maxPixels=1e10,
                        bestEffort=True).get("rzepak").getInfo())
    print(f"\nAREAL RZEPAKU w obszarze {2 * PROMIEN_M / 1000:.0f} x "
          f"{2 * PROMIEN_M / 1000:.0f} km")
    print(f"  deklaracje ARiMR (GSA {ROK})   10 808 ha")
    print(f"  model                          {ha:8,.0f} ha")

    print("\nWaznosc cech:")
    waga = las.explain().getInfo().get("importance", {})
    for k, v in sorted(waga.items(), key=lambda kv: -kv[1]):
        print(f"  {k:14s} {v:8.1f}")

    WYNIKI.mkdir(exist_ok=True)
    (WYNIKI / "json" / "klasyfikator_gsa.json").write_text(json.dumps({
        "rok": ROK, "etykiety": f"ARiMR GSA {ROK}",
        "bufor_ujemny_m": BUFOR_UJEMNY, "blok_m": BLOK_M,
        "punktow": int(n_proba), "przestrzenna": wynik,
        "areal_model_ha": ha, "areal_gsa_ha": 10808,
        "waznosc_cech": waga,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'klasyfikator_gsa.json'}")
