"""
ETAP 18c - test przenoszenia miedzy latami Z RADAREM: ucz 2025, sprawdz 2026.

DLACZEGO POWTARZAMY TEN TEST
Pierwsza wersja (wielo_transfer.py, same cechy optyczne) byla kaleka nie
z winy modelu: sezon 2026 jeszcze trwa, wiec oba okna wrzesniowe Sentinela-2
byly puste w 100%, a sierpniowe w 37%. Zeby test byl uczciwy, trzeba bylo
wyrzucic 16 z 52 okien - i wypadly wlasnie te, ktore odrozniaja rosliny
pozne. Slonecznik, gryka i fasola dostawaly ocene bez danych z wlasnego
okresu kwitnienia.

Sentinel-1 tej dziury nie ma: radar leci co 6 dni niezaleznie od chmur,
a w tescie na 2025 dal 0 pustych okien na 78 (wobec 8 na 52 u optyki)
i 52.9% waznosci modelu.

Miary jak poprzednio:
  F1        - trafienie w pojedyncza dzialke
  r splot   - trafienie w ZAGESZCZENIE po jadrze 3 km (miara wlasciwa dla mapy)
  r geo     - odniesienie "roslo tam, gdzie rok temu". Model musi je pobic,
              inaczej detekcja niczego nie wnosi. Dla upraw trwalych przegrana
              z tym odniesieniem jest wynikiem POPRAWNYM - one sie nie ruszaja.

Uruchomienie:
    python skrypty/detekcja/transfer_s1s2.py
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
from cechy_s1s2 import cechy, kolekcja_s1
from wielo_diagnoza import ODRZUC, SCAL
from wielo_transfer import (DRZEW, GRUPA, LAM_M, PROG_R, ZASIEG_M, ZIARNO,
                            naiwna_geografia, r_splot)

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
CACHE = {2025: WYNIKI / "cache" / "wielo_cechy_s1.csv",
         2026: WYNIKI / "cache" / "wielo_cechy_s1_2026.csv"}
PKT = {2025: WYNIKI / "cache" / "wielo_punkty.csv",
       2026: WYNIKI / "cache" / "wielo_punkty_2026.csv"}
S2 = {2025: WYNIKI / "cache" / "wielo_cechy.csv",
      2026: WYNIKI / "cache" / "wielo_cechy_2026.csv"}


def pobierz_s1(rok: int, df: pd.DataFrame, krok: int = 1200) -> pd.DataFrame:
    if CACHE[rok].exists():
        X = pd.read_csv(CACHE[rok]).set_index("i")
        print(f"  cechy S1 {rok} z cache: {X.shape}")
        return X
    K.AOI = ee.Geometry.Rectangle(
        [float(df.lon.min()) - .1, float(df.lat.min()) - .1,
         float(df.lon.max()) + .1, float(df.lat.max()) + .1],
        "EPSG:4326", False)
    print(f"  scen S1 {rok}: {kolekcja_s1(rok).size().getInfo()}")
    obraz, nazwy = cechy(rok, z_radarem=True)
    rad = [n for n in nazwy if n.startswith(("vv_", "vh_", "rat_"))]
    obraz = obraz.select(rad)
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
                time.sleep(20 * (prob + 1))
        czesci.append(pd.DataFrame([f["properties"] for f in d["features"]]))
        print(f"    S1 {rok}: {min(i + krok, len(df)):6,}/{len(df):,}")
    X = pd.concat(czesci, ignore_index=True).set_index("i").sort_index()
    X.to_csv(CACHE[rok], index_label="i")
    return X


def zbior(rok: int) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = pd.read_csv(PKT[rok])
    X2 = pd.read_csv(S2[rok]).set_index("i")
    X1 = pobierz_s1(rok, df)
    k2 = [c for c in X2.columns if c.startswith(("ndvi", "ndyi"))]
    k1 = [c for c in X1.columns if c.startswith(("vv_", "vh_", "rat_"))]
    d = df.reset_index(drop=True).join(X2[k2]).join(X1[k1])
    d = d[~d.etykieta.isin(ODRZUC)].copy()
    d["grupa"] = d.etykieta.replace(SCAL).replace(GRUPA)
    return d.dropna(subset=k2 + k1), k2, k1


if __name__ == "__main__":
    K.start()
    print("1/3  zbiory 2025 i 2026 (S2 z cache + S1)")
    d25, k2, k1 = zbior(2025)
    d26, _, _ = zbior(2026)
    print(f"  n25={len(d25):,}  n26={len(d26):,}")

    # okno musi byc kompletne w OBU latach; -99 = brak sceny radarowej
    def dobre(kol, brak):
        return [c for c in kol
                if (d25[c] <= brak if brak < 0 else d25[c] == brak).mean() <= .25
                and (d26[c] <= brak if brak < 0 else d26[c] == brak).mean() <= .25]
    k2o, k1o = dobre(k2, 0), dobre(k1, -98)
    print(f"\n2/3  okna wspolne: S2 {len(k2o)}/{len(k2)}, "
          f"S1 {len(k1o)}/{len(k1)}")

    print("\n3/3  ucz 2025 -> sprawdz 2026")
    wyniki = {}
    for nazwa, kol in (("S2", k2o), ("S1+S2", k2o + k1o)):
        las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                     random_state=ZIARNO).fit(d25[kol],
                                                              d25.grupa)
        pred = las.predict(d26[kol])
        xy25 = d25[["x", "y"]].to_numpy()
        xy26 = d26[["x", "y"]].to_numpy()
        geo = naiwna_geografia(xy25, d25.grupa.to_numpy(), xy26)
        w = {}
        for g in sorted(d26.grupa.unique()):
            w[g] = {
                "f1": f1_score((d26.grupa == g).astype(int),
                               (pred == g).astype(int)),
                "r_splot": r_splot(xy26, (d26.grupa == g).to_numpy(),
                                   (pred == g)),
                "r_geo": r_splot(xy26, (d26.grupa == g).to_numpy(), (geo == g)),
            }
        wyniki[nazwa] = w
        print(f"  {nazwa}: F1-makro "
              f"{f1_score(d26.grupa, pred, average='macro'):.3f}")

    print(f"\n{'gatunek':26s}{'r S2':>8}{'r S1+S2':>10}{'zysk':>8}"
          f"{'r geo':>8}  werdykt")
    ile = 0
    for g in sorted(wyniki["S2"]):
        a, b = wyniki["S2"][g]["r_splot"], wyniki["S1+S2"][g]["r_splot"]
        gg = wyniki["S1+S2"][g]["r_geo"]
        if b >= PROG_R and b > gg:
            wer, ile = "detekcja wnosi", ile + 1
        elif b >= PROG_R:
            wer = "dobre, ale pamiec lepsza"
        else:
            wer = "ponizej progu"
        print(f"{g[:24]:26s}{a:>8.3f}{b:>10.3f}{b-a:>+8.3f}{gg:>8.3f}  {wer}")
    print(f"\ngatunkow, gdzie detekcja bije pamiec i przechodzi prog: {ile}")

    (WYNIKI / "json" / "transfer_s1s2.json").write_text(json.dumps({
        "trening": 2025, "test": 2026,
        "n_cech": {"S2": len(k2o), "S1": len(k1o)},
        "jadro": {"lambda_m": LAM_M, "zasieg_m": ZASIEG_M},
        "wyniki": wyniki, "prog_r": PROG_R,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano transfer_s1s2.json")
