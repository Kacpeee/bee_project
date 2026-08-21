"""
Jaka jest trafnosc klasyfikatora NA PIKSELU, a nie w srodku dzialki.

PO CO
Raportowane F1 0,940 dla rzepaku liczy sie na JEDNYM punkcie reprezentatywnym
na dzialke, w jej wnetrzu, po zwezeniu o 10 m. Wdrozenie klasyfikuje KAZDY
piksel - takze brzegowy, ktory zahacza o sasiednie pole i ma sygnal mieszany.
To sa dwie rozne liczby i mylenie ich zawyza obraz jakosci.

Starszy pomiar pikselowy istnieje (detekcja_wojewodztwo.json: precyzja 0,707,
czulosc 0,672), ale dotyczy klasyfikatora 3-cechowego, nie obecnego
wielogatunkowego S1+S2. Zestawienie "0,940 na dzialce vs 0,689 na pikselu"
miesza wiec dwie zmiany naraz: poziom agregacji I model.

CO ROBI TEN SKRYPT
Losuje piksele WEWNATRZ dzialek z blokow TESTOWYCH, zapisujac dla kazdego
odleglosc od granicy dzialki. Model uczy sie na blokach treningowych
(z istniejacego cache, bez ponownego pobierania). Wynik: trafnosc pikselowa
ogolem ORAZ w funkcji odleglosci od miedzy - to ona rozstrzyga, czy blad
bierze sie z modelu, czy z natury pikseli brzegowych.

Bloki testowe wyznacza ta sama regula co klasyfikator_wielo.py
((bx+by) % 10), wiec zbior treningowy i testowy pozostaja rozlaczne.

Uruchomienie:
    python skrypty/detekcja/ocena_pikselowa.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from pyproj import Transformer
from shapely.geometry import Point

sys.path[:0] = [str(p) for p in Path(__file__).resolve().parents[1].iterdir()
                if p.is_dir()]

import ee                                                    # noqa: E402
import gee_klasyfikator_rzepaku as K                         # noqa: E402
import potencjal_gsa as P                                    # noqa: E402
from cechy_s1s2 import cechy                                 # noqa: E402
from wielo_diagnoza import ODRZUC, SCAL                      # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

ROK = 2025
BLOK_M = 2500
UDZIAL_TESTU = 0.3
ZIARNO = 42
DRZEW = 300
GRUPA = {"koniczyna czerwona": "motylkowe pastewne",
         "lucerna mieszańcowa": "motylkowe pastewne"}

DZIALEK_NA_KLASE = 260     # tyle dzialek testowych na gatunek
PIKSELI_NA_DZIALKE = 4     # tyle pikseli w kazdej
CACHE = WYNIKI / "cache" / "piksele_punkty.csv"
CACHE_CECH = WYNIKI / "cache" / "piksele_cechy.csv"
KROK = 1000                # punktow na jedno zapytanie do GEE


def punkty() -> pd.DataFrame:
    """Piksele wewnatrz dzialek testowych, z odlegloscia od granicy."""
    if CACHE.exists():
        d = pd.read_csv(CACHE)
        print(f"punkty z cache: {len(d):,}")
        return d

    rng = np.random.default_rng(ZIARNO)
    do4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    czesci = []
    for nazwa in list(P.POZYTKI):
        g = pyogrio.read_dataframe(
            SHP, encoding="utf-8",
            where="roslina IN ('" + nazwa.replace("'", "''") + "')")
        if g.empty:
            print(f"  {nazwa[:24]:26s} BRAK")
            continue
        sr = g.geometry.representative_point()
        bx = np.floor(sr.x.values / BLOK_M).astype(int)
        by = np.floor(sr.y.values / BLOK_M).astype(int)
        g = g[((bx + by) % 10) < UDZIAL_TESTU * 10]      # tylko bloki TESTOWE
        # dzialki ponizej 0,3 ha nie maja wnetrza - piksel 10 m to 1% ich pola
        g = g[g.geometry.area >= 3000]
        if g.empty:
            continue
        g = g.sample(n=min(DZIALEK_NA_KLASE, len(g)), random_state=ZIARNO)

        wiersze = []
        for idx, geom in zip(g.index, g.geometry):
            minx, miny, maxx, maxy = geom.bounds
            proby, ile = 0, 0
            # losowanie odrzucajace: punkt musi lezec w dzialce
            while ile < PIKSELI_NA_DZIALKE and proby < 200:
                proby += 1
                px = rng.uniform(minx, maxx)
                py = rng.uniform(miny, maxy)
                p = Point(px, py)
                if not geom.contains(p):
                    continue
                wiersze.append({"x": px, "y": py, "etykieta": nazwa,
                                "dzialka": int(idx),
                                # odleglosc do miedzy - klucz calej analizy
                                "od_granicy_m": float(geom.exterior.distance(p))
                                if geom.geom_type == "Polygon"
                                else float(geom.boundary.distance(p)),
                                "pow_ha": float(geom.area) / 10_000})
                ile += 1
        czesci.append(pd.DataFrame(wiersze))
        print(f"  {nazwa[:24]:26s} {len(g):5,} dzialek -> "
              f"{len(wiersze):6,} pikseli")

    d = pd.concat(czesci, ignore_index=True)
    d["lon"], d["lat"] = do4326.transform(d["x"].values, d["y"].values)
    d = d.reset_index(drop=True)
    d["i"] = d.index
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(CACHE, index=False)
    print(f"\nrazem {len(d):,} pikseli z {d.dzialka.nunique():,} dzialek")
    return d


def pobierz_cechy(d: pd.DataFrame) -> pd.DataFrame:
    if CACHE_CECH.exists():
        X = pd.read_csv(CACHE_CECH).set_index("i")
        print(f"cechy z cache: {X.shape}")
        return X
    K.AOI = ee.Geometry.Rectangle(
        [float(d.lon.min()) - .1, float(d.lat.min()) - .1,
         float(d.lon.max()) + .1, float(d.lat.max()) + .1],
        "EPSG:4326", False)
    obraz, nazwy = cechy(ROK, z_radarem=True)
    print(f"cech: {len(nazwy)}")

    czesci, t0 = [], time.time()
    for i in range(0, len(d), KROK):
        pod = d.iloc[i:i + KROK]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"i": int(r.i)})
            for r in pod.itertuples()])
        for prob in range(4):
            try:
                got = obraz.reduceRegions(fc, ee.Reducer.first(), 10).getInfo()
                break
            except Exception as e:
                if prob == 3:
                    raise
                print(f"    ponawiam ({str(e)[:50]})")
                time.sleep(20 * (prob + 1))
        czesci.append(pd.DataFrame([f["properties"] for f in got["features"]]))
        zrob = min(i + KROK, len(d))
        tempo = (time.time() - t0) / zrob
        print(f"  {zrob:6,}/{len(d):,}  "
              f"pozostalo ~{tempo * (len(d) - zrob) / 60:.0f} min", flush=True)
    X = pd.concat(czesci, ignore_index=True).set_index("i").sort_index()
    X.to_csv(CACHE_CECH, index_label="i")
    return X


if __name__ == "__main__":
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import f1_score, precision_score, recall_score

    K.start()
    d = punkty()
    X = pobierz_cechy(d)

    # ---- model uczony na blokach TRENINGOWYCH, z istniejacego cache
    tr = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    Xt = (pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
          .join(pd.read_csv(WYNIKI / "cache" / "wielo_cechy_s1.csv")
                .set_index("i")))
    tr = tr.reset_index(drop=True).join(Xt)
    tr = tr[(tr.test == 0) & (~tr.etykieta.isin(ODRZUC))].copy()
    tr["grupa"] = tr.etykieta.replace(SCAL).replace(GRUPA)

    kol = [c for c in Xt.columns
           if c.startswith(("ndvi", "ndyi", "vv_", "vh_", "rat_"))]
    kol = [c for c in kol if c in X.columns]
    tr = tr.dropna(subset=kol)
    print(f"\ntrening: {len(tr):,} dzialek (bloki treningowe), {len(kol)} cech")

    te = d.join(X[kol], on="i")
    te = te[~te.etykieta.isin(ODRZUC)].copy()
    te["grupa"] = te.etykieta.replace(SCAL).replace(GRUPA)
    te = te.dropna(subset=kol)
    print(f"test:    {len(te):,} pikseli z {te.dzialka.nunique():,} dzialek")

    las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                 random_state=ZIARNO).fit(tr[kol], tr.grupa)
    te["pred"] = las.predict(te[kol])

    def miary(s, kl):
        y = (s.grupa == kl).astype(int)
        p = (s.pred == kl).astype(int)
        if y.sum() == 0:
            return None
        return {"precyzja": float(precision_score(y, p, zero_division=0)),
                "czulosc": float(recall_score(y, p, zero_division=0)),
                "f1": float(f1_score(y, p, zero_division=0)),
                "n": int(y.sum())}

    print("\n" + "=" * 62)
    print("TRAFNOSC NA PIKSELU (model bez blokow testowych)")
    f1m = f1_score(te.grupa, te.pred, average="macro")
    print(f"  F1-makro {f1m:.3f}")
    rz = miary(te, "rzepak ozimy")
    print(f"  rzepak: precyzja {rz['precyzja']:.3f}  czulosc {rz['czulosc']:.3f}"
          f"  F1 {rz['f1']:.3f}  (n={rz['n']:,})")

    # ---- KLUCZOWE: trafnosc wg odleglosci od miedzy
    print("\nRZEPAK WG ODLEGLOSCI OD GRANICY DZIALKI")
    pasma = [(0, 10), (10, 20), (20, 40), (40, 80), (80, 10_000)]
    wg_pasm = {}
    print(f"{'pasmo':>14}{'pikseli':>10}{'precyzja':>10}{'czulosc':>9}{'F1':>7}")
    for a, b in pasma:
        s = te[(te.od_granicy_m >= a) & (te.od_granicy_m < b)]
        m = miary(s, "rzepak ozimy")
        if not m:
            continue
        wg_pasm[f"{a}-{b}"] = m
        et = f"{a}-{b} m" if b < 10_000 else f">{a} m"
        print(f"{et:>14}{len(s):>10,}{m['precyzja']:>10.3f}"
              f"{m['czulosc']:>9.3f}{m['f1']:>7.3f}")

    # ---- to samo, ale zagregowane do dzialki (glosowanie wiekszosciowe)
    agg = (te.groupby("dzialka")
             .agg(grupa=("grupa", "first"),
                  pred=("pred", lambda s: s.value_counts().index[0])))
    m_dz = miary(agg, "rzepak ozimy")
    print(f"\nPO AGREGACJI DO DZIALKI (glosowanie {PIKSELI_NA_DZIALKE} pikseli)")
    print(f"  rzepak: precyzja {m_dz['precyzja']:.3f}  "
          f"czulosc {m_dz['czulosc']:.3f}  F1 {m_dz['f1']:.3f}")
    print(f"  F1-makro {f1_score(agg.grupa, agg.pred, average='macro'):.3f}")

    (WYNIKI / "json" / "ocena_pikselowa.json").write_text(json.dumps({
        "rok": ROK,
        "opis": "trafnosc na pikselu vs w srodku dzialki; model uczony "
                "wylacznie na blokach treningowych",
        "pikseli": int(len(te)), "dzialek": int(te.dzialka.nunique()),
        "pikseli_na_dzialke": PIKSELI_NA_DZIALKE,
        "f1_makro_piksel": float(f1m),
        "rzepak_piksel": rz,
        "rzepak_wg_odleglosci": wg_pasm,
        "rzepak_po_agregacji": m_dz,
        "f1_makro_po_agregacji": float(
            f1_score(agg.grupa, agg.pred, average="macro")),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano wyniki/json/ocena_pikselowa.json")
