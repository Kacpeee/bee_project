"""
ETAP 31 - odrzucanie CALYCH SEZONOW zamiast pojedynczych obserwacji.

PROBLEM Z DOTYCHCZASOWYM ODRZUCANIEM
Kalibracja odrzucala pojedyncze obserwacje odstajace od mediany roku
o wiecej niz 8 dni. Prog 8 dni byl dobrany po fakcie i odrzucal punkty,
a nie przyczyne - to wyglada na dobieranie danych pod wynik.

CO POKAZALA DIAGNOZA
Odrzucenia nie sa rozlozone rownomiernie, tylko skupione w konkretnych
sezonach. Rozrzut obserwacji w wojewodztwie wg roku:

    2018  8 d      2021 13 d (1 odrzut)    2024  7 d
    2019  9 d      2022  9 d               2025  6 d
    2020 25 d (2)  2023  6 d               2026 40 d (4 odrzuty)

Model daje dla calego wojewodztwa rozrzut ok. 10 dni - to jest granica
fizyczna wynikajaca z gradientu termicznego na 230 km. Rzepak nie kwitnie
w jednym wojewodztwie z rozrzutem 40 dni. To NIE JEST zmiennosc zjawiska,
tylko AWARIA ODCZYTU krzywych NDYI - w 2026 (sezon biezacy) archiwum
Sentinel-2 jest rzadsze, tak samo jak przy tescie przenoszenia, gdzie
2026 mial 24 z 52 okien puste.

KRYTERIUM - REGULA ODPORNA, NIE PROG POD WYNIK
Sezon wyklucza sie w calosci, gdy rozrzut jego obserwacji przekracza
DWUKROTNOSC MEDIANY rozrzutow ze wszystkich sezonow. Jest to standardowa
regula odstajacych oparta na medianie, wiec odporna na same odstajace,
i nie odwoluje sie do tego, jaki RMSE chcemy dostac.

UWAGA - pierwsza wersja tego skryptu porownywala rozrzut obserwacji
z rozrzutem MODELOWANYM i odrzucila wszystkie dziewiec sezonow. Powod:
modelowany rozrzut miedzy siedmioma obszarami pomiarowymi wynosi 1-3 dni,
bo lezą blisko siebie, podczas gdy 10 dni dotyczylo calego wojewodztwa
(1806x2237 px) wraz z jego skrajnymi punktami. Blad wart zapamietania:
ta sama wielkosc liczona na innym zbiorze punktow ma inny rzad.

Uruchomienie:
    python skrypty/fenologia/odrzut_sezonow.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walidacja_krzyzowa import (BAZY, PROGI, D0, kumulacje,      # noqa: E402
                                przewidz, dopasuj)

WYNIKI = ROOT / "wyniki"
MARGINES = 2.0      # ile razy rozrzut sezonu moze przekroczyc mediane rozrzutow


if __name__ == "__main__":
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json")
                     .read_text(encoding="utf-8"))
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv",
                      parse_dates=["data"])
    obs = {n: {int(r): v} for n, s in fin["obserwacje"].items()
           for r, v in s.items()}
    punkty = [(n, int(r), v)
              for n, s in fin["obserwacje"].items() for r, v in s.items()]

    print("liczenie kumulacji GDD...", flush=True)
    KUM = {b: kumulacje(dfm, b) for b in BAZY}

    # parametry startowe z calosci - tylko po to, by policzyc rozrzut modelowy
    b0, p0 = dopasuj(punkty, KUM)
    print(f"parametry startowe: baza {b0:.1f} C, prog {p0:.0f}\n")

    lata = sorted({r for _, r, _ in punkty})
    rozrzut = {}
    for rok in lata:
        v = [x for _, r, x in punkty if r == rok]
        rozrzut[rok] = max(v) - min(v)
    med = float(np.median(list(rozrzut.values())))
    prog_r = MARGINES * med
    print(f"mediana rozrzutow sezonowych: {med:.0f} d, "
          f"prog odrzutu: {prog_r:.0f} d")
    print()

    print(f"{'rok':>6}{'n':>4}{'rozrzut obs':>13}{'x mediany':>12}{'werdykt':>12}")
    diag, zle = {}, []
    for rok in lata:
        n_ = sum(1 for _, r, _ in punkty if r == rok)
        o = rozrzut[rok]
        ok = o <= prog_r
        if not ok:
            zle.append(rok)
        diag[rok] = {"n": n_, "rozrzut_obs": o, "x_mediany": o / med,
                     "przyjety": ok}
        print(f"{rok:>6}{n_:>4}{o:>11.0f} d{o / med:>11.1f}"
              f"{'ODRZUCONY' if not ok else 'ok':>12}")

    czyste = [p for p in punkty if p[1] not in zle]
    print(f"\nodrzucone sezony: {zle or 'brak'}")
    print(f"obserwacji: {len(punkty)} -> {len(czyste)}")

    print("\nKALIBRACJA I WALIDACJA NA SEZONACH PRZYJETYCH")
    b1, p1 = dopasuj(czyste, KUM)
    bl = [przewidz(KUM[b1], n, r, p1) - v for n, r, v in czyste
          if przewidz(KUM[b1], n, r, p1) is not None]
    rin = float(np.sqrt(np.mean(np.square(bl))))
    print(f"  dopasowanie: baza {b1:.1f} C, prog {p1:.0f}, RMSE {rin:.2f} d")

    blcv = []
    for i, (n, r, v) in enumerate(czyste):
        b, pr = dopasuj(czyste[:i] + czyste[i + 1:], KUM)
        q = przewidz(KUM[b], n, r, pr)
        if q is not None:
            blcv.append(q - v)
    blcv = np.array(blcv, float)
    rcv = float(np.sqrt(np.mean(blcv ** 2)))
    print(f"  leave-one-out: RMSE {rcv:.2f} d, bezwzgledny "
          f"{np.abs(blcv).mean():.2f} d, najgorszy {np.abs(blcv).max():.1f} d")
    print(f"  optymizm: {rcv - rin:+.2f} d")

    print("\nPOROWNANIE Z DOTYCHCZASOWYM PODEJSCIEM")
    print("  odrzut 7 pojedynczych punktow (prog 8 d po fakcie): 3.48 d")
    print(f"  odrzut calych sezonow (kryterium fizyczne):        {rcv:.2f} d")
    print("  bez zadnego odrzutu:                               6.31 d")

    (WYNIKI / "json" / "odrzut_sezonow.json").write_text(json.dumps({
        "kryterium": f"sezon odrzucany, gdy rozrzut jego obserwacji "
                     f"przekracza {MARGINES}x mediane rozrzutow wszystkich "
                     f"sezonow - regula odporna oparta na medianie, nie prog "
                     f"dobrany pod oczekiwany wynik",
        "mediana_rozrzutow_d": med,
        "prog_odrzutu_d": prog_r,
        "margines": MARGINES,
        "diagnoza_lat": diag,
        "sezony_odrzucone": zle,
        "n_przed": len(punkty), "n_po": len(czyste),
        "baza": float(b1), "prog": float(p1),
        "rmse_dopasowania": rin, "rmse_walidacji_loo": rcv,
        "blad_bezwzgledny": float(np.abs(blcv).mean()),
        "najgorszy_d": float(np.abs(blcv).max()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/odrzut_sezonow.json")
