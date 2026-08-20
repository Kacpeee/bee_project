"""
Jak dziala model W TRAKCIE sezonu - czyli jedyny sposob, w jaki jest uzyteczny.

ZARZUT, KTORY TO ROZSTRZYGA
Mapa terminu kwitnienia dla 2025 jest bezuzyteczna, bo ten rok juz byl. Dla
2027 nie da sie jej policzyc dzis, bo model potrzebuje temperatur od lutego do
kwietnia, a mamy sierpien 2026. Prognozy sezonowe na pol roku nie maja
uzytecznej sprawdzalnosci dla temperatury w Polsce.

JAK MODEL DZIALA NAPRAWDE
Prognoza sie zaciesnia w miare sezonu. W dniu decyzji bierzemy:
  - rzeczywiste GDD od 1 lutego do dzis
  - dla pozostalych dni srednia wieloletnia (klimatologia)
i sprawdzamy, kiedy suma osiagnie prog. Im pozniej pytamy, tym wiekszy udzial
danych rzeczywistych i tym mniejszy blad.

To jest hindcast: udajemy, ze stoimy 1 marca 2019 i nie wiemy nic o reszcie
sezonu. Wynik mowi, ILE DNI WCZESNIEJ mozna wiedziec i z jakim bledem.

Uruchomienie:
    python prognoza_w_sezonie.py
"""

from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
PROG_ODRZUTU = 8   # dni od mediany sezonu, jak przy kalibracji
DNI_DECYZJI = [46, 60, 74, 91, 105, 121]      # 15 II, 1 III, 15 III, 1 IV, 15 IV, 1 V
TLO, ATRAMENT, MUTED = "#fcfcfb", "#141b16", "#6b756e"


