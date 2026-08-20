"""
ETAP 35 - dlaczego prognoza nie poprawia sie miedzy lutym a kwietniem.

OBSERWACJA
Blad prognozy terminu kwitnienia rzepaku wg dnia decyzji:
    15 II  7.3 d      1 IV  7.8 d
    1 III  7.4 d     15 IV  6.4 d
    15 III 6.7 d      1 V   4.8 d
Przez dwa i pol miesiaca nie poprawia sie wcale - spada dopiero na
przelomie kwietnia i maja. Czyli wczesna pogoda nie niesie informacji.

HIPOTEZA
Akumulacja GDD startuje 1 II (d0=32). Przy niskich temperaturach lutowych
przyrosty sa bliskie zeru, wiec pierwsze tygodnie nie roznicuja lat -
model "czeka" na cieplo i dopiero wtedy zaczyna rozrozniac sezony.
Jesli tak, przesuniecie startu nic nie zmieni (te dni i tak nic nie wnosza),
ale rowniez nie zaszkodzi - a moze poprawic, jesli obecny start wprowadza
szum z przypadkowych cieplych dni w lutym.

CO ROBIMY
Dla kazdego kandydata na dzien startu przeliczamy pelna kalibracje
(baza + prog) i blad prognozy w kazdym dniu decyzji. Porownanie pokazuje,
czy problem lezy w starcie akumulacji, czy gdzie indziej.

Uruchomienie:
    python skrypty/fenologia/start_akumulacji.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walidacja_krzyzowa import BAZY, PROGI

WYNIKI = ROOT / "wyniki"
STARTY = [1, 15, 32, 46, 60, 74]          # 1 I, 15 I, 1 II, 15 II, 1 III, 15 III
DNI_DECYZJI = [46, 60, 74, 91, 105, 121]  # 15 II ... 1 V


def kum(dfm, baza, d0):
    out = {}
    for n, g in dfm.groupby("obszar"):
        out[n] = {}
        for rok, s in g.groupby("rok"):
            s = s.sort_values("doy")
            gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - baza, 0)
            gdd[s["doy"].to_numpy() < d0] = 0
            out[n][int(rok)] = (s["doy"].to_numpy(), np.cumsum(gdd))
    return out


def rmse(pkt, K, prog):
    b = []
    for n, rok, praw in pkt:
        if n not in K or rok not in K[n]:
            continue
        doy, c = K[n][rok]
        i = np.searchsorted(c, prog)
        if i < len(doy):
            b.append((doy[i] - praw) ** 2)
    return (sum(b) / len(b)) ** .5 if b else np.inf


if __name__ == "__main__":
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json").read_text(encoding="utf-8"))
    _os = json.loads((WYNIKI / "json" / "odrzut_sezonow.json").read_text(encoding="utf-8"))
    zle = set(_os["sezony_odrzucone"])
    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])
    pkt = [(n, int(r), v) for n, s in fin["obserwacje"].items()
           for r, v in s.items() if int(r) not in zle]
    print(f"obserwacji: {len(pkt)}, sezony odrzucone: {sorted(zle)}\n")

    print("KALIBRACJA DLA ROZNYCH DNI STARTU AKUMULACJI\n")
    print(f"{'start':>8}{'baza':>7}{'prog':>7}{'RMSE':>8}")
    naj = {}
    for d0 in STARTY:
        best = (np.inf, None, None)
        for b in BAZY:
            K = kum(dfm, b, d0)
            for p in PROGI:
                r = rmse(pkt, K, p)
                if r < best[0]:
                    best = (r, b, p)
        naj[d0] = best
        et = (pd.Timestamp("2025-01-01") + pd.Timedelta(days=d0 - 1)).strftime("%d %b")
        print(f"{et:>8}{best[1]:>7.1f}{best[2]:>7.0f}{best[0]:>8.2f}")

    # prognoza w sezonie dla najlepszego i obecnego startu
    print("\nBLAD PROGNOZY WG DNIA DECYZJI\n")
    klim_cache = {}
    naglowek = f"{'start':>8}" + "".join(f"{d:>7}" for d in DNI_DECYZJI)
    print(naglowek.replace("46", "15 II").replace("60", "1 III")
          .replace("74", "15III").replace("91", " 1 IV")
          .replace("105", "15 IV").replace("121", "  1 V"))
    tab = {}
    for d0 in STARTY:
        r0, baza, prog = naj[d0]
        dfm["gdd"] = np.maximum((dfm["Tmax"] + dfm["Tmin"]) / 2 - baza, 0)
        klim = dfm.groupby(["obszar", "doy"])["gdd"].mean().unstack(fill_value=0)
        wier = []
        for dd in DNI_DECYZJI:
            bl = []
            for n, rok, praw in pkt:
                g = dfm[(dfm["obszar"] == n) & (dfm["rok"] == rok)].sort_values("doy")
                if g.empty:
                    continue
                doy = g["doy"].to_numpy(); gdd = g["gdd"].to_numpy()
                mies = np.where(doy <= dd, gdd,
                                klim.loc[n].reindex(doy, fill_value=0).to_numpy())
                mies = np.where(doy < d0, 0, mies)
                i = np.searchsorted(np.cumsum(mies), prog)
                if i < len(doy):
                    bl.append(doy[i] - praw)
            wier.append(float(np.sqrt(np.mean(np.square(bl)))))
        tab[d0] = wier
        et = (pd.Timestamp("2025-01-01") + pd.Timedelta(days=d0 - 1)).strftime("%d %b")
        print(f"{et:>8}" + "".join(f"{v:>7.1f}" for v in wier))

    obecny = tab[32]
    najl = min(tab, key=lambda d: sum(tab[d][:4]))     # ktory najlepszy WCZESNIE
    print(f"\nobecny start: 1 II")
    et = (pd.Timestamp("2025-01-01") + pd.Timedelta(days=najl - 1)).strftime("%d %b")
    print(f"najlepszy dla wczesnych prognoz: {et}")
    zysk = [o - n for o, n in zip(obecny[:4], tab[najl][:4])]
    print(f"zysk w lutym-kwietniu: {np.mean(zysk):+.2f} d")

    (WYNIKI / "json" / "start_akumulacji.json").write_text(json.dumps({
        "pytanie": "czy dzien startu akumulacji GDD tlumaczy brak poprawy "
                   "prognozy miedzy lutym a kwietniem",
        "starty_testowane": [int(x) for x in STARTY],
        "kalibracja": {str(d): {"baza": float(naj[d][1]), "prog": float(naj[d][2]),
                                "rmse": float(naj[d][0])} for d in STARTY},
        "prognoza_wg_startu": {str(d): [float(v) for v in tab[d]] for d in STARTY},
        "dni_decyzji": [int(x) for x in DNI_DECYZJI],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/start_akumulacji.json")
