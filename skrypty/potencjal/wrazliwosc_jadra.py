"""
ETAP 29 - pomiar wplywu NORMALIZACJI jadra sezonowego na mape.

ZASTRZEZENIE, KTORE TO ROZSTRZYGA
Po wprowadzeniu jader sezonowych (etap 27) okazalo sie, ze jadra nie sa
znormalizowane, a ich sumy roznia sie drastycznie:

    wiosna  lambda  294 m, zasieg 1178 m  ->  suma jadra   50
    lato    lambda 1285 m, zasieg 5142 m  ->  suma jadra  943   (19.0x)
    jesien  lambda  760 m, zasieg 3041 m  ->  suma jadra  330   ( 6.7x)

Skutek: hektar pozytku letniego wchodzi do sumy sezonowej 19 RAZY mocniej
niz hektar pozytku wiosennego - wylacznie z geometrii jadra, nie z biologii.
Widac to wprost przy TUZ: ta sama powierzchnia 173 786 ha daje maksimum
47.5 dla I pokosu (wiosna) i 636.1 dla odrostu (lato).

DLACZEGO TO PODEJRZANE
Pszczoly lataja latem dalej, BO KWIATOW JEST MNIEJ (to wlasnie wniosek
Couvillon i in. 2014). Nieznormalizowane jadro premiuje wiec niedobor:
im pozytek rzadszy, tym szersze jadro, tym wiekszy wynik. To bledne kolo.

DWIE INTERPRETACJE - I NA TYM POLEGA SPOR
  A. splot nieznormalizowany = "ile cukru LACZNIE lezy w zasiegu lotu".
     Latem zasieg jest wiekszy, wiec faktycznie lezy go wiecej. Ale wtedy
     nie wolno tego sumowac miedzy porami jak rownowaznych skladnikow.
  B. splot znormalizowany (suma jadra = 1) = "GESTOSC pozytku wazona
     dostepnoscia". Gatunki porownuja sie wtedy wydajnoscia i powierzchnia,
     a zmierzony dystans lotu decyduje TYLKO o szerokosci rozmycia.

CO ROBI TEN SKRYPT
Nie rozstrzyga sporu deklaracja, tylko MIERZY, o ile rozjezdzaja sie mapy:
rasteryzuje kazda uprawe RAZ, splata dwoma wariantami jadra i porownuje
korelacja, wspolnym top-10% oraz przesunieciem udzialow miedzy porami.

Jesli mapy sa zbiezne - spor jest akademicki. Jesli nie - trzeba wybrac
swiadomie i zapisac wybor, a nie odziedziczyc go po przypadku.

Uruchomienie:
    python skrypty/potencjal/wrazliwosc_jadra.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np                                            # noqa: E402
import pyogrio                                                # noqa: E402
from rasterio.features import rasterize                       # noqa: E402
from rasterio.transform import from_origin                    # noqa: E402
from scipy.signal import fftconvolve                          # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import potencjal_gsa as P                                     # noqa: E402
from wojewodztwo import (PIKSEL, PIKSEL_RASTER, SHP, jadro,   # noqa: E402
                         JADRA_SEZONOWE, pora_kwitnienia)

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"


def top_procent(m, maska, p=10.0):
    return maska & (m >= np.percentile(m[maska], 100 - p))


if __name__ == "__main__":
    info = pyogrio.read_info(SHP)
    l, b, r, t = info["total_bounds"]
    l, b = np.floor(l / PIKSEL) * PIKSEL, np.floor(b / PIKSEL) * PIKSEL
    r, t = np.ceil(r / PIKSEL) * PIKSEL, np.ceil(t / PIKSEL) * PIKSEL
    nx, ny = int((r - l) / PIKSEL), int((t - b) / PIKSEL)
    kro = PIKSEL // PIKSEL_RASTER

    print("SUMY JADER SEZONOWYCH")
    jadra_raw, jadra_norm = {}, {}
    for pora, (lam, zas) in JADRA_SEZONOWE.items():
        K = jadro(lam, zas)
        jadra_raw[pora] = K
        jadra_norm[pora] = K / K.sum()
        print(f"  {pora:8s} suma {K.sum():8,.0f}   "
              f"{K.sum() / jadro(*JADRA_SEZONOWE['wiosna']).sum():5.1f}x wiosny")

    print("\nRasteryzacja raz, splot dwoma wariantami:")
    sur, nor, pory = {}, {}, {}
    for nazwa in P.POZYTKI:
        g = pyogrio.read_dataframe(
            SHP, encoding="utf-8",
            where=f"roslina = '{P.uprawa_zrodlowa(nazwa)}'")
        if g.empty:
            continue
        r20 = rasterize(((geom, 1) for geom in g.geometry),
                        out_shape=(ny * kro, nx * kro),
                        transform=from_origin(l, t, PIKSEL_RASTER, PIKSEL_RASTER),
                        fill=0, dtype="uint8")
        udzial = r20.reshape(ny, kro, nx, kro).mean(axis=(1, 3))
        del r20
        pora = pora_kwitnienia(P.POZYTKI[nazwa][2])
        pory[nazwa] = pora
        sur[nazwa] = fftconvolve(udzial, jadra_raw[pora], mode="same").astype("float32")
        nor[nazwa] = fftconvolve(udzial, jadra_norm[pora], mode="same").astype("float32")
        print(f"  {nazwa[:26]:28s} {pora:8s} {udzial.sum():9,.0f} ha")
        del udzial

    def zloz(d):
        out = np.zeros((ny, nx), "float64")
        for n, mm in d.items():
            out += mm * P.POZYTKI[n][0]
        return out

    A, B = zloz(sur), zloz(nor)
    maska = (A > 0) & (B > 0)
    rA, rB = np.corrcoef(A[maska], B[maska])[0, 1], None
    tA, tB = top_procent(A, maska), top_procent(B, maska)
    wsp = (tA & tB).sum() / tA.sum() * 100

    print("\n" + "=" * 62)
    print("POROWNANIE: JADRO SUROWE vs ZNORMALIZOWANE")
    print("=" * 62)
    print(f"  korelacja map            {rA:.3f}")
    print(f"  wspolne top-10% miejsc   {wsp:.0f}%")

    print(f"\n{'pora':10s}{'udzial surowe':>16}{'udzial norm.':>15}{'zmiana':>11}")
    ud = {}
    for pora in JADRA_SEZONOWE:
        a = sum(sur[n].sum() * P.POZYTKI[n][0] for n in sur if pory[n] == pora)
        bb = sum(nor[n].sum() * P.POZYTKI[n][0] for n in nor if pory[n] == pora)
        ua, ub = a / A.sum() * 100, bb / B.sum() * 100
        ud[pora] = {"surowe_proc": ua, "znorm_proc": ub}
        print(f"{pora:10s}{ua:>15.1f}%{ub:>14.1f}%{ub - ua:>+10.1f} pkt")

    print(f"\n{'gatunek':24s}{'pora':9s}{'surowe':>9}{'norm.':>9}{'zmiana':>10}")
    gat = {}
    for n in sorted(sur, key=lambda x: -nor[x].sum() * P.POZYTKI[x][0]):
        ua = sur[n].sum() * P.POZYTKI[n][0] / A.sum() * 100
        ub = nor[n].sum() * P.POZYTKI[n][0] / B.sum() * 100
        gat[n] = {"surowe_proc": ua, "znorm_proc": ub, "pora": pory[n]}
        if max(ua, ub) >= 1.0:
            print(f"{n[:22]:24s}{pory[n]:9s}{ua:>8.1f}%{ub:>8.1f}%{ub - ua:>+9.1f} pkt")

    print("\nWNIOSEK")
    if rA >= 0.95 and wsp >= 90:
        print("  Mapy sa zbiezne - wybor wariantu nie zmienia rankingu miejsc.")
        print("  Spor jest akademicki, wystarczy zadeklarowac interpretacje.")
    else:
        print("  Mapy SIE ROZJEZDZAJA - wybor wariantu realnie przestawia")
        print("  ranking. Trzeba go dokonac swiadomie i uzasadnic, a nie")
        print("  odziedziczyc po przypadkowej geometrii jadra.")

    (WYNIKI / "json" / "wrazliwosc_jadra.json").write_text(json.dumps({
        "cel": "pomiar wplywu normalizacji jadra sezonowego na mape",
        "sumy_jader": {p: float(K.sum()) for p, K in jadra_raw.items()},
        "korelacja": float(rA),
        "top10_wspolne_proc": float(wsp),
        "udzial_por": ud,
        "udzial_gatunkow": gat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/wrazliwosc_jadra.json")
