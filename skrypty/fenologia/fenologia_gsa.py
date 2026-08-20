"""
ETAP 3 - data kwitnienia rzepaku w kazdym sezonie + kalibracja GDD na N sezonow.

PO CO
Prog cieplny stal na JEDNEJ obserwacji (2022). Model bez bledu to nie model.
Tu wyciagamy date kwitnienia z kazdego sezonu Sentinel-2 i kalibrujemy prog na
wszystkich naraz, dostajac wreszcie RMSE w dniach.

DWIE PULAPKI I JAK SA OMIJANE

1. PLODOZMIAN. GSA jest tylko za 2025, a rzepak wraca na pole co 3-4 lata, wiec
   dzialki z 2025 nie sa rzepakiem w 2018. Pola w kazdym sezonie wskazuje wiec
   klasyfikator wyuczony na etykietach GSA.

2. CYRKULARNOSC. Klasyfikator pelnosezonowy uzywa cech z okna kwitnienia, wiec
   wskazywalby piksele, ktore zakwitly TAM, GDZIE OKNO - i data ciazylaby ku
   srodkowi okna. Dlatego uzywany jest wariant PRZEDKWITNIENIOWY: tylko jesien
   i marzec. Pola sa wskazywane sygnalem, ktory z kwitnieniem nie ma nic
   wspolnego, a dopiero potem mierzymy, kiedy zakwitly.

3. KWANTYZACJA DO DAT PRZELOTOW. Argmax po kilkunastu scenach daje wyniki typu
   139/139/139. Przez trzy najwyzsze punkty prowadzona jest parabola i brany
   jej wierzcholek - data wychodzi z dokladnoscia pod-przelotowa.

NORMALIZACJA SCENY
Mierzymy nadwyzke: srednie NDYI na pikselach rzepaku minus mediana NDYI gruntow
ornych z TEJ SAMEJ sceny. Bez tego dominuje zmiennosc atmosferyczna.

Uruchomienie:
    python fenologia_gsa.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import ee
import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import gee_klasyfikator_rzepaku as K
import klasyfikator_gsa as G
import ksztalt_ndyi as KN
import meteo_gdd as MG
from gee_klasyfikator_rzepaku import LICZBA_DRZEW, cechy, orne_maska, przygotuj
from gee_ndyi_przeglad import MAX_CHMUR, start

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

LATA = range(2017, 2027)
OKNO_OD, OKNO_DO = "03-20", "07-05"
SKALA = 100
MIN_DAT = 6

# cechy dostepne PRZED kwitnieniem - tylko nimi wskazujemy pola
CECHY_PRZED = ["jesien_ndvi", "marzec_ndvi", "marzec_ndyi"]


def d(doy: float, rok: int = 2022) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day:02d}.{x.month:02d}"


# ---------------------------------------------------------------- krzywa
def krzywa(rok: int, maska: ee.Image, aoi: ee.Geometry) -> list[dict]:
    orne = orne_maska()
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi).filterDate(f"{rok}-{OKNO_OD}", f"{rok}-{OKNO_DO}")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CHMUR))
           .map(przygotuj))

    def stat(img: ee.Image) -> ee.Feature:
        tlo = (img.select("NDYI").updateMask(orne)
               .reduceRegion(ee.Reducer.median(), aoi, SKALA,
                             maxPixels=1e9, bestEffort=True).get("NDYI"))
        rz = (img.select(["NDYI", "NDVI"]).updateMask(maska)
              .reduceRegion(ee.Reducer.mean(), aoi, SKALA,
                            maxPixels=1e9, bestEffort=True))
        pokrycie = (img.select("NDYI").updateMask(maska).mask()
                    .reduceRegion(ee.Reducer.mean(), aoi, 200,
                                  maxPixels=1e9, bestEffort=True).get("NDYI"))
        return ee.Feature(None, {
            "doy": img.select("DOY").reduceRegion(
                ee.Reducer.first(), aoi, 1000, maxPixels=1e9,
                bestEffort=True).get("DOY"),
            "ndyi_rz": rz.get("NDYI"), "ndvi_rz": rz.get("NDVI"),
            "ndyi_tlo": tlo, "pokrycie": pokrycie})

    w = [f["properties"] for f in
         ee.FeatureCollection(col.map(stat)).getInfo()["features"]]
    return [x for x in w if x.get("doy") and x.get("ndyi_rz") is not None
            and x.get("ndyi_tlo") is not None and (x.get("pokrycie") or 0) > 0.03]


def szczyt(w: list[dict]) -> tuple[float, float]:
    """Wierzcholek paraboli przez trzy najwyzsze sasiadujace punkty."""
    # dwie sceny z tego samego dnia (sasiednie orbity) daja d2 = 0 w paraboli
    scal = {}
    for v in w:
        scal.setdefault(int(v["doy"]), []).append(v["ndyi_rz"] - v["ndyi_tlo"])
    w = [{"doy": k, "n": sum(x) / len(x)} for k, x in sorted(scal.items())]
    y = [v["n"] for v in w]
    i = int(np.argmax(y))
    if i == 0 or i == len(y) - 1:
        return float(w[i]["doy"]), y[i]
    (x1, y1), (x2, y2), (x3, y3) = ((w[j]["doy"], y[j]) for j in (i - 1, i, i + 1))
    d1, d2, d3 = (x1-x2)*(x1-x3), (x2-x1)*(x2-x3), (x3-x1)*(x3-x2)
    a = y1/d1 + y2/d2 + y3/d3
    b = -y1*(x2+x3)/d1 - y2*(x1+x3)/d2 - y3*(x1+x2)/d3
    if a >= 0:
        return float(x2), y2
    v = -b / (2 * a)
    return (float(v) if x1 <= v <= x3 else float(x2)), y2


# ---------------------------------------------------------------- kalibracja
def rmse(a: dict, b: dict) -> float:
    w = sorted(set(a) & set(b))
    return (sum((a[r] - b[r]) ** 2 for r in w) / len(w)) ** 0.5 if w else float("nan")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    df_pkt = G.punkty()
    start()
    aoi = ee.Geometry.Point([G.SRODEK_LON, G.SRODEK_LAT]).buffer(G.PROMIEN_M).bounds()
    K.AOI = aoi

    print(f"\nKlasyfikator PRZEDKWITNIENIOWY ({', '.join(CECHY_PRZED)}), "
          f"etykiety GSA {G.ROK}:")
    x25 = cechy(G.ROK).updateMask(orne_maska())
    proba = x25.sampleRegions(collection=G.kolekcja(df_pkt), scale=10,
                              geometries=False, tileScale=4)
    las = ee.Classifier.smileRandomForest(LICZBA_DRZEW).train(
        features=proba.filter(ee.Filter.eq("test", 0)),
        classProperty="rzepak", inputProperties=CECHY_PRZED)
    m = (proba.filter(ee.Filter.eq("test", 1)).classify(las)
         .errorMatrix("rzepak", "classification").array().getInfo())
    (tn, fp), (fn, tp) = m[0], m[1]
    prec, czul = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    print(f"  precyzja={prec:.3f} czulosc={czul:.3f} "
          f"F1={2*prec*czul/max(prec+czul,1e-9):.3f}  (proba wazona powierzchnia)")

    print("\nKrzywa nadwyzki NDYI na pikselach wskazanych jako rzepak:")
    obs, krzywe = {}, {}
    for rok in LATA:
        try:
            maska = cechy(rok).updateMask(orne_maska()).classify(las).selfMask()
            w = krzywa(rok, maska, aoi)
        except Exception as e:
            print(f"{rok}: blad ({type(e).__name__}) - pomijam")
            continue
        if len(w) < MIN_DAT:
            print(f"{rok}: {len(w)} uzytecznych dat - pomijam")
            continue
        doy, wys = szczyt(w)
        obs[rok] = doy
        krzywe[rok] = [{"doy": int(v["doy"]),
                        "nadwyzka": v["ndyi_rz"] - v["ndyi_tlo"],
                        "ndvi": v["ndvi_rz"]} for v in sorted(w, key=lambda v: v["doy"])]
        print(f"{rok}: {len(w):2d} dat -> kwitnienie {d(doy, rok)} "
              f"(DOY {doy:5.1f}), nadwyzka {wys:.3f}")

    if len(obs) < 4:
        raise SystemExit("Za malo sezonow.")

    # --------------------------------------------------- kalibracja progu
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_dobowe.csv", parse_dates=["data"])
    dfm["gdd"] = (dfm["Tsr"] - MG.BAZA).clip(lower=0)
    print(f"\nKalibracja progu GDD (baza {MG.BAZA} °C), N = {len(obs)}:")
    naj = None
    for wariant in ("1I", "1II", "weg"):
        akum = MG.akumuluj(dfm, wariant)
        wyniki = []
        for prog in range(150, 601, 5):
            t = MG.termin(akum, prog).dropna(subset=["doy"])
            pred = {int(r.rok): int(r.doy) for r in t.itertuples()}
            wyniki.append((rmse(obs, pred), prog))
        blad, prog = min(wyniki)
        print(f"  start {wariant:4s}: prog {prog:3d} GDD -> RMSE {blad:.1f} dnia")
        if naj is None or blad < naj[0]:
            naj = (blad, prog, wariant)

    blad, prog, wariant = naj
    akum = MG.akumuluj(dfm, wariant)
    t = MG.termin(akum, prog).dropna(subset=["doy"])
    pred = {int(r.rok): int(r.doy) for r in t.itertuples()}

    sr = sum(obs.values()) / len(obs)
    stala = {r: sr for r in obs}
    lat = sorted(obs)
    pers = {lat[i]: obs[lat[i - 1]] for i in range(1, len(lat))}
    print("\nCzy model bije naiwne odniesienia (RMSE w dniach):")
    print(f"  model GDD ({wariant}, {prog} GDD)      {blad:5.1f}")
    print(f"  stala (srednia {d(sr)})           {rmse(obs, stala):5.1f}")
    print(f"  persystencja (jak rok temu)   {rmse(obs, pers):5.1f}")

    print(f"\n{'rok':>6}{'obserwacja':>13}{'model':>9}{'blad':>7}")
    for r in sorted(obs):
        if r in pred:
            print(f"{r:>6}{d(obs[r], r):>13}{d(pred[r], r):>9}{pred[r]-obs[r]:>+7.0f}")

    ksztalt = KN.ksztalt_z_krzywych(
        {str(k): v for k, v in krzywe.items()},
        {str(k): v for k, v in obs.items()})
    print(f"\nOkno NDYI (mediana, n_przed={ksztalt['n_przed']}, "
          f"n_po={ksztalt['n_po']}): "
          f"-{ksztalt['przed_pelnia']} / +{ksztalt['po_pelni']} dni")

    (WYNIKI / "json" / "fenologia.json").write_text(json.dumps({
        "metoda": "klasyfikator przedkwitnieniowy (jesien+marzec) na etykietach "
                  "GSA 2025; nadwyzka NDYI nad mediana gruntow ornych; "
                  "wierzcholek paraboli przez 3 najwyzsze punkty",
        "klasyfikator_przed": {"precyzja": prec, "czulosc": czul},
        "obserwacje": {str(k): v for k, v in obs.items()},
        "model": {"baza": MG.BAZA, "start": wariant, "prog_gdd": prog,
                  "rmse_dni": blad},
        "odniesienia": {"stala": rmse(obs, stala), "persystencja": rmse(obs, pers)},
        "przewidywania": {str(k): v for k, v in pred.items()},
        "ksztalt_kwitnienia": ksztalt,
        "krzywe": {str(k): v for k, v in krzywe.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'fenologia.json'}")
