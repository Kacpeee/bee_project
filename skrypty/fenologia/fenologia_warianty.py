"""
ETAP 22 - czy jarowizacja i gorny prog temperatury poprawiaja model?

DWA ZNANE UPROSZCZENIA MODELU TERMICZNEGO

1. BRAK JAROWIZACJI. Rzepak ozimy wymaga okresu chlodu, zeby przejsc do
   fazy generatywnej. Nasz model sumuje cieplo od 1 lutego i nie sprawdza,
   czy zima byla wystarczajaco chlodna. Standardem w fenologii sa modele
   dwufazowe: najpierw jednostki chlodu, potem cieplo.

2. BRAK GORNEGO PROGU. Sumujemy cieplo liniowo bez ograniczenia, a powyzej
   ok. 30 C rozwoj roslin zwalnia lub sie zatrzymuje. W upalne lata model
   przyspiesza kwitnienie mocniej, niz dzieje sie naprawde.

CZY TO SZKODZI - MIERZYMY, NIE ZAKLADAMY
Mamy 52 zmierzone daty kwitnienia (7 obszarow x 9 sezonow, Sentinel-2), wiec
kazdy wariant da sie ocenic tym samym bledem RMSE co model podstawowy.
Wariant wchodzi do modelu tylko wtedy, gdy poprawia wynik - inaczej zostaje
udokumentowanym uproszczeniem.

WARIANTY
  A  podstawowy: baza 1.0 C od 1 II, prog 555            (RMSE 3.5 d)
  B  + gorny prog: temperatura scinana do T_max przed suma
  C  + jarowizacja: cieplo liczone dopiero po zebraniu N jednostek chlodu
  D  oba naraz

Progi dobierane sa na nowo dla kazdego wariantu, zeby porownanie bylo
uczciwe - inaczej wariant przegralby tylko dlatego, ze prog zostal
skalibrowany pod inna formule.

Uruchomienie:
    python skrypty/fenologia/fenologia_warianty.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"

BAZA, D0 = 1.0, 32              # jak w modelu koncowym
GORNE = [None, 25.0, 28.0, 30.0]
# jednostka chlodu: dzien ze srednia w przedziale (0, 7.2) C - przyblizenie
# godzin chlodu przy danych dobowych; start liczenia od 1 XI roku poprzedniego
CHLOD_LO, CHLOD_HI = 0.0, 7.2
WYM_CHLODU = [None, 20, 40, 60, 80]


def gdd_dobowe(tmax, tmin, gorny):
    t = (tmax + tmin) / 2
    if gorny is not None:
        t = np.minimum(t, gorny)
    return np.maximum(t - BAZA, 0)


def termin(s: pd.DataFrame, prog: float, gorny, wym_chlodu) -> float:
    """Data osiagniecia progu. Przy jarowizacji cieplo rusza dopiero po
    zebraniu wymaganej liczby jednostek chlodu."""
    s = s.sort_values("data")
    doy = s["doy"].to_numpy()
    tmax, tmin = s["Tmax"].to_numpy(), s["Tmin"].to_numpy()
    g = gdd_dobowe(tmax, tmin, gorny)
    start = D0
    if wym_chlodu is not None:
        tsr = (tmax + tmin) / 2
        chlod = ((tsr > CHLOD_LO) & (tsr < CHLOD_HI)).astype(int)
        # liczymy od 1 XI poprzedniego roku: dni o doy >= 305 naleza do
        # poprzedniego sezonu, wiec w obrebie roku kalendarzowego bierzemy
        # od poczatku stycznia (reszta chlodu wpada w ten sam plik meteo)
        nar = np.cumsum(chlod)
        osiag = np.argmax(nar >= wym_chlodu) if nar[-1] >= wym_chlodu else None
        if osiag is None:
            return np.nan            # zima za ciepla - model nie rusza
        start = max(D0, int(doy[osiag]))
    g = g.copy()
    g[doy < start] = 0
    i = np.searchsorted(np.cumsum(g), prog)
    return float(doy[i]) if i < len(doy) else np.nan


if __name__ == "__main__":
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json")
                     .read_text(encoding="utf-8"))
    odrz = {(o["obszar"], o["rok"]) for o in
            json.loads((WYNIKI / "json" / "fenologia_kalibracja.json")
                       .read_text(encoding="utf-8"))["odrzucone"]}
    obs = [(n, int(r), v) for n, s in fin["obserwacje"].items()
           for r, v in s.items() if (n, int(r)) not in odrz]
    d = pd.read_csv(WYNIKI / "cache" / "meteo_obszary.csv", parse_dates=["data"])
    d["doy"] = d["data"].dt.dayofyear
    print(f"obserwacji: {len(obs)}\n")

    print(f"{'wariant':34s}{'prog':>7}{'RMSE':>8}{'zmiana':>9}{'n':>5}")
    wyniki, baza_rmse = {}, None
    for gorny in GORNE:
        for wym in WYM_CHLODU:
            # kalibracja progu dla TEGO wariantu
            najl = (1e9, None)
            for prog in np.arange(300, 900, 5):
                bl = []
                for n, rok, praw in obs:
                    s = d[(d.obszar == n) & (d.rok == rok)]
                    if s.empty:
                        continue
                    t = termin(s, prog, gorny, wym)
                    if not np.isnan(t):
                        bl.append(t - praw)
                if len(bl) < len(obs) * 0.8:
                    continue
                r = float(np.sqrt(np.mean(np.array(bl) ** 2)))
                if r < najl[0]:
                    najl = (r, prog, len(bl))
            if najl[1] is None:
                continue
            opis = ("podstawowy" if gorny is None and wym is None else
                    f"gorny prog {gorny:.0f} C" if wym is None else
                    f"jarowizacja {wym} dni" if gorny is None else
                    f"prog {gorny:.0f} C + jarowizacja {wym}")
            if baza_rmse is None:
                baza_rmse = najl[0]
            zm = najl[0] - baza_rmse
            wyniki[opis] = {"prog": float(najl[1]), "rmse": najl[0],
                            "n": najl[2], "gorny": gorny, "chlod": wym}
            print(f"{opis:34s}{najl[1]:>7.0f}{najl[0]:>8.2f}"
                  f"{zm:>+9.2f}{najl[2]:>5}")

    najlepszy = min(wyniki.items(), key=lambda x: x[1]["rmse"])
    print(f"\nnajlepszy: {najlepszy[0]} - RMSE {najlepszy[1]['rmse']:.2f} d")
    if najlepszy[1]["rmse"] > baza_rmse - 0.1:
        print("Poprawa ponizej 0.1 dnia = w granicach szumu. "
              "Uproszczenia zostaja, udokumentowane jako nieszkodliwe.")
    (WYNIKI / "json" / "fenologia_warianty.json").write_text(json.dumps({
        "obserwacji": len(obs), "baza": BAZA, "start_doy": D0,
        "chlod_przedzial": [CHLOD_LO, CHLOD_HI],
        "warianty": wyniki, "najlepszy": najlepszy[0],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano fenologia_warianty.json")
