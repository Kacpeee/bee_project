"""
Kalibracja modelu fenologicznego na wszystkich obszarach naraz.

CO SIE ZMIENIA WZGLEDEM POPRZEDNIEJ WERSJI

1. BAZA JEST DOPASOWYWANA, NIE ZAKLADANA.
   Dotad baza 4 °C byla wybrana tak, zeby pasowala do JEDNEGO zmierzonego
   kwitnienia. Przy 59 obserwacjach mozna dopasowac baze i prog jednoczesnie,
   przeszukujac siatke dwuwymiarowa.

2. OBSERWACJE PODEJRZANE SA ODRZUCANE.
   Obszary oddalone o 23 km roznily sie w niektorych latach o 12, a nawet
   o 26 dni - to jest biologicznie niemozliwe i oznacza awarie pomiaru
   (luka w zdjeciach, slaby sygnal, zle dopasowana parabola). Odrzucamy
   obserwacje odstajace od mediany danego roku o wiecej niz PROG_ODRZUTU dni.

DEKOMPOZYCJA BLEDU, dla przypomnienia po co to wszystko:
  calkowity RMSE 7.0 d = szum pomiaru ~2.9 d + blad modelu ~6.4 d
Model jest waskim gardlem, nie pomiar - dlatego pracujemy nad modelem.

Uruchomienie:
    python fenologia_kalibracja.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import meteo_gdd as MG

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
CACHE = WYNIKI / "cache" / "meteo_obszary.csv"

PROG_ODRZUTU = 8          # dni odchylenia od mediany roku
BAZY = np.arange(0.0, 8.51, 0.5)
PROGI = np.arange(150, 901, 5)
STARTY = {"1I": 1, "1II": 32}


def d(doy: float, rok: int = 2022) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day:02d}.{x.month:02d}"


def meteo_obszarow(obszary: dict) -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_csv(CACHE, parse_dates=["data"])
    czesci = []
    for n, v in obszary.items():
        print(f"  meteo: {n}")
        df = MG.pobierz(v["lat"], v["lon"], date(2017, 1, 1),
                        date.today() - timedelta(days=6))
        czesci.append(df.assign(obszar=n))
    df = pd.concat(czesci, ignore_index=True)
    df.to_csv(CACHE, index=False)
    return df


def terminy(g: pd.DataFrame, baza: float, d0: int) -> dict[int, np.ndarray]:
    """Dla kazdego roku: skumulowane GDD po dniach, od dnia d0."""
    out = {}
    for rok, s in g.groupby("rok"):
        s = s.sort_values("doy")
        gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - baza, 0)
        gdd[s["doy"].to_numpy() < d0] = 0
        out[rok] = (s["doy"].to_numpy(), np.cumsum(gdd))
    return out


def rmse_dla(obs: dict, kum: dict, prog: float) -> tuple[float, int]:
    bledy = []
    for n, s in obs.items():
        for rok, praw in s.items():
            if rok not in kum[n]:
                continue
            doy, c = kum[n][rok]
            i = np.searchsorted(c, prog)
            if i >= len(doy):
                continue
            bledy.append((doy[i] - praw) ** 2)
    return ((sum(bledy) / len(bledy)) ** 0.5 if bledy else np.inf), len(bledy)


if __name__ == "__main__":
    w = json.loads((WYNIKI / "json" / "fenologia_wielo.json").read_text(encoding="utf-8"))
    obs = {n: {int(r): v for r, v in s.items()} for n, s in w["obserwacje"].items()}

    # --- odrzucenie obserwacji odstajacych od mediany roku
    lata = sorted({r for s in obs.values() for r in s})
    odrzucone = []
    for rok in lata:
        maja = {n: s[rok] for n, s in obs.items() if rok in s}
        if len(maja) < 3:
            continue
        med = np.median(list(maja.values()))
        for n, v in maja.items():
            if abs(v - med) > PROG_ODRZUTU:
                odrzucone.append((n, rok, v, med))
    print(f"ODRZUCONE OBSERWACJE (odchylenie > {PROG_ODRZUTU} dni od mediany roku)")
    for n, rok, v, med in odrzucone:
        print(f"  {n:12s} {rok}  {d(v, rok)}  mediana roku {d(med, rok)}  "
              f"({v - med:+.0f} d)")
    czyste = {n: {r: v for r, v in s.items()
                  if (n, r, v, np.median([obs[m][r] for m in obs if r in obs[m]]))
                  not in odrzucone}
              for n, s in obs.items()}
    n_przed = sum(len(s) for s in obs.values())
    n_po = sum(len(s) for s in czyste.values())
    print(f"\n  {n_przed} -> {n_po} obserwacji\n")

    print("Meteo dla obszarow...")
    dfm = meteo_obszarow(w["obszary"])

    # --- siatka baza x prog x start
    print("\nDOPASOWANIE BAZY I PROGU JEDNOCZESNIE")
    print(f"{'zbior':>10}{'start':>7}{'baza':>7}{'prog':>7}{'RMSE':>8}{'n':>6}")
    najlepsze = {}
    for etyk, zbior in (("wszystkie", obs), ("czyste", czyste)):
        naj = None
        for sn, d0 in STARTY.items():
            kum = {n: terminy(dfm[dfm["obszar"] == n], 0, d0) for n in zbior}
            for baza in BAZY:
                kum = {n: terminy(dfm[dfm["obszar"] == n], baza, d0) for n in zbior}
                for prog in PROGI:
                    r, k = rmse_dla(zbior, kum, prog)
                    if naj is None or r < naj[0]:
                        naj = (r, baza, prog, sn, k)
        najlepsze[etyk] = naj
        r, baza, prog, sn, k = naj
        print(f"{etyk:>10}{sn:>7}{baza:>7.1f}{prog:>7.0f}{r:>8.1f}{k:>6}")

    # --- porownanie z wersja wyjsciowa
    stary = w["model_wspolny"]
    print(f"\nPOROWNANIE")
    print(f"  poprzednio (baza 4.0 zalozona, prog {stary['prog']}): "
          f"RMSE {stary['rmse']:.1f} d")
    r, baza, prog, sn, k = najlepsze["czyste"]
    print(f"  teraz (baza {baza:.1f} dopasowana, prog {prog:.0f}, "
          f"obserwacje czyste): RMSE {r:.1f} d")

    # odniesienia na tym samym zbiorze
    wszyst = [v for s in czyste.values() for v in s.values()]
    sr = float(np.mean(wszyst))
    stala = ((sum((v - sr) ** 2 for s in czyste.values() for v in s.values())
              / len(wszyst)) ** 0.5)
    print(f"  odniesienie 'zawsze srednia ({d(sr)})': RMSE {stala:.1f} d")

    # Czy dopasowanie jest jednoznaczne? W modelach GDD baza i prog sa
    # wymienne - niska baza z wysokim progiem daje prawie to samo co wysoka
    # baza z niskim. Sprawdzamy, jak szeroka jest dolina rozwiazan.
    r_opt, b_opt, p_opt, s_opt, _ = najlepsze["czyste"]
    d0 = STARTY[s_opt]
    bliskie = []
    for baza in BAZY:
        kum = {n: terminy(dfm[dfm["obszar"] == n], baza, d0) for n in czyste}
        for prog in PROGI:
            r, k = rmse_dla(czyste, kum, prog)
            if r <= r_opt + 0.2:
                bliskie.append((float(baza), int(prog), float(r)))
    print("\nJEDNOZNACZNOSC DOPASOWANIA")
    print(f"  rozwiazan w promieniu 0.2 dnia od optimum: {len(bliskie)}")
    if bliskie:
        bz = [x[0] for x in bliskie]; pz = [x[1] for x in bliskie]
        print(f"  baza:  {min(bz):.1f} - {max(bz):.1f} °C")
        print(f"  prog:  {min(pz)} - {max(pz)} GDD")
        print("  -> baza i prog sa wymienne; para ma sens, pojedyncza liczba nie")

    (WYNIKI / "json" / "fenologia_kalibracja.json").write_text(json.dumps({
        "prog_odrzutu_dni": PROG_ODRZUTU,
        "odrzucone": [{"obszar": n, "rok": int(r), "doy": float(v),
                       "mediana": float(med)} for n, r, v, med in odrzucone],
        "n_przed": n_przed, "n_po": n_po,
        "najlepsze": {k2: {"rmse": float(v[0]), "baza": float(v[1]),
                           "prog": int(v[2]), "start": v[3], "n": int(v[4])}
                      for k2, v in najlepsze.items()},
        "odniesienie_stala": float(stala),
        "dolina_rozwiazan": [{"baza": b, "prog": p, "rmse": r}
                             for b, p, r in bliskie],
    }, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"\nZapisano {WYNIKI / 'fenologia_kalibracja.json'}")
