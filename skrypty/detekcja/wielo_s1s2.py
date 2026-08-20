"""
ETAP 18b - czy radar (Sentinel-1) poprawia rozpoznawanie pozytkow?

TEST JEST POROWNAWCZY
Te same punkty, ten sam podzial przestrzenny, ten sam las losowy - rozni sie
wylacznie zestaw cech:
    S2      52 okna optyczne (stan obecny)
    S1      78 okien radarowych (VV, VH, VH-VV)
    S1+S2   130 cech
Roznica miedzy kolumnami jest wartoscia radaru, zmierzona a nie zalozona.

Sprawdzane sa dwie miary, bo dla mapy licza sie rozne rzeczy:
    F1 na punkcie   - czy model trafia w pojedyncza dzialke
    r po agregacji  - czy trafia w ZAGESZCZENIE rejonu (mapa i tak rozmywa
                      wszystko jadrem 3 km, wiec to jest miara wlasciwa)

Cechy radarowe sa pobierane raz i cache'owane - dalsze eksperymenty ida
lokalnie, bez GEE.

Uruchomienie:
    python skrypty/detekcja/wielo_s1s2.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import ee
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import gee_klasyfikator_rzepaku as K
from cechy_s1s2 import cechy
from wielo_diagnoza import ODRZUC, SCAL

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
ROK = 2025
DRZEW = 300
ZIARNO = 42
CACHE_S1 = WYNIKI / "cache" / "wielo_cechy_s1.csv"
GRUPA = {"koniczyna czerwona": "motylkowe pastewne",
         "lucerna mieszańcowa": "motylkowe pastewne"}


def pobierz_s1(df: pd.DataFrame, krok: int = 1200) -> pd.DataFrame:
    if CACHE_S1.exists():
        X = pd.read_csv(CACHE_S1).set_index("i")
        print(f"cechy S1 z cache: {X.shape}")
        return X
    # AOI musi byc ustawione PRZED budowa kolekcji - bez tego filterBounds
    # zwraca pustke i median() daje obraz bez pasm
    K.AOI = ee.Geometry.Rectangle(
        [float(df.lon.min()) - .1, float(df.lat.min()) - .1,
         float(df.lon.max()) + .1, float(df.lat.max()) + .1],
        "EPSG:4326", False)
    from cechy_s1s2 import kolekcja_s1
    n_scen = kolekcja_s1(ROK).size().getInfo()
    print(f"scen Sentinel-1 (IW, zstepujaca, VV+VH): {n_scen}")
    if n_scen == 0:
        raise SystemExit("brak scen S1 - sprawdz filtry orbity/polaryzacji")
    obraz, nazwy = cechy(ROK, z_radarem=True)
    rad = [n for n in nazwy if n.startswith(("vv_", "vh_", "rat_"))]
    obraz = obraz.select(rad)
    print(f"cech radarowych: {len(rad)}")
    czesci = []
    for i in range(0, len(df), krok):
        pod = df.iloc[i:i + krok]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([r.lon, r.lat]), {"i": int(r.Index)})
            for r in pod.itertuples()])
        pr = obraz.sampleRegions(collection=fc, scale=10, geometries=False,
                                 tileScale=8)
        for prob in range(4):
            try:
                d = pr.getInfo()
                break
            except Exception as e:
                if prob == 3:
                    raise
                print(f"    ponawiam ({str(e)[:40]})")
                time.sleep(20 * (prob + 1))
        czesci.append(pd.DataFrame([f["properties"] for f in d["features"]]))
        print(f"  S1 {min(i + krok, len(df)):6,}/{len(df):,}")
    X = pd.concat(czesci, ignore_index=True).set_index("i").sort_index()
    X.to_csv(CACHE_S1, index_label="i")
    return X


def ocen(d, kol, nazwa):
    tr, te = d[d.test == 0], d[d.test == 1]
    las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                 random_state=ZIARNO).fit(tr[kol], tr.grupa)
    te = te.assign(pred=las.predict(te[kol]),
                   cx=(te.x // 10000).astype(int),
                   cy=(te.y // 10000).astype(int))
    f1m = f1_score(te.grupa, te.pred, average="macro")
    wy = {}
    for g in sorted(te.grupa.unique()):
        f1 = f1_score((te.grupa == g).astype(int), (te.pred == g).astype(int))
        a = te.groupby(["cx", "cy"]).apply(
            lambda s: pd.Series({"p": (s.pred == g).sum(),
                                 "t": (s.grupa == g).sum()}),
            include_groups=False)
        a = a[a.sum(axis=1) > 0]
        r = (float(np.corrcoef(a.p, a.t)[0, 1])
             if len(a) > 3 and a.p.std() > 0 else float("nan"))
        wy[g] = {"f1": f1, "r": r}
    print(f"{nazwa:12s} cech {len(kol):4d}   F1-makro {f1m:.3f}")
    return wy, f1m, las


if __name__ == "__main__":
    K.start()
    df = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    X2 = pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
    X1 = pobierz_s1(df)

    k2 = [c for c in X2.columns if c.startswith(("ndvi", "ndyi"))]
    k1 = [c for c in X1.columns if c.startswith(("vv_", "vh_", "rat_"))]
    d = df.reset_index(drop=True).join(X2[k2]).join(X1[k1])
    d = d[~d.etykieta.isin(ODRZUC)].copy()
    d["grupa"] = d.etykieta.replace(SCAL).replace(GRUPA)
    d = d.dropna(subset=k2 + k1)
    # -99 = brak sceny radarowej w oknie
    zle1 = [c for c in k1 if (d[c] <= -98).mean() > .25]
    zle2 = [c for c in k2 if (d[c] == 0).mean() > .25]
    k1o = [c for c in k1 if c not in zle1]
    k2o = [c for c in k2 if c not in zle2]
    print(f"\npunktow {len(d):,}; okna puste: S2 {len(zle2)}/{len(k2)}, "
          f"S1 {len(zle1)}/{len(k1)}")

    print("\nPOROWNANIE ZESTAWOW CECH")
    wS2, fS2, _ = ocen(d, k2o, "S2")
    wS1, fS1, _ = ocen(d, k1o, "S1")
    wOB, fOB, las = ocen(d, k2o + k1o, "S1+S2")

    print(f"\n{'gatunek':26s}{'F1 S2':>8}{'F1 S1+S2':>10}{'zysk':>8}"
          f"{'r S2':>8}{'r S1+S2':>10}")
    for g in sorted(wS2):
        a, b = wS2[g], wOB[g]
        print(f"{g[:24]:26s}{a['f1']:>8.3f}{b['f1']:>10.3f}"
              f"{b['f1']-a['f1']:>+8.3f}{a['r']:>8.3f}{b['r']:>10.3f}")

    waz = pd.Series(las.feature_importances_, index=k2o + k1o)
    udz1 = waz[[c for c in k1o]].sum()
    print(f"\nudzial cech radarowych w waznosci modelu: {udz1:.1%}")
    print("10 najwazniejszych: " +
          ", ".join(waz.sort_values(ascending=False).head(10).index))

    (WYNIKI / "json" / "wielo_s1s2.json").write_text(json.dumps({
        "rok": ROK, "f1_makro": {"S2": fS2, "S1": fS1, "S1_S2": fOB},
        "n_cech": {"S2": len(k2o), "S1": len(k1o), "S1_S2": len(k2o) + len(k1o)},
        "okna_puste": {"S2": len(zle2), "S1": len(zle1)},
        "per_gatunek": {g: {"S2": wS2[g], "S1_S2": wOB[g]} for g in wS2},
        "waznosc_radaru": float(udz1),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano wielo_s1s2.json")
