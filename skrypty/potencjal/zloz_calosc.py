"""
ETAP 25 - zlozenie calosci: mapa pojemnosci pasiecznej przecietnego roku.

CO TO SPINA
Wszystkie ustalenia projektu w jeden produkt. Kazda warstwa ma udokumentowane
zrodlo i uzasadnienie, dlaczego pochodzi wlasnie stamtad:

  GATUNKI WEDRUJACE (rzepak, gryka, slonecznik) - z DETEKCJI satelitarnej,
  osobno dla kazdego sezonu. Uzasadnienie: test przenoszenia wykazal, ze
  model bije odniesienie "roslo tam, gdzie rok temu" (rzepak 0.958 wobec
  0.338). Te uprawy chodza w plodozmianie, wiec deklaracje sprzed roku sa
  dla nich bezuzyteczne.

  GATUNKI TRWALE (laki, malina, porzeczka, sad, motylkowe, fasola, bobik,
  gorczyca) - z DEKLARACJI, zamrozone. Uzasadnienie: dla nich pamiec
  o miejscu WYGRYWA z modelem, bo one sie nie przemieszczaja. To jest
  metoda poprawna, nie awaryjna.

  TERMINY - z modelu sum temperatur dla wszystkich 15 gatunkow, osobno dla
  kazdego sezonu. Zaden gatunek nie ma juz sztywnej daty.

  JEDNOSTKA - pojemnosc pasieczna (ile rodzin wyzywi miejsce), nie tony
  cukru. Znosi problem braku nasycenia: rodzina zbierze tyle samo, czy
  w zasiegu jest 10 czy 20 ton.

CZEGO TU NIE MA
Pozytkow dzikich - lipy, akacji, nawloci, mniszka. Sprawdzian wobec GUS
wykazal, ze mapa niedoszacowuje o ok. 27%, a to jest spodziewany kierunek
wlasnie z tego powodu.

Uruchomienie:
    python skrypty/potencjal/zloz_calosc.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import rasterio
from scipy.signal import fftconvolve

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import potencjal_gsa as P
import wojewodztwo as W
from podzial_upraw import NIEWEDRUJACE, WEDRUJACE, sprawdz_kompletnosc

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
LATA = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
ZAPOTRZEBOWANIE = 90.0 / 1.25       # kg cukrow na rodzine na sezon


if __name__ == "__main__":
    kal = json.loads((WYNIKI / "json" / "kalibracja_arealowa.json")
                     .read_text(encoding="utf-8"))
    wsp = kal["wspolczynniki"]
    # Jadra SEZONOWE i ZNORMALIZOWANE - te same, co w wojewodztwo.py.
    # Wczesniej bylo tu jedno stale W.jadro() (lambda 1000, zasieg 3000).
    # Suma sie zgadzala (502.89 = SUMA_ODNIESIENIA), wiec bilans cukru byl
    # poprawny i blad nie rzucal sie w oczy - ale KSZTALT byl zly: rzepak
    # kwitnie wiosna, kiedy pszczoly lataja srednio 493 m, wiec jego jadro
    # ma zasieg 1178 m, a nie 3000 m. Warstwa zmienna rozmywala go wiec
    # 2.5x za szeroko, podczas gdy warstwa stala szla juz z jader
    # sezonowych. Produkt koncowy mieszal dwie konwencje.
    sprawdz_kompletnosc(P.POZYTKI)   # zaden pozytek nie moze wypasc
    _jadra = {}
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon_srednia.tif") as f:
        prof, ksztalt = f.profile, f.shape
        maska = ~np.isnan(f.read(1))

    # --- warstwa stala: gatunki trwale ze sredniej deklaracji 2025/26
    z25 = np.load(WYNIKI / "cache" / "woj_splot_2025.npz")
    z26 = np.load(WYNIKI / "cache" / "woj_splot_2026.npz")
    # STRAZNIK: gatunek trwaly wymieniony w NIEWEDRUJACE, ktorego nie ma
    # w cache, znikalby tu po cichu. Tak wlasnie gubil sie drugi pokos TUZ.
    brak = [n for n in NIEWEDRUJACE
            if n in P.POZYTKI and not any(n in z.files for z in (z25, z26))]
    if brak:
        raise SystemExit("CACHE NIEAKTUALNY - brak klas trwalych: "
                         + ", ".join(brak)
                         + " | usun woj_splot_*.npz i przelicz "
                           "wojewodztwo.py oraz wojewodztwo_sezony.py")
    stale = np.zeros(ksztalt, "float32")
    uzyte = []
    for n in NIEWEDRUJACE:
        if n not in P.POZYTKI:
            continue
        war = [z[n] for z in (z25, z26) if n in z.files]
        stale += np.mean(war, axis=0) * P.POZYTKI[n][0]
        uzyte.append(n)
    print(f"warstwa stala: {len(uzyte)} gatunkow trwalych "
          f"({stale[maska].sum()/W.SUMA_ODNIESIENIA/1e6:.1f} mln kg cukrow)")

    # --- warstwa zmienna: gatunki wedrujace z detekcji, sezon po sezonie
    print("\nwarstwa zmienna (detekcja, po kalibracji arealowej):")
    sezony, braki = {}, []
    for rok in LATA:
        f = WYNIKI / "cache" / f"wielo_klasy_{rok}.npz"
        if not f.exists():
            braki.append(rok)
            continue
        with np.load(f) as z:
            dostepne = list(z.files)
            war = np.zeros(ksztalt, "float32")
            szt = {}
            for n in WEDRUJACE:
                if n not in dostepne or n not in P.POZYTKI:
                    continue
                u = z[n] * wsp.get(n, 1.0)          # kalibracja arealowa
                spl = fftconvolve(u, W.jadro_dla(n, _jadra), mode="same")
                war += spl * P.POZYTKI[n][0]
                szt[n] = float(u[maska].sum())
        sezony[rok] = war
        print(f"  {rok}: " + ", ".join(f"{n.split()[0]} {v:,.0f} ha"
                                       for n, v in szt.items()))
    if braki:
        print(f"  brakuje sezonow: {braki} (liczenie w toku)")
    if not sezony:
        raise SystemExit("brak policzonych sezonow")

    # --- przecietny rok i pojemnosc
    zmienna = np.mean([sezony[r] for r in sorted(sezony)], axis=0)
    cukier = np.where(maska, zmienna + stale, np.nan)
    pojemnosc = cukier / ZAPOTRZEBOWANIE

    print(f"\nPRZECIETNY ROK ({len(sezony)} sezonow: "
          f"{', '.join(map(str, sorted(sezony)))})")
    # UWAGA: cukier[] to wynik SPLOTU, wiec kazdy kilogram jest policzony
    # tyle razy, ile wynosi suma jadra (~503). Surowa suma dawala 11 252
    # mln kg przy rzeczywistych 26 mln - liczbe bez sensu fizycznego.
    # Dzielenie przez sume jadra przywraca bilans.
    print(f"  cukier razem w wojewodztwie: "
          f"{np.nansum(cukier)/W.SUMA_ODNIESIENIA/1e6:,.1f} mln kg")
    print(f"  udzial warstwy satelitarnej: "
          f"{zmienna[maska].sum()/(zmienna[maska].sum()+stale[maska].sum()):.1%}")
    print("\n  POJEMNOSC PASIECZNA (rodzin w zasiegu lotu 3 km)")
    for q in (50, 75, 90, 99):
        print(f"    percentyl {q:>3}: {np.nanpercentile(pojemnosc, q):6.0f}")
    v = pojemnosc[maska]
    print(f"\n  powierzchnia >= 100 rodzin: {100*(v >= 100).mean():.1f}%")

    prof.update(dtype="float32", nodata=np.nan, count=1)
    for nazwa, arr in (("woj_koncowa_cukier", cukier),
                       ("woj_koncowa_pojemnosc", pojemnosc)):
        with rasterio.open(WYNIKI / "rastry" / f"{nazwa}.tif", "w",
                           **prof) as dst:
            dst.write(arr.astype("float32"), 1)

    (WYNIKI / "json" / "zloz_calosc.json").write_text(json.dumps({
        "sezony_uzyte": sorted(sezony), "sezony_brakujace": braki,
        "gatunki_z_detekcji": list(WEDRUJACE),
        "gatunki_z_deklaracji": uzyte,
        "zapotrzebowanie_rodziny_kg_cukrow": ZAPOTRZEBOWANIE,
        "cukier_razem_mln_kg": float(np.nansum(cukier) / 1e6),
        "udzial_satelity": float(
            zmienna[maska].sum() / (zmienna[maska].sum() + stale[maska].sum())),
        "pojemnosc_percentyle": {str(q): float(np.nanpercentile(pojemnosc, q))
                                 for q in (50, 75, 90, 99)},
        "brak": "pozytki dzikie (lipa, akacja, nawloc, mniszek) - "
                "sprawdzian wobec GUS wskazuje niedoszacowanie ok. 27%",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano woj_koncowa_*.tif i zloz_calosc.json")
