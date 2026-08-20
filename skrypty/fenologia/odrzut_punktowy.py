"""
ETAP 40 - odrzucanie ODSTAJACYCH OBSERWACJI na rozszerzonej probie.

DLACZEGO WRACAMY DO ODRZUTU PUNKTOWEGO
Przy 7 obszarach awarie odczytu skupialy sie w calych sezonach (2020, 2026),
wiec regula "odrzuc sezon, gdy rozrzut przekracza dwukrotnosc mediany"
dzialala. Po rozszerzeniu do 19 obszarow i 162 obserwacji obraz sie zmienil:
awarie sa ROZPROSZONE - w kazdym sezonie kilka pojedynczych odczytow lezy
skrajnie daleko, a reszta jest dobra.

Regula sezonowa przestala wtedy cokolwiek odrzucac, bo mediana rozrzutow
sama urosla (z 9 na 30 dni) i prog razem z nia. Miara wzgledna zawodzi,
gdy psuje sie caly rozklad.

DLACZEGO TO NIE JEST POWROT DO DOBIERANIA DANYCH
Pierwotny odrzut punktowy uzywal progu 8 dni wybranego po zobaczeniu
wynikow. Tutaj prog wyprowadzamy z FIZYKI, przed spojrzeniem na bledy:

  - rozrzut MODELOWANY miedzy 19 obszarami: mediana 2 dni, maksimum 5 dni
    (obszary leza blizej siebie niz krance wojewodztwa)
  - odchylenie od mediany sezonu moze wiec siegac ok. 2.5 dnia z termiki
  - niepewnosc odczytu NDYI (wierzcholek paraboli): ok. 3 dni
  - prog fizyczny: ok. 6 dni

Zamiast bronic jednej liczby, liczymy wynik dla calego zakresu progow
i pokazujemy, jak od niego zalezy. Czytelnik widzi wtedy koszt decyzji,
a nie tylko jej efekt.

Uruchomienie:
    python skrypty/fenologia/odrzut_punktowy.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walidacja_krzyzowa import BAZY, PROGI
from start_akumulacji import kum, rmse

WYNIKI = ROOT / "wyniki"
D0 = 74
PROGI_ODRZUTU = [6, 8, 10, 12, 15, 20, 999]


def dopasuj(pkt, KUM):
    naj = (np.inf, None, None)
    for b in BAZY:
        K = KUM[b]
        for p in PROGI:
            r = rmse(pkt, K, float(p))
            if r < naj[0]:
                naj = (r, float(b), float(p))
    return naj[1], naj[2]


def przewidz(K, n, rok, prog):
    if n not in K or rok not in K[n]:
        return None
    doy, c = K[n][rok]
    i = np.searchsorted(c, prog)
    return float(doy[i]) if i < len(doy) else None


if __name__ == "__main__":
    obs = json.loads((WYNIKI / "json" / "fenologia_wielo.json")
                     .read_text(encoding="utf-8"))["obserwacje"]
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])
    wszystkie = [(n, int(r), v) for n, s in obs.items() for r, v in s.items()]
    med = {}
    for n, r, v in wszystkie:
        med.setdefault(r, []).append(v)
    med = {r: float(np.median(v)) for r, v in med.items()}

    print(f"obserwacji: {len(wszystkie)}, obszarow: {len(obs)}\n")
    print("liczenie kumulacji GDD...", flush=True)
    KUM = {b: kum(dfm, float(b), D0) for b in BAZY}
    print("gotowe\n")

    print(f"{'prog':>6}{'obs.':>7}{'odrzuc.':>9}{'baza':>7}{'prog GDD':>10}"
          f"{'dopas.':>9}{'LOO':>8}{'najgorszy':>11}")
    tab = []
    for po in PROGI_ODRZUTU:
        pkt = [(n, r, v) for n, r, v in wszystkie if abs(v - med[r]) <= po]
        if len(pkt) < 20:
            continue
        b, p = dopasuj(pkt, KUM)
        bl = [przewidz(KUM[b], n, r, v) - v for n, r, v in pkt
              if przewidz(KUM[b], n, r, p) is not None]
        bl = [przewidz(KUM[b], n, r, p) - v for n, r, v in pkt
              if przewidz(KUM[b], n, r, p) is not None]
        rin = float(np.sqrt(np.mean(np.square(bl))))
        cv = []
        for i, (n, r, v) in enumerate(pkt):
            bb, pp = dopasuj(pkt[:i] + pkt[i + 1:], KUM)
            q = przewidz(KUM[bb], n, r, pp)
            if q is not None:
                cv.append(q - v)
        cv = np.array(cv, float)
        rcv = float(np.sqrt(np.mean(cv ** 2)))
        et = "bez odrzutu" if po == 999 else f"{po} d"
        print(f"{et:>6}{len(pkt):>7}{len(wszystkie)-len(pkt):>9}"
              f"{b:>7.1f}{p:>10.0f}{rin:>9.2f}{rcv:>8.2f}{np.abs(cv).max():>10.1f} d")
        tab.append({"prog_odrzutu_d": None if po == 999 else po,
                    "n": len(pkt), "odrzuconych": len(wszystkie) - len(pkt),
                    "baza": b, "prog_gdd": p, "rmse_dopasowania": rin,
                    "rmse_loo": rcv, "najgorszy_d": float(np.abs(cv).max())})

    print("\nJAK TO CZYTAC")
    print("  Prog fizyczny wyprowadzony przed spojrzeniem na bledy wynosi ok. 6 d.")
    print("  Im luzniejszy prog, tym wiecej awarii odczytu zostaje w zbiorze")
    print("  i tym gorszy wynik - ale odrzucanie wiecej niz ok. 10% obserwacji")
    print("  zaczyna byc dobieraniem danych pod wynik.")

    (WYNIKI / "json" / "odrzut_punktowy.json").write_text(json.dumps({
        "problem": "po rozszerzeniu do 19 obszarow awarie odczytu sa "
                   "rozproszone, wiec regula sezonowa przestala dzialac",
        "prog_fizyczny_d": 6,
        "uzasadnienie": "rozrzut modelowany miedzy obszarami: mediana 2 d, "
                        "maks 5 d -> odchylenie od mediany do 2.5 d z termiki; "
                        "plus ok. 3 d niepewnosci odczytu NDYI",
        "warianty": tab,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/odrzut_punktowy.json")
