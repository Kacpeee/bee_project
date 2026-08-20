"""
Skladanie ostatecznej wersji modelu fenologicznego dla raportu.

Laczy trzy rzeczy policzone osobno:
  - obserwacje z 7 obszarow (fenologia_wielo.json)
  - parametry dopasowane na siatce baza x prog (fenologia_kalibracja.json)
  - przewidywania przeliczone tymi parametrami dla kazdego obszaru i roku

Wczesniejsza wersja raportu podawala RMSE 3.6 dnia z JEDNEGO obszaru. Ta liczba
byla optymistyczna - obszar pilotazowy okazal sie najlepszym z siedmiu. Tu
wchodzi obraz pelny, wraz z informacja, ktore obserwacje odrzucono i dlaczego.

Uruchomienie:
    python fenologia_final.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
OBSZAR_GLOWNY = "Hrubieszow"


def przewiduj(g: pd.DataFrame, baza: float, d0: int, prog: float) -> dict[int, int]:
    out = {}
    for rok, s in g.groupby("rok"):
        s = s.sort_values("doy")
        gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - baza, 0)
        gdd[s["doy"].to_numpy() < d0] = 0
        c = np.cumsum(gdd)
        i = np.searchsorted(c, prog)
        if i < len(s):
            out[int(rok)] = int(s["doy"].to_numpy()[i])
    return out


if __name__ == "__main__":
    w = json.loads((WYNIKI / "json" / "fenologia_wielo.json").read_text(encoding="utf-8"))
    k = json.loads((WYNIKI / "json" / "fenologia_kalibracja.json").read_text(encoding="utf-8"))
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])

    naj = k["najlepsze"]["czyste"]
    baza, prog = naj["baza"], naj["prog"]
    d0 = {"1I": 1, "1II": 32}[naj["start"]]
    odrz = {(o["obszar"], o["rok"]) for o in k["odrzucone"]}

    obs = {n: {int(r): v for r, v in s.items()} for n, s in w["obserwacje"].items()}
    pred = {n: przewiduj(dfm[dfm["obszar"] == n], baza, d0, prog) for n in obs}

    # statystyki per obszar, tylko na obserwacjach niewykluczonych
    per = {}
    for n, s in obs.items():
        b = [(pred[n][r] - v) for r, v in s.items()
             if r in pred[n] and (n, r) not in odrz]
        if b:
            per[n] = {"lat": w["obszary"][n]["lat"], "n": len(b),
                      "rmse": float(np.sqrt(np.mean(np.square(b)))),
                      "bias": float(np.mean(b))}

    print(f"MODEL: baza {baza} °C, akumulacja od {naj['start']}, prog {prog} GDD\n")
    print(f"{'obszar':>12}{'lat':>7}{'n':>4}{'RMSE':>7}{'obciazenie':>12}")
    for n in sorted(per, key=lambda x: per[x]["lat"]):
        v = per[n]
        print(f"{n:>12}{v['lat']:>7.2f}{v['n']:>4}{v['rmse']:>7.1f}{v['bias']:>+11.1f} d")

    wsz = [(pred[n][r] - v) for n, s in obs.items() for r, v in s.items()
           if r in pred[n] and (n, r) not in odrz]
    print(f"\n{'RAZEM':>12}{'':>7}{len(wsz):>4}"
          f"{np.sqrt(np.mean(np.square(wsz))):>7.1f}{np.mean(wsz):>+11.1f} d")

    (WYNIKI / "json" / "fenologia_final.json").write_text(json.dumps({
        "model": {"baza": baza, "prog": prog, "start": naj["start"],
                  "rmse": float(np.sqrt(np.mean(np.square(wsz)))),
                  "n": len(wsz), "n_odrzuconych": len(odrz)},
        "dolina": {"baza_min": min(x["baza"] for x in k["dolina_rozwiazan"]),
                   "baza_max": max(x["baza"] for x in k["dolina_rozwiazan"]),
                   "prog_min": min(x["prog"] for x in k["dolina_rozwiazan"]),
                   "prog_max": max(x["prog"] for x in k["dolina_rozwiazan"])},
        "odniesienie_stala": k["odniesienie_stala"],
        "rmse_bez_odrzucania": k["najlepsze"]["wszystkie"]["rmse"],
        "per_obszar": per,
        "obserwacje": {n: {str(r): v for r, v in s.items()} for n, s in obs.items()},
        "przewidywania": {n: {str(r): v for r, v in s.items()}
                          for n, s in pred.items()},
        "odrzucone": k["odrzucone"],
        "glowny": OBSZAR_GLOWNY,
        "transfer": {"rmse_prog_wspolny": w["model_wspolny"]["rmse"],
                     "rmse_progi_lokalne": w["rmse_lokalne"]},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'fenologia_final.json'}")
