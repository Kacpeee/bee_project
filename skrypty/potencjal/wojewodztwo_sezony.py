"""
ETAP 7 - potencjal pozytkowy na DWOCH sezonach deklaracji: 2025 i 2026.

DLACZEGO TYLKO DWA
ARiMR otworzyl dane przestrzenne w grudniu 2025 i publikuje wylacznie
roczniki 2025 i 2026. Wczesniejszych deklaracji nie ma i nie bedzie - to jest
twardy limit zrodla, nie nasza decyzja.

PO CO DRUGI SEZON
Mapa z jednego roku moze byc przypadkiem: rzepak chodzi w plodozmianie, wiec
konkretne pola zmieniaja sie co roku. Pytanie brzmi, czy po rozmyciu jadrem
zasiegu lotu (3 km) REJONY zostaja te same. Jesli tak - mapa z jednego roku
jest reprezentatywna i mozna jej uzywac na przyszlosc. Jesli nie - trzeba
uczciwie napisac, ze mapa jest wazna jeden sezon.

Wszystko liczone na siatce woj_sezon.tif, wiec piksel odpowiada pikselowi.

WYNIK
  woj_sezon_2026.tif    - potencjal sezonowy wg deklaracji 2026
  woj_sezon_srednia.tif - srednia obu sezonow (nowa warstwa glowna)
  wyniki/sezony_porownanie.json

Uruchomienie:
    python wojewodztwo_sezony.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import pyogrio
import rasterio
from matplotlib.path import Path as MplPath
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.signal import fftconvolve
from shapely.geometry import MultiLineString
from shapely.ops import polygonize, unary_union

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import mapa_wojewodztwa as MW
import potencjal_gsa as P
import wojewodztwo as W

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PIKSEL, PIKSEL_R = 100, 20

SHP = {
    2025: ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp",
    2026: None,   # znajdowany globem - nazwa pliku w paczce nieznana z gory
}


def znajdz_shp_2026() -> Path:
    kand = sorted((ROOT / "dane" / "gsa_lubelskie_2026").glob("*.shp"))
    if not kand:
        raise SystemExit("brak shapefile 2026 - pobieranie jeszcze trwa?")
    return kand[0]


def kolumna_rosliny(shp: Path) -> str:
    pola = pyogrio.read_info(shp)["fields"]
    for f in pola:
        if "rosl" in f.lower():
            return f
    raise SystemExit(f"brak kolumny z roslina; pola: {list(pola)}")


def splot_roku(rok: int, shp: Path, l, t, nx, ny, K) -> dict[str, np.ndarray]:
    cache = WYNIKI / "cache" / f"woj_splot_{rok}.npz"
    if cache.exists():
        z = np.load(cache)
        print(f"  splot {rok} z cache ({len(z.files)} klas)")
        return {k: z[k] for k in z.files}
    kol = kolumna_rosliny(shp)
    kro = PIKSEL // PIKSEL_R
    wynik, _jadra = {}, {}
    print(f"  rasteryzacja {rok} (kolumna '{kol}'):")
    for nazwa in P.POZYTKI:
        # "TUZ odrost" to drugi pokos tej samej laki, nie osobna uprawa -
        # w deklaracjach nie istnieje, wiec musi brac geometrie uprawy
        # zrodlowej. Bez tego rasteryzacja zwracala 0 ha i drugi pokos
        # (9.4% cukrow) znikal z sezonu 2026 bez zadnego ostrzezenia.
        g = pyogrio.read_dataframe(
            shp, encoding="utf-8",
            where=f"{kol} = '{P.uprawa_zrodlowa(nazwa)}'")
        if g.empty:
            print(f"    {nazwa[:26]:28s} BRAK w {rok}")
            continue
        r20 = rasterize(((geom, 1) for geom in g.geometry),
                        out_shape=(ny * kro, nx * kro),
                        transform=from_origin(l, t, PIKSEL_R, PIKSEL_R),
                        fill=0, dtype="uint8")
        udzial = r20.reshape(ny, kro, nx, kro).mean(axis=(1, 3))
        del r20
        # jadro SEZONOWE i ZNORMALIZOWANE, tak jak w wojewodztwo.py.
        # Wczesniej bylo tu jedno stale K, wiec ten skrypt liczyl mape
        # inna metoda niz glowny - i sezony 2025/2026 nie byly porownywalne
        # z mapa wojewodztwa.
        wynik[nazwa] = fftconvolve(udzial, W.jadro_dla(nazwa, _jadra),
                                   mode="same").astype("float32")
        print(f"    {nazwa[:26]:28s} {udzial.sum():9,.0f} ha")
        del udzial
    np.savez_compressed(cache, **wynik)
    return wynik


if __name__ == "__main__":
    with rasterio.open(WYNIKI / "rastry" / "woj_sezon.tif") as f:
        b, (ny, nx), tf = f.bounds, f.shape, f.transform
    l, t = b.left, b.top
    K = W.jadro()
    SHP[2026] = znajdz_shp_2026()

    # maska wojewodztwa + margines splotu
    drogi, miasta, granice = MW.podklad()
    poly = max(polygonize(unary_union(MultiLineString(
        [g for g in granice if len(g) > 1]))), key=lambda q: q.area)
    yy, xx = np.mgrid[0:ny, 0:nx]
    maska = MplPath(np.array(poly.exterior.coords)).contains_points(
        np.column_stack([l + (xx.ravel() + .5) * PIKSEL,
                         t - (yy.ravel() + .5) * PIKSEL])).reshape(ny, nx)
    marg = int(W.ZASIEG_M / PIKSEL)
    maska[:marg] = maska[-marg:] = False
    maska[:, :marg] = maska[:, -marg:] = False

    # stary cache 2025 pod nowa nazwa - to ten sam wynik
    stary = WYNIKI / "cache" / "woj_splot.npz"
    nowy = WYNIKI / "cache" / "woj_splot_2025.npz"
    if stary.exists() and not nowy.exists():
        stary.rename(nowy)

    sezon, areal = {}, {}
    for rok in (2025, 2026):
        print(f"\nSEZON {rok}")
        spl = splot_roku(rok, SHP[rok], l, t, nx, ny, K)
        s = np.zeros((ny, nx), "float32")
        for nazwa, mm in spl.items():
            # straznik kompletnosci - patrz wojewodztwo.py
            if nazwa not in P.POZYTKI:  # cache moze miec uprawy wykluczone
                continue
            s += mm * P.POZYTKI[nazwa][0]
            # ha z sumy splotu: splot to udzial x jadro, wiec ha odzyskujemy
            # dopiero z rasteryzacji - tu wystarczy suma udzialow przed splotem,
            # ale jej nie cachujemy; przyblizamy przez odwrocenie sumy jadra
            areal.setdefault(rok, {})[nazwa] = float(mm.sum() / K.sum())
        sezon[rok] = np.where(maska, s, np.nan)
        del spl

    prof = {"driver": "GTiff", "height": ny, "width": nx, "count": 1,
            "dtype": "float32", "crs": "EPSG:2180", "transform": tf,
            "compress": "deflate", "nodata": np.nan}
    srednia = (sezon[2025] + sezon[2026]) / 2
    for nazwa, arr in (("woj_sezon_2026", sezon[2026]),
                       ("woj_sezon_srednia", srednia)):
        with rasterio.open(WYNIKI / "rastry" / f"{nazwa}.tif", "w", **prof) as dst:
            dst.write(arr.astype("float32"), 1)

    # ------------------------------------------------ porownanie
    ok = ~np.isnan(sezon[2025]) & ~np.isnan(sezon[2026])
    a, c = sezon[2025][ok] / 1000, sezon[2026][ok] / 1000
    r = float(np.corrcoef(a, c)[0, 1])
    # czy najlepsze rejony zostaja najlepsze: top 10% w 2025 vs top 10% w 2026
    p90a, p90c = np.percentile(a, 90), np.percentile(c, 90)
    top_zgoda = float(((a >= p90a) & (c >= p90c)).sum() / max((a >= p90a).sum(), 1))

    print(f"\nPOROWNANIE SEZONOW (n = {ok.sum():,} px)")
    print(f"  korelacja map:            r = {r:.3f}")
    print(f"  mediana 2025 / 2026:      {np.median(a):.1f} / {np.median(c):.1f} t")
    print(f"  top-10% z 2025 nadal w top-10% w 2026: {top_zgoda*100:.0f}%")
    print(f"\n{'gatunek':>26}{'2025 ha':>12}{'2026 ha':>12}{'zmiana':>9}")
    zmiany = {}
    for nazwa in P.POZYTKI:
        h25 = areal.get(2025, {}).get(nazwa, 0)
        h26 = areal.get(2026, {}).get(nazwa, 0)
        if max(h25, h26) < 500:
            continue
        zm = (h26 / h25 - 1) * 100 if h25 else float("nan")
        zmiany[nazwa] = {"ha_2025": h25, "ha_2026": h26, "zmiana_pct": zm}
        print(f"{nazwa[:25]:>26}{h25:>12,.0f}{h26:>12,.0f}{zm:>+8.0f}%")

    (WYNIKI / "json" / "sezony_porownanie.json").write_text(json.dumps({
        "korelacja": r, "top10_zgoda": top_zgoda,
        "mediana_t": {"2025": float(np.median(a)), "2026": float(np.median(c))},
        "gatunki": zmiany,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano woj_sezon_2026.tif, woj_sezon_srednia.tif i JSON")
