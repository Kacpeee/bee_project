"""
ETAP 13 - walidacja ERA5 wobec rzeczywistej stacji IMGW (Zamosc, kod 595).

PO CO
Caly model meteo stoi na reanalizie ERA5 (Open-Meteo). Reanaliza to model
fizyczny, nie termometr - jesli ma lokalny blad systematyczny, kalibracja
progu GDD wchlonela go po cichu. Dotad byl to jawnie otwarty punkt
w ZRODLA.md; tu go zamykamy pomiarem.

CO JEST POROWNYWANE (2018-2025, na wspolrzednych stacji 50.694N 23.246E):
  1. temperatura srednia dobowa II-V: blad sredni i RMSE
  2. suma GDD (baza 1.0, od 1 II) na 15 V kazdego roku
  3. TERMIN KWITNIENIA z obu zrodel - miara, ktora naprawde ma znaczenie:
     jesli daty roznia sie o <=1 dzien, zrodlo temperatur jest bez znaczenia

Dane stacyjne: danepubliczne.imgw.pl, pliki s_d_595_RRRR.csv (pobrane
do dane/imgw/). Uklad kolumn: 2=rok, 3=miesiac, 4=dzien, 5=TMAX, 7=TMIN.

Uruchomienie:
    python imgw_walidacja.py
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
import requests

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
IMGW = ROOT / "dane" / "imgw"

LAT, LON = 50.694, 23.246          # Zamosc-Mokre
LATA = range(2018, 2026)
BAZA, D0, PROG = 1.0, 32, 555      # model finalny
TLO, ATRAMENT, MUTED = "#fcfcfb", "#141b16", "#6b756e"
MIES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def dz(doy: float, rok: int = 2025) -> str:
    x = date(rok, 1, 1) + timedelta(days=int(round(doy)) - 1)
    return f"{x.day} {MIES[x.month - 1]}"


def imgw() -> pd.DataFrame:
    czesci = []
    for r in LATA:
        d = pd.read_csv(IMGW / f"s_d_595_{r}.csv", encoding="cp1250",
                        header=None, usecols=[2, 3, 4, 5, 7],
                        names=["rok", "mies", "dzien", "Tmax", "Tmin"])
        czesci.append(d)
    d = pd.concat(czesci, ignore_index=True)
    d["data"] = pd.to_datetime(dict(year=d.rok, month=d.mies, day=d.dzien))
    return d[["data", "rok", "Tmax", "Tmin"]]


def era5() -> pd.DataFrame:
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": LAT, "longitude": LON,
        "start_date": f"{LATA[0]}-01-01", "end_date": f"{LATA[-1]}-12-31",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Warsaw"}, timeout=120)
    r.raise_for_status()
    j = r.json()["daily"]
    d = pd.DataFrame({"data": pd.to_datetime(j["time"]),
                      "Tmax": j["temperature_2m_max"],
                      "Tmin": j["temperature_2m_min"]})
    d["rok"] = d["data"].dt.year
    return d


def termin(d: pd.DataFrame, rok: int) -> float:
    s = d[d["rok"] == rok].sort_values("data")
    doy = s["data"].dt.dayofyear.to_numpy()
    gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - BAZA, 0)
    gdd[doy < D0] = 0
    i = np.searchsorted(np.cumsum(gdd), PROG)
    return float(doy[i]) if i < len(doy) else np.nan


if __name__ == "__main__":
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    st, er = imgw(), era5()
    m = st.merge(er, on="data", suffixes=("_st", "_er"))
    m["rok"] = m["data"].dt.year
    m["Tsr_st"] = (m.Tmax_st + m.Tmin_st) / 2
    m["Tsr_er"] = (m.Tmax_er + m.Tmin_er) / 2
    w = m[m["data"].dt.month.isin([2, 3, 4, 5])].dropna(
        subset=["Tsr_st", "Tsr_er"])

    bias = float((w.Tsr_er - w.Tsr_st).mean())
    rmse = float(np.sqrt(((w.Tsr_er - w.Tsr_st) ** 2).mean()))
    r = float(np.corrcoef(w.Tsr_er, w.Tsr_st)[0, 1])
    print(f"II-V, {len(w):,} dni wspolnych:")
    print(f"  blad sredni ERA5-stacja: {bias:+.2f} K, RMSE {rmse:.2f} K, "
          f"r = {r:.3f}")

    print(f"\n{'rok':>6}{'stacja':>8}{'ERA5':>8}{'roznica':>9}")
    daty, rozn = {}, []
    for rok in LATA:
        ts = termin(st.rename(columns={"Tmax": "Tmax", "Tmin": "Tmin"}), rok)
        te = termin(er, rok)
        d_ = te - ts if not (np.isnan(ts) or np.isnan(te)) else np.nan
        daty[rok] = {"stacja": ts, "era5": te}
        if not np.isnan(d_):
            rozn.append(d_)
        print(f"{rok:>6}{dz(ts):>8}{dz(te):>8}{d_:>+8.0f} d")
    sr, mx = float(np.mean(rozn)), float(np.max(np.abs(rozn)))
    print(f"\nroznica terminu: srednio {sr:+.1f} dnia, maksymalnie {mx:.0f}")

    # --- wykres: rozrzut dobowy + roznice terminow
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.8), dpi=170)
    fig.patch.set_facecolor(TLO)
    a1.set_facecolor(TLO)
    a1.plot([-15, 30], [-15, 30], color=MUTED, lw=1, ls="--")
    a1.plot(w.Tsr_st, w.Tsr_er, ".", ms=2.5, color="#d4542a", alpha=.4)
    a1.set_xlabel("stacja IMGW Zamość [°C]", fontsize=10)
    a1.set_ylabel("ERA5 w punkcie stacji [°C]", fontsize=10)
    a1.set_title("Temperatura dobowa II–V, 2018–2025", fontsize=12,
                 weight="bold", color=ATRAMENT, loc="left")
    a1.text(.03, .96, f"błąd średni {bias:+.2f} K\nRMSE {rmse:.2f} K\n"
            f"r = {r:.3f}", transform=a1.transAxes, va="top", fontsize=9.5,
            family="monospace", color=ATRAMENT,
            bbox=dict(facecolor="#ffffff", edgecolor="#dde3dd", pad=5))
    a2.set_facecolor(TLO)
    lata = [r_ for r_ in LATA]
    dd = [daty[r_]["era5"] - daty[r_]["stacja"] for r_ in lata]
    a2.bar(lata, dd, color="#d4542a", width=.6)
    a2.axhline(0, color=ATRAMENT, lw=1)
    a2.set_ylim(-4, 4)
    a2.set_ylabel("dni (ERA5 − stacja)", fontsize=10)
    a2.set_title("Różnica przewidzianego terminu kwitnienia", fontsize=12,
                 weight="bold", color=ATRAMENT, loc="left")
    a2.text(.03, .96, f"średnio {sr:+.1f} d · maks {mx:.0f} d\n"
            f"błąd modelu: 3,5 d", transform=a2.transAxes, va="top",
            fontsize=9.5, family="monospace", color=ATRAMENT,
            bbox=dict(facecolor="#ffffff", edgecolor="#dde3dd", pad=5))
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
        a.grid(color="#e1e0d9", lw=.7)
        a.set_axisbelow(True)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    (ROOT / "mapy" / "wykres_imgw.png").write_bytes(buf.getvalue())

    (WYNIKI / "json" / "imgw_walidacja.json").write_text(json.dumps({
        "stacja": "Zamosc 595", "lata": list(LATA), "n_dni": int(len(w)),
        "bias_K": bias, "rmse_K": rmse, "r": r,
        "terminy": daty, "roznica_srednia_d": sr, "roznica_maks_d": mx,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano wykres_imgw.png i JSON")
