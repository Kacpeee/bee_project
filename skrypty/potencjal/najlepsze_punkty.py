"""
ETAP 32 - OD MAPY DO PUNKTU: gdzie konkretnie postawic ul.

PO CO
Mapa potencjalu odpowiada "w ktorym rejonie", ale pszczelarz potrzebuje
wspolrzednych. Ten skrypt zamienia pole potencjalu na LISTE MIEJSC.

DLACZEGO NIE TRZEBA SCHODZIC DO 10 M
Kusi, zeby przeliczyc wszystko w rozdzielczosci Sentinela (10 m) i dopiero
wtedy wskazac punkt. To jest zbedne: jadro zasiegu lotu rozmywa pozytek na
1178 m (wiosna), wiec pole potencjalu jest gladkie. Maksimum policzone na
siatce 100 m lezy w tym samym miejscu co policzone na 10 m - dostalibysmy
ten sam punkt po stukrotnie dluzszym liczeniu.

PROMIEN ROWNOWAZNOSCI - dlaczego sama wspolrzedna klamie
Skoro pole jest gladkie, to maksimum jest PLASKIE. Podanie punktu z
dokladnoscia do metra sugerowalaby precyzje, ktorej nie ma. Dlatego dla
kazdego miejsca liczony jest promien, w ktorym potencjal trzyma sie
POWYZEJ 95% maksimum lokalnego.

Komunikat dla pszczelarza brzmi wtedy uczciwie:
    "optimum tutaj, ale w promieniu R jest praktycznie tak samo dobrze -
     wybierz w tym kole miejsce z dojazdem, oslona od wiatru i woda"

To jest wazne praktycznie, bo pszczelarz i tak nie postawi ula na srodku
cudzego pola. Dostaje obszar do negocjacji z rolnikiem, a nie punkt,
ktory moze wypasc w rowie.

ROZDZIELANIE MIEJSC
Dwa maksima blizej siebie niz zasieg lotu opisuja TO SAMO wzniesienie
pozytkowe - pszczola z obu punktow oblatuje te same pola. Dlatego kolejne
miejsca wybierane sa z zachowaniem minimalnego odstepu.

Uruchomienie:
    python skrypty/potencjal/najlepsze_punkty.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np                                            # noqa: E402
import rasterio                                               # noqa: E402
from pyproj import Transformer                                # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
RASTER = WYNIKI / "rastry" / "woj_koncowa_pojemnosc.tif"
PIKSEL = 100
# Odstep miedzy rekomendacjami. NIE jest to zasieg jadra (1178 m), bo przy
# takim odstepie pierwsza dziesiatka wypadala w jednym powiecie - pszczelarz
# nie potrzebuje pietnastu punktow w promieniu 5 km, tylko rozrzuconych po
# wojewodztwie. 8 km to okolo siedmiokrotnosc zasiegu lotu, wiec rekomendacje
# opisuja rozlaczne obszary pozytkowe.
ODSTEP_M = 8000.0
ILE = 12
# Progi rownowaznosci. Pierwotnie byl tylko 95% i wychodzil najczesciej 0 m -
# co samo w sobie jest wynikiem: pole potencjalu NIE jest plaskie w skali
# 100 m, mimo ze splot je wygladza. Dlatego podajemy trzy progi.
PROGI_ROWNOWAZNOSCI = (0.95, 0.90, 0.80)


def promien_rownowaznosci(m: np.ndarray, iy: int, ix: int,
                          udzial: float) -> float:
    """Do jakiej odleglosci potencjal trzyma sie powyzej `udzial` maksimum."""
    szczyt = m[iy, ix]
    prog = szczyt * udzial
    for r in range(1, 40):
        y0, y1 = max(0, iy - r), min(m.shape[0], iy + r + 1)
        x0, x1 = max(0, ix - r), min(m.shape[1], ix + r + 1)
        wyc = m[y0:y1, x0:x1]
        yy, xx = np.ogrid[y0:y1, x0:x1]
        d = np.hypot(yy - iy, xx - ix)
        pier = (d >= r - .5) & (d <= r + .5)
        if not pier.any():
            continue
        if np.nanmin(np.where(pier, wyc, np.inf)) < prog:
            return (r - 1) * PIKSEL
    return 39 * PIKSEL


if __name__ == "__main__":
    with rasterio.open(RASTER) as f:
        m = f.read(1).astype("float64")
        T = f.transform
    waz = np.isfinite(m)
    print(f"raster {m.shape}, pikseli z danymi: {waz.sum():,}")
    print(f"pojemnosc: mediana {np.nanmedian(m[waz]):.0f}, "
          f"maksimum {np.nanmax(m[waz]):.0f} rodzin\n")

    do4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    prac = np.where(waz, m, -np.inf)
    odstep_px = int(ODSTEP_M / PIKSEL)

    print("promien rownowaznosci [m] - ile mozna sie przesunac, tracac "
          "mniej niz 5 / 10 / 20% pozytku")
    print()
    print(f"{'#':>3}{'rodzin':>9}{'95%':>8}{'90%':>8}{'80%':>8}"
          f"{'szerokosc':>12}{'dlugosc':>10}")
    miejsca = []
    for k in range(ILE):
        iy, ix = np.unravel_index(np.argmax(prac), prac.shape)
        if not np.isfinite(prac[iy, ix]):
            break
        wart = float(m[iy, ix])
        pr = {u: promien_rownowaznosci(m, iy, ix, u)
              for u in PROGI_ROWNOWAZNOSCI}
        r95 = pr[0.95]
        x, y = T * (ix + 0.5, iy + 0.5)
        lon, lat = do4326.transform(x, y)
        miejsca.append({"nr": k + 1, "rodzin": wart,
                        "promien_95_m": pr[0.95], "promien_90_m": pr[0.90],
                        "promien_80_m": pr[0.80], "lat": lat, "lon": lon,
                        "x_2180": float(x), "y_2180": float(y)})
        print(f"{k+1:>3}{wart:>9.0f}{pr[0.95]:>8.0f}{pr[0.90]:>8.0f}"
              f"{pr[0.80]:>8.0f}{lat:>12.4f}{lon:>10.4f}")
        # wygas cale wzniesienie, zeby kolejny punkt byl innym miejscem
        y0, y1 = max(0, iy - odstep_px), min(m.shape[0], iy + odstep_px + 1)
        x0, x1 = max(0, ix - odstep_px), min(m.shape[1], ix + odstep_px + 1)
        prac[y0:y1, x0:x1] = -np.inf

    print()
    for u in PROGI_ROWNOWAZNOSCI:
        r = [q[f"promien_{int(u*100)}_m"] for q in miejsca]
        print(f"  prog {u:.0%}: mediana {np.median(r):.0f} m, "
              f"zakres {min(r):.0f}-{max(r):.0f} m")
    print()
    print("WNIOSEK - ODWROTNY, NIZ ZAKLADANO")
    print("  Przy progu 5% promien bywa ZEROWY: przesuniecie o 100 m")
    print("  kosztuje ponad 5% pozytku. Pole potencjalu NIE jest plaskie")
    print("  w skali stu metrow, mimo ze splot jadrem 1178 m je wygladza.")
    print("  Twierdzenie, ze potencjal w obrebie pola jest staly, bylo")
    print("  ZALOZENIEM - pomiar je obala. Mapa 100 m niesie informacje")
    print("  o wyborze MIEJSCA, nie tylko rejonu.")
    print("  a nie mapa - i tak nalezy to pszczelarzowi zakomunikowac.")

    (WYNIKI / "json" / "najlepsze_punkty.json").write_text(json.dumps({
        "zrodlo": "woj_koncowa_pojemnosc.tif - produkt koncowy, przecietny "
                  "rok z 7 sezonow, jednostka: rodziny pszczele",
        "odstep_m": ODSTEP_M,
        "uzasadnienie_odstepu": "8 km, ok. 7x zasieg lotu - przy odstepie "
                                "rownym zasiegowi (1178 m) cala czolowka "
                                "wypadala w jednym powiecie",
        "progi_rownowaznosci": list(PROGI_ROWNOWAZNOSCI),
        "uwaga": "promien rownowaznosci mowi, ze wewnatrz niego mapa NIE "
                 "rozstrzyga - decyduja dojazd, oslona od wiatru i woda",
        "miejsca": miejsca,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/najlepsze_punkty.json")
