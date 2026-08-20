"""
ETAP 27 - jadro zasiegu lotu ZMIENNE SEZONOWO.

PROBLEM
Caly projekt uzywal jednego jadra exp(-d/1000) obcietego na 3 km, dla
wszystkich gatunkow i calego sezonu. Tymczasem zmierzone dystanse lotu sa
silnie sezonowe (Couvillon i in., PLOS ONE 2014, odczyt 5 tys. tancow):

    wiosna  493 m       lato 2156 m       jesien 1275 m

Roznica miedzy wiosna a latem jest CZTEROKROTNA. Powod jest biologiczny:
latem w krajobrazie jest mniej kwiatow, wiec pszczoly szukaja dalej.

Nasze stale jadro bylo wiec za szerokie dla rzepaku i za waskie dla gryki
i slonecznika - czyli systematycznie zanizalo pozytki lipcowe i sierpniowe,
a to jest dokladnie ta czesc kalendarza, ktora i tak jest najslabsza.

JAK DOBRANO LAMBDA
Dla wagi exp(-d/lambda) na plaszczyznie sredni dystans wazony wynosi w
przyblizeniu 3*lambda (dla zasiegu nieskonczonego). Przy obcieciu na R
zaleznosc jest slabsza, wiec lambda dobierana jest NUMERYCZNIE tak, by
sredni wazony dystans jadra rownal sie wartosci zmierzonej dla danej pory.
Zasieg R = 4*lambda obejmuje ok. 99% wagi.

PRZYPISANIE PORY
Wg daty pelni kwitnienia gatunku (z modelu fenologicznego):
    do 31 V      - wiosna
    1 VI - 31 VIII - lato
    od 1 IX      - jesien

Uruchomienie:
    python skrypty/potencjal/jadro_sezonowe.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL = 100

# zmierzone srednie dystanse lotu [m] - Couvillon i in. 2014
DYSTANS = {"wiosna": 493.0, "lato": 2156.0, "jesien": 1275.0}


def sredni_dystans(lam: float, zasieg: float) -> float:
    """Sredni dystans wazony jadrem exp(-d/lam) obcietym na zasieg."""
    r = int(zasieg // PIKSEL)
    i = np.arange(-r, r + 1)
    dx, dy = np.meshgrid(i, i)
    d = np.hypot(dx, dy) * PIKSEL
    w = np.where(d <= zasieg, np.exp(-d / lam), 0.0)
    return float((d * w).sum() / w.sum())


def dobierz_lambda(cel: float) -> tuple[float, float]:
    """Lambda dajaca zadany sredni dystans; zasieg = 4*lambda."""
    lo, hi = 20.0, 3000.0
    for _ in range(40):
        sr = (lo + hi) / 2
        if sredni_dystans(sr, 4 * sr) < cel:
            lo = sr
        else:
            hi = sr
    lam = (lo + hi) / 2
    return lam, 4 * lam


def jadro(lam: float, zasieg: float) -> np.ndarray:
    r = int(zasieg // PIKSEL)
    i = np.arange(-r, r + 1)
    dx, dy = np.meshgrid(i, i)
    d = np.hypot(dx, dy) * PIKSEL
    return np.where(d <= zasieg, np.exp(-d / lam), 0.0)


def pora_dla(doy: float) -> str:
    if doy < 152:
        return "wiosna"
    return "lato" if doy < 244 else "jesien"


if __name__ == "__main__":
    print("KALIBRACJA JADER NA ZMIERZONYCH DYSTANSACH LOTU\n")
    print(f"{'pora':10s}{'dystans (Couvillon)':>21}{'lambda':>9}"
          f"{'zasieg':>9}{'kontrola':>10}")
    jadra = {}
    for pora, cel in DYSTANS.items():
        lam, zas = dobierz_lambda(cel)
        K = jadro(lam, zas)
        jadra[pora] = {"lambda_m": lam, "zasieg_m": zas,
                       "suma_jadra": float(K.sum()),
                       "px": int(K.shape[0]),
                       "sredni_dystans_m": sredni_dystans(lam, zas)}
        print(f"{pora:10s}{cel:>18.0f} m{lam:>8.0f} m{zas:>8.0f} m"
              f"{jadra[pora]['sredni_dystans_m']:>8.0f} m")

    # dotychczasowe jadro dla porownania
    stare = sredni_dystans(1000.0, 3000.0)
    K_stare = jadro(1000.0, 3000.0)
    print(f"\n{'dotychczasowe':10s}{'(lambda 1000, zasieg 3000)':>21}"
          f"{'':>18}{stare:>8.0f} m")

    print(f"\nCO TO ZMIENIA\n{'pora':10s}{'zmiana sredniego dystansu':>28}"
          f"{'zmiana sumy jadra':>20}")
    for pora, j in jadra.items():
        print(f"{pora:10s}{j['sredni_dystans_m']/stare:>26.2f}x"
              f"{j['suma_jadra']/K_stare.sum():>19.2f}x")

    print("\nWNIOSEK")
    print("  Wiosna (rzepak, 57% cukrow): zasieg zawezony - dotychczasowa")
    print("  mapa ROZMYWALA rzepak szerzej, niz pszczoly realnie lataja.")
    print("  Lato (gryka, slonecznik): zasieg poszerzony - te pozytki byly")
    print("  systematycznie zanizane, bo obcinalismy je na 3 km.")

    (WYNIKI / "json" / "jadro_sezonowe.json").write_text(json.dumps({
        "zrodlo": "Couvillon M.J. i in., PLOS ONE 9(4), 2014 - odczyt 5 tys. "
                  "tancow pszczelich; srednie dystanse lotu wg pory roku",
        "dystanse_zmierzone_m": DYSTANS,
        "jadra": jadra,
        "poprzednie": {"lambda_m": 1000.0, "zasieg_m": 3000.0,
                       "sredni_dystans_m": stare,
                       "suma_jadra": float(K_stare.sum())},
        "przypisanie_pory": "wg DOY pelni kwitnienia: <152 wiosna, "
                            "152-243 lato, >=244 jesien",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano jadro_sezonowe.json")
