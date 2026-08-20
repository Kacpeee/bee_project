"""
ETAP 30 - WALIDACJA KRZYZOWA modelu fenologicznego rzepaku.

ZASTRZEZENIE, KTORE TO ZAMYKA
Projekt podawal dotad blad modelu 3.5 dnia (pelny sezon) i 4.4 dnia
(prognoza na 1 V). Obie liczby byly liczone NA TYCH SAMYCH 52 obserwacjach,
na ktorych dobrano baze termiczna (1.0 C) i prog GDD (555). Model byl wiec
sprawdzany na danych, ktore go stworzyly - to jest BLAD DOPASOWANIA, nie
blad prognozy, i jest z definicji optymistyczny.

Dodatkowo siedem obserwacji odrzucono jako odstajace i te same siedem
wykluczono z liczenia bledu, czyli najtrudniejsze przypadki wypadly z oceny.

CO ROBI TEN SKRYPT
Leave-one-out: dla kazdej obserwacji parametry (baza, prog) dobierane sa
na POZOSTALYCH, a blad liczony na odlozonej. Zaden punkt nie ocenia sam
siebie. Dodatkowo liczony jest blad na pelnym zbiorze, z odrzuconymi
wlacznie, zeby bylo widac, ile kosztuje czyszczenie danych.

CZEGO TO NIE NAPRAWIA
Wartosci odniesienia to daty odczytane z krzywych NDYI Sentinel-2, a nie
obserwacje polowe - model porownywany jest z inna estymacja satelitarna.
Niezalezna podkladke mamy tylko dla lipy i robinii (mapy fitofenologiczne
IMGW, 51 stacji): blad 2.8 dnia i -1 dzien.

Uruchomienie:
    python skrypty/fenologia/walidacja_krzyzowa.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(p) for p in (ROOT / "skrypty").iterdir() if p.is_dir()]

WYNIKI = ROOT / "wyniki"
BAZY = np.arange(0.0, 8.51, 0.5)
PROGI = np.arange(150, 901, 5)
D0 = 32                      # start akumulacji: 1 II


def kumulacje(dfm: pd.DataFrame, baza: float) -> dict:
    """Skumulowane GDD dla kazdego obszaru i roku przy danej bazie."""
    out = {}
    for n, g in dfm.groupby("obszar"):
        out[n] = {}
        for rok, s in g.groupby("rok"):
            s = s.sort_values("doy")
            gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2
                             - baza, 0)
            gdd[s["doy"].to_numpy() < D0] = 0
            out[n][int(rok)] = (s["doy"].to_numpy(), np.cumsum(gdd))
    return out


def przewidz(kum: dict, n: str, rok: int, prog: float):
    if n not in kum or rok not in kum[n]:
        return None
    doy, c = kum[n][rok]
    i = np.searchsorted(c, prog)
    return float(doy[i]) if i < len(doy) else None


def dopasuj(punkty, KUM) -> tuple[float, float]:
    """Baza i prog minimalizujace RMSE na podanych punktach."""
    naj = (np.inf, None, None)
    for baza in BAZY:
        kum = KUM[baza]
        for prog in PROGI:
            b = []
            for n, rok, praw in punkty:
                p = przewidz(kum, n, rok, prog)
                if p is not None:
                    b.append((p - praw) ** 2)
            if b:
                r = (sum(b) / len(b)) ** 0.5
                if r < naj[0]:
                    naj = (r, baza, prog)
    return naj[1], naj[2]


if __name__ == "__main__":
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json")
                     .read_text(encoding="utf-8"))
    kal = json.loads((WYNIKI / "json" / "fenologia_kalibracja.json")
                     .read_text(encoding="utf-8"))
    odrz = {(o["obszar"], o["rok"]) for o in kal["odrzucone"]}
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv",
                      parse_dates=["data"])

    wszystkie = [(n, int(r), v)
                 for n, s in fin["obserwacje"].items() for r, v in s.items()]
    czyste = [p for p in wszystkie if (p[0], p[1]) not in odrz]
    print(f"obserwacji razem: {len(wszystkie)}, "
          f"po odrzuceniu odstajacych: {len(czyste)}")

    print("\nliczenie kumulacji GDD dla siatki baz...", flush=True)
    KUM = {b: kumulacje(dfm, b) for b in BAZY}

    for etyk, zbior in (("CZYSTE (jak dotad)", czyste),
                        ("PELNE (z odrzuconymi)", wszystkie)):
        print(f"\n{'=' * 58}\n{etyk}  n={len(zbior)}\n{'=' * 58}")

        # --- dopasowanie na calosci: to jest liczba podawana dotad
        b0, p0 = dopasuj(zbior, KUM)
        bl_in = []
        for n, rok, praw in zbior:
            p = przewidz(KUM[b0], n, rok, p0)
            if p is not None:
                bl_in.append(p - praw)
        rin = float(np.sqrt(np.mean(np.square(bl_in))))
        print(f"  dopasowanie in-sample: baza {b0:.1f} C, prog {p0:.0f}, "
              f"RMSE {rin:.2f} d   <- liczba podawana dotad")

        # --- leave-one-out: kazdy punkt oceniany parametrami z pozostalych
        bl_cv, params = [], []
        for i, (n, rok, praw) in enumerate(zbior):
            reszta = zbior[:i] + zbior[i + 1:]
            b, pr = dopasuj(reszta, KUM)
            params.append((b, pr))
            p = przewidz(KUM[b], n, rok, pr)
            if p is not None:
                bl_cv.append(p - praw)
        bl_cv = np.array(bl_cv, float)
        rcv = float(np.sqrt(np.mean(bl_cv ** 2)))
        print(f"  leave-one-out:         RMSE {rcv:.2f} d, "
              f"blad sredni {bl_cv.mean():+.2f} d, "
              f"bezwzgledny {np.abs(bl_cv).mean():.2f} d")
        print(f"  optymizm dopasowania:  {rcv - rin:+.2f} d "
              f"({(rcv / rin - 1) * 100:+.0f}%)")
        bs = sorted({b for b, _ in params})
        ps = sorted({p for _, p in params})
        print(f"  stabilnosc parametrow: baza {bs[0]:.1f}-{bs[-1]:.1f} C, "
              f"prog {ps[0]:.0f}-{ps[-1]:.0f}")
        print(f"  najgorszy przypadek:   {np.abs(bl_cv).max():.1f} d")

        if etyk.startswith("CZYSTE"):
            wynik_czyste = {"n": len(zbior), "rmse_in_sample": rin,
                            "rmse_loo": rcv, "baza": float(b0),
                            "prog": float(p0),
                            "blad_sredni": float(bl_cv.mean()),
                            "najgorszy_d": float(np.abs(bl_cv).max())}
        else:
            wynik_pelne = {"n": len(zbior), "rmse_in_sample": rin,
                           "rmse_loo": rcv,
                           "najgorszy_d": float(np.abs(bl_cv).max())}

    print("\nJAK TO RAPORTOWAC")
    print("  Podawac RMSE z walidacji krzyzowej, nie z dopasowania.")
    print("  Przy dwoch dopasowywanych parametrach i kilkudziesieciu")
    print("  obserwacjach roznica bywa niewielka - ale musi byc ZMIERZONA.")

    (WYNIKI / "json" / "walidacja_krzyzowa.json").write_text(json.dumps({
        "metoda": "leave-one-out: dla kazdej obserwacji baza i prog dobierane "
                  "na pozostalych, blad liczony na odlozonej",
        "zastrzezenie": "wartosci odniesienia to daty z krzywych NDYI "
                        "Sentinel-2, nie obserwacje polowe; niezalezna "
                        "walidacja polowa istnieje tylko dla lipy (2.8 d) "
                        "i robinii (-1 d) wobec map IMGW",
        "czyste": wynik_czyste,
        "pelne_z_odrzuconymi": wynik_pelne,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/walidacja_krzyzowa.json")
