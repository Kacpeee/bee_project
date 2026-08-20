"""
ETAP 3b - fenologia w SIEDMIU obszarach zamiast jednego.

DLACZEGO PRZESTRZEN, A NIE DLUZSZY SZEREG
Probowalismy wydluzyc zapis wstecz i sie nie da:
  - MODIS ma codzienne przeloty, ale piksel 500 m to 25 ha, a mediana dzialki
    rzepakowej tutaj to 1.16 ha. Kwitnienie zmienia sygnal piksela o kilka
    procent i ginie w mieszaninie - sprawdzone, zadna metoda odjecia trendu
    nie odtworzyla dat z Sentinela.
  - Landsat ma 30 m, ale przelot co 16 dni. W czterech sezonach na dziewiec
    nie ma ani jednego zdjecia w promieniu +/-5 dni od pelni kwitnienia;
    dziury 20-30 dni wypadaja dokladnie w oknie kwitnienia.
Sentinel-2 jest jedynym sensorem majacym naraz rozdzielczosc i czestotliwosc,
stad zapis zaczyna sie w 2018 i to jest granica fizyczna, nie organizacyjna.

Zamiast tego replikacja przestrzenna: 7 obszarow x 9 sezonow. Daje to nie tylko
wiecej obserwacji, ale odpowiedz na pytanie, ktorego jeden obszar nie stawia -
CZY JEDEN PROG CIEPLNY DZIALA W CALYM REGIONIE, czy trzeba go roznicowac.
To jest test przenoszalnosci modelu, a nie tylko jego dopasowania.

Uruchomienie:
    python fenologia_wielo.py
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

import fenologia_gsa as F
import gee_klasyfikator_rzepaku as K
import klasyfikator_gsa as G
import meteo_gdd as MG
from gee_klasyfikator_rzepaku import LICZBA_DRZEW, cechy, orne_maska
from gee_ndyi_przeglad import start

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

# obszary z >2000 ha rzepaku, rozrzucone po szerokosci i dlugosci
OBSZARY = {
    "Zamosc":      (50.640, 23.250),
    "Hrubieszow":  (50.755, 23.600),
    "Krasnik":     (50.920, 22.220),
    "Bychawa":     (51.000, 22.530),
    "Chelm":       (51.180, 23.450),
    "Naleczow":    (51.280, 22.150),
    "Radzyn":      (51.780, 22.620),

    # ROZSZERZENIE PROBY (etap 38). Siedem obszarow dawalo 59 obserwacji,
    # z czego 45 po odrzucie sezonow - za malo, zeby wylapac rzadkie lata
    # (najgorszy przypadek siegal 9-12 dni). Ponizsze wyznaczono z GESTOSCI
    # RZEPAKU w deklaracjach GSA 2025: komorki 15 km o powierzchni rzepaku
    # powyzej 1500 ha, wybierane zachlannie z odstepem 20 km od juz zajetych.
    # Kryterium jest wiec danymi, nie wyborem na oko.
    "Turobin":     (50.840, 22.872),   # 3 286 ha rzepaku
    "Tomaszow":    (50.531, 23.906),   # 3 230
    "Piaski":      (51.109, 22.894),   # 2 948
    "Izbica":      (50.825, 23.297),   # 2 652
    "Krasnystaw":  (50.952, 23.522),   # 2 424
    "Wlodawa":     (51.640, 23.157),   # 2 091
    "Leczna":      (51.251, 22.691),   # 2 089
    "Parczew":     (51.782, 22.952),   # 2 051
    "Hrubieszow2": (50.800, 23.934),   # 1 955
    "Zamosc2":     (50.967, 23.096),   # 1 913
    "Bilgoraj":    (50.405, 23.681),   # 1 769
    "Zakrzowek":   (50.712, 22.649),   # 1 669
}
LATA = range(2018, 2027)
PROMIEN_M = 15_000


def d(doy: float, rok: int = 2022) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day:02d}.{x.month:02d}"


# ---------------------------------------------------------------- jeden obszar
def daty_kwitnienia(nazwa: str, lat: float, lon: float) -> dict[int, float]:
    aoi = ee.Geometry.Point([lon, lat]).buffer(PROMIEN_M).bounds()
    K.AOI = aoi

    df = G.punkty(lat, lon, PROMIEN_M, cicho=True)
    x25 = cechy(G.ROK).updateMask(orne_maska())
    proba = x25.sampleRegions(collection=G.kolekcja(df), scale=10,
                              geometries=False, tileScale=4)
    las = ee.Classifier.smileRandomForest(LICZBA_DRZEW).train(
        features=proba.filter(ee.Filter.eq("test", 0)),
        classProperty="rzepak", inputProperties=F.CECHY_PRZED)

    obs = {}
    for rok in LATA:
        try:
            maska = cechy(rok).updateMask(orne_maska()).classify(las).selfMask()
            w = F.krzywa(rok, maska, aoi)
        except Exception as e:
            print(f"    {rok}: blad {type(e).__name__}")
            continue
        if len(w) < F.MIN_DAT:
            print(f"    {rok}: {len(w)} dat - pomijam")
            continue
        obs[rok] = F.szczyt(w)[0]
    return obs


# ---------------------------------------------------------------- kalibracja
def rmse(a: dict, b: dict) -> float:
    w = sorted(set(a) & set(b))
    return (sum((a[r] - b[r]) ** 2 for r in w) / len(w)) ** 0.5 if w else float("nan")


def prognoza(meteo: pd.DataFrame, prog: float, start_w: str) -> dict[int, int]:
    t = MG.termin(MG.akumuluj(meteo, start_w), prog).dropna(subset=["doy"])
    return {int(r.rok): int(r.doy) for r in t.itertuples()}


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    start()
    print(f"{len(OBSZARY)} obszarow x {len(LATA)} sezonow, baza GDD {MG.BAZA} °C\n")

    # Zapis PRZYROSTOWY po kazdym obszarze. Wczesniej wynik szedl na dysk
    # dopiero na koncu, wiec przerwanie po godzinie liczenia kasowalo wszystko.
    czesciowy = WYNIKI / "json" / "fenologia_wielo_czesciowe.json"
    obs, meteo = {}, {}
    if czesciowy.exists():
        z = json.loads(czesciowy.read_text(encoding="utf-8"))
        obs = {n: {int(r): v for r, v in s.items()} for n, s in z.items()}
        print(f"wznawiam: gotowe juz {len(obs)} obszarow "
              f"({', '.join(obs)})\n")

    for nazwa, (lat, lon) in OBSZARY.items():
        if nazwa not in obs:
            print(f"{nazwa} ({lat}, {lon}):", flush=True)
            obs[nazwa] = daty_kwitnienia(nazwa, lat, lon)
            czesciowy.write_text(json.dumps(
                {n: {str(r): v for r, v in s.items()} for n, s in obs.items()},
                ensure_ascii=False, indent=1), encoding="utf-8")
        meteo[nazwa] = MG.pobierz(lat, lon, date(2017, 1, 1),
                                  date.today() - timedelta(days=6))
        s = obs[nazwa]
        print(f"  {len(s)} sezonow: " +
              " ".join(f"{r}:{d(v, r)}" for r, v in sorted(s.items())), flush=True)

    wszystkie = [(n, r, v) for n, s in obs.items() for r, v in s.items()]
    print(f"\nRAZEM {len(wszystkie)} obserwacji "
          f"({len(obs)} obszarow, {len({r for _, r, _ in wszystkie})} sezonow)")

    # --- prog wspolny dla calego regionu
    print("\nKALIBRACJA")
    naj = None
    for wariant in ("1I", "1II", "weg"):
        wyniki = []
        for prog in range(200, 601, 5):
            bledy = []
            for n, s in obs.items():
                p = prognoza(meteo[n], prog, wariant)
                bledy += [(p[r] - s[r]) ** 2 for r in s if r in p]
            wyniki.append(((sum(bledy) / len(bledy)) ** 0.5, prog))
        b, pr = min(wyniki)
        print(f"  wspolny prog, start {wariant:4s}: {pr:3d} GDD -> RMSE {b:.1f} dnia")
        if naj is None or b < naj[0]:
            naj = (b, pr, wariant)
    blad_w, prog_w, wariant = naj

    # --- prog osobny dla kazdego obszaru
    print(f"\n  progi lokalne (start {wariant}):")
    lok, bledy_lok = {}, []
    for n, s in obs.items():
        wyniki = [(rmse(s, prognoza(meteo[n], p, wariant)), p)
                  for p in range(200, 601, 5)]
        b, p = min(wyniki)
        lok[n] = {"prog": p, "rmse": b, "lat": OBSZARY[n][0], "n": len(s)}
        pr_ = prognoza(meteo[n], p, wariant)
        bledy_lok += [(pr_[r] - s[r]) ** 2 for r in s if r in pr_]
        print(f"    {n:12s} lat {OBSZARY[n][0]:.2f}  prog {p:3d}  "
              f"RMSE {b:4.1f} d  (n={len(s)})")
    blad_l = (sum(bledy_lok) / len(bledy_lok)) ** 0.5

    print(f"\n  RMSE prog wspolny: {blad_w:.1f} dnia")
    print(f"  RMSE progi lokalne: {blad_l:.1f} dnia   "
          f"(zysk {blad_w - blad_l:+.1f} d, {7 - 1} dodatkowych parametrow)")

    # czy prog zalezy od szerokosci geograficznej
    la = np.array([v["lat"] for v in lok.values()])
    pg = np.array([v["prog"] for v in lok.values()])
    if la.std() > 0 and pg.std() > 0:
        r = np.corrcoef(la, pg)[0, 1]
        print(f"  korelacja progu z szerokoscia geograficzna: r = {r:+.2f}")

    WYNIKI.mkdir(exist_ok=True)
    (WYNIKI / "json" / "fenologia_wielo.json").write_text(json.dumps({
        "obszary": {n: {"lat": v[0], "lon": v[1]} for n, v in OBSZARY.items()},
        "obserwacje": {n: {str(r): v for r, v in s.items()} for n, s in obs.items()},
        "n_obserwacji": len(wszystkie),
        "model_wspolny": {"baza": MG.BAZA, "start": wariant, "prog": prog_w,
                          "rmse": blad_w},
        "progi_lokalne": lok, "rmse_lokalne": blad_l,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'fenologia_wielo.json'}")