def dz(doy: float, rok: int = 2025) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json").read_text(encoding="utf-8"))
    m = fin["model"]
    # start akumulacji z odrzut_sezonow.json - przesuniety na 15 III po
    # walidacji (patrz start_walidacja.py). Stary 1 II zostawiony jako
    # awaryjny, gdyby klucza brakowalo.
    d0 = None   # ustawiane nizej
    _os = json.loads((WYNIKI / "json" / "odrzut_sezonow.json")
                     .read_text(encoding="utf-8"))
    zle_sezony = set(_os["sezony_odrzucone"])
    baza, prog = _os["baza"], _os["prog"]
    d0 = _os.get("start_doy", 32)

    dfm = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])
    dfm["gdd"] = np.maximum((dfm["Tmax"] + dfm["Tmin"]) / 2 - baza, 0)
    obs = {n: {int(r): v for r, v in s.items()}
           for n, s in fin["obserwacje"].items()}
    # ODRZUT PUNKTOWY - te same 8 dni od mediany sezonu, co przy kalibracji.
    # Lista odrzuconych SEZONOW jest po rozszerzeniu proby pusta, bo awarie
    # odczytu sa rozproszone. Bez tego filtra prognoza liczyla sie takze na
    # obserwacjach z bledem do 43 dni i dawala 7.2 d zamiast realnych 3.9.
    _med = {}
    for _n, _s in obs.items():
        for _r, _v in _s.items():
            _med.setdefault(_r, []).append(_v)
    _med = {r: float(np.median(v)) for r, v in _med.items()}
    obs = {n: {r: v for r, v in s.items() if abs(v - _med[r]) <= PROG_ODRZUTU}
           for n, s in obs.items()}
    obs = {n: s for n, s in obs.items() if s}
    print(f'po odrzucie punktowym ({PROG_ODRZUTU} d): '
          f'{sum(len(s) for s in obs.values())} obserwacji, {len(obs)} obszarow')

    # klimatologia: srednie dobowe GDD dla kazdego obszaru i dnia roku
    klim = dfm.groupby(["obszar", "doy"])["gdd"].mean().unstack(fill_value=0)

    wyniki = {d: [] for d in DNI_DECYZJI}
    for n, s in obs.items():
        g = dfm[dfm["obszar"] == n]
        for rok, praw in s.items():
            if rok in zle_sezony:
                continue
            rr = g[g["rok"] == rok].sort_values("doy")
            if rr.empty:
                continue
            doy = rr["doy"].to_numpy()
            gdd = rr["gdd"].to_numpy()
            for dd in DNI_DECYZJI:
                # dane rzeczywiste do dnia decyzji, dalej klimatologia
                mieszane = np.where(doy <= dd, gdd,
                                    klim.loc[n].reindex(doy, fill_value=0).to_numpy())
                mieszane = np.where(doy < d0, 0, mieszane)
                i = np.searchsorted(np.cumsum(mieszane), prog)
                if i < len(doy):
                    wyniki[dd].append(doy[i] - praw)

    print("BLAD PROGNOZY W ZALEZNOSCI OD DNIA DECYZJI\n")
    print(f"{'dzien decyzji':>15}{'RMSE':>8}{'sr. blad':>10}{'wyprzedzenie':>15}{'n':>5}")
    stat = {}
    sr_kwit = np.mean([v for s in obs.values() for v in s.values()])
    for dd in DNI_DECYZJI:
        b = np.array(wyniki[dd], float)
        r = float(np.sqrt(np.mean(b ** 2)))
        stat[dd] = {"rmse": r, "bias": float(b.mean()), "n": len(b)}
        print(f"{dz(dd):>15}{r:>8.1f}{b.mean():>+10.1f}{sr_kwit-dd:>12.0f} dni{len(b):>5}")
    # RMSE po sezonie z odrzut_sezonow.json, nie ze starego fenologia_final -
    # inaczej ostatni wiersz stalby na zbiorze 52 obs., a reszta tabeli na 45.
    peln = _os["rmse_walidacji_loo"]
    print(f"{'po sezonie':>15}{peln:>8.1f}{'':>10}{'0':>12} dni")

    # --- wykres
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=170)
    fig.patch.set_facecolor(TLO); ax.set_facecolor(TLO)
    x = [sr_kwit - d for d in DNI_DECYZJI]
    y = [stat[d]["rmse"] for d in DNI_DECYZJI]
    ax.plot(x, y, "-o", color="#d4542a", lw=2.4, ms=7, zorder=3,
            label="prognoza w trakcie sezonu")
    ax.axhline(peln, color=MUTED, ls="--", lw=1.6, zorder=2)
    ax.text(x[0], peln - .35, f"model z pełnymi danymi: {peln:.1f} dnia",
            fontsize=9.5, color=MUTED, va="top")
    for xi, yi, dd in zip(x, y, DNI_DECYZJI):
        ax.annotate(dz(dd), (xi, yi), xytext=(0, 11), textcoords="offset points",
                    ha="center", fontsize=9, color=ATRAMENT, weight="bold")
    ax.set_xlabel("ile dni przed kwitnieniem pytamy", fontsize=10.5, color=ATRAMENT)
    ax.set_ylabel("błąd prognozy [dni]", fontsize=10.5, color=ATRAMENT)
    ax.invert_xaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e1e0d9", lw=.8); ax.set_axisbelow(True)
    ax.set_title("Im bliżej kwitnienia, tym pewniejsza prognoza",
                 fontsize=14, weight="bold", color=ATRAMENT, loc="left", pad=20)
    ax.text(0, 1.005, f"hindcast na {len(pkt) if 'pkt' in dir() else stat[DNI_DECYZJI[0]]['n']} obserwacjach: w dniu decyzji znane są tylko "
            "temperatury do tego dnia, dalej średnia wieloletnia",
            transform=ax.transAxes, fontsize=9.5, color=MUTED, va="bottom")
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    (ROOT / "mapy" / "wykres_prognoza.png").write_bytes(buf.getvalue())

    (WYNIKI / "json" / "prognoza_w_sezonie.json").write_text(json.dumps({
        "model": m, "dni_decyzji": DNI_DECYZJI,
        "sredni_termin_kwitnienia": float(sr_kwit),
        "statystyki": {str(k): v for k, v in stat.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano wykres_prognoza.png")
