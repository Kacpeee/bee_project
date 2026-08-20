"""
ETAP 35b - czy przesuniecie startu akumulacji na 15 III jest prawdziwa
poprawa, czy artefaktem wyboru.

PROBLEM
Test szesciu dni startu pokazal, ze 15 III daje najlepszy RMSE (3.13 wobec
3.89 dla obecnego 1 II) i najlepsza prognoze na 1 V (3.9 wobec 4.8 dnia).
Ale wybralismy ten start PO ZOBACZENIU wynikow na tych samych danych -
przy szesciu kandydatach czesc przewagi moze byc przypadkiem.

CO ROBIMY
Leave-one-out dla obu wariantow: dla kazdej obserwacji parametry (baza,
prog) dobierane sa na pozostalych, blad liczony na odlozonej. Dodatkowo
wariant "start tez wybierany wewnatrz petli" - najostrzejszy test, bo
wtedy nawet wybor startu nie widzi ocenianej obserwacji.

Uruchomienie:
    python skrypty/fenologia/start_walidacja.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walidacja_krzyzowa import BAZY, PROGI
from start_akumulacji import kum, rmse, STARTY

WYNIKI = ROOT / "wyniki"


def dopasuj(pkt, KUM):
    naj = (np.inf, None, None)
    for b in BAZY:
        K = KUM[b]
        for p in PROGI:
            r = rmse(pkt, K, p)
            if r < naj[0]:
                naj = (r, b, p)
    return naj[1], naj[2]


def przewidz(K, n, rok, prog):
    if n not in K or rok not in K[n]:
        return None
    doy, c = K[n][rok]
    i = np.searchsorted(c, prog)
    return float(doy[i]) if i < len(doy) else None


if __name__ == "__main__":
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json").read_text(encoding="utf-8"))
    _os = json.loads((WYNIKI / "json" / "odrzut_sezonow.json").read_text(encoding="utf-8"))
    zle = set(_os["sezony_odrzucone"])
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])
    pkt = [(n, int(r), v) for n, s in fin["obserwacje"].items()
           for r, v in s.items() if int(r) not in zle]
    print(f"obserwacji: {len(pkt)}\n")

    print("liczenie kumulacji dla wszystkich startow i baz...", flush=True)
    KUM = {d0: {b: kum(dfm, b, d0) for b in BAZY} for d0 in STARTY}
    print("gotowe\n")

    wyn = {}
    for d0, et in ((32, "1 II  (obecny)"), (74, "15 III (kandydat)")):
        b0, p0 = dopasuj(pkt, KUM[d0])
        bl_in = [przewidz(KUM[d0][b0], n, r, p0) - v for n, r, v in pkt
                 if przewidz(KUM[d0][b0], n, r, p0) is not None]
        rin = float(np.sqrt(np.mean(np.square(bl_in))))
        bl = []
        for i, (n, r, v) in enumerate(pkt):
            b, p = dopasuj(pkt[:i] + pkt[i + 1:], KUM[d0])
            q = przewidz(KUM[d0][b], n, r, p)
            if q is not None:
                bl.append(q - v)
        bl = np.array(bl, float)
        rcv = float(np.sqrt(np.mean(bl ** 2)))
        wyn[d0] = {"opis": et, "baza": float(b0), "prog": float(p0),
                   "rmse_in": rin, "rmse_loo": rcv,
                   "najgorszy": float(np.abs(bl).max())}
        print(f"{et:20s} baza {b0:.1f}  prog {p0:.0f}  "
              f"dopasowanie {rin:.2f} d   LOO {rcv:.2f} d   "
              f"(optymizm {rcv-rin:+.2f})")

    # najostrzejszy test: start tez wybierany bez ocenianej obserwacji
    print("\nTEST NAJOSTRZEJSZY - start wybierany wewnatrz petli LOO")
    bl, wybory = [], {}
    for i, (n, r, v) in enumerate(pkt):
        reszta = pkt[:i] + pkt[i + 1:]
        naj = (np.inf, None, None, None)
        for d0 in STARTY:
            b, p = dopasuj(reszta, KUM[d0])
            rr = rmse(reszta, KUM[d0][b], p)
            if rr < naj[0]:
                naj = (rr, d0, b, p)
        _, d0, b, p = naj
        wybory[d0] = wybory.get(d0, 0) + 1
        q = przewidz(KUM[d0][b], n, r, p)
        if q is not None:
            bl.append(q - v)
    bl = np.array(bl, float)
    rcv_all = float(np.sqrt(np.mean(bl ** 2)))
    print(f"  RMSE {rcv_all:.2f} d, najgorszy {np.abs(bl).max():.1f} d")
    print(f"  ktory start wygrywal: " +
          ", ".join(f"{d}: {c}x" for d, c in sorted(wybory.items())))

    print("\nWERDYKT")
    if wyn[74]["rmse_loo"] < wyn[32]["rmse_loo"] - 0.2:
        print(f"  Przesuniecie startu na 15 III to PRAWDZIWA poprawa: "
              f"{wyn[32]['rmse_loo']:.2f} -> {wyn[74]['rmse_loo']:.2f} d "
              f"w walidacji krzyzowej.")
    else:
        print("  Przewaga 15 III NIE utrzymuje sie w walidacji krzyzowej -")
        print("  byla artefaktem wyboru sposrod szesciu kandydatow.")

    (WYNIKI / "json" / "start_walidacja.json").write_text(json.dumps({
        "warianty": {str(k): v for k, v in wyn.items()},
        "loo_ze_startem_w_petli": {"rmse": rcv_all,
                                   "wybory_startu": {str(k): v for k, v in wybory.items()}},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/start_walidacja.json")
