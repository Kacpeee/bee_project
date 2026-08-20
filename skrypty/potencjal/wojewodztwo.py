"""
Model dla calego wojewodztwa lubelskiego zamiast jednego bufora 10 km.

CO SIE SKALUJE, A CO TRZEBA BYLO PRZEROBIC

Skaluje sie samo: mapa potencjalu i kalendarz licza sie lokalnie w numpy,
a shapefile GSA obejmuje cale wojewodztwo. Model fenologiczny tez - pokazalismy
na siedmiu obszarach, ze jeden prog cieplny opisuje 115 km, wiec da sie go
zastosowac na siatce.

Trzeba bylo przerobic:
  - meteo z JEDNEGO punktu na siatke ok. 25 km, bo wojewodztwo ma 230 km
    z polnocy na poludnie i termin kwitnienia rozni sie w nim istotnie
  - rasteryzacje na kafelki, bo przy 20 m cale wojewodztwo to setki milionow
    pikseli na klase

CZEGO TU NIE MA
Modulacji pogodowej - warstwa lotnosci jest policzona dla punktu i jej
rozciagniecie na wojewodztwo wymagaloby osobnej siatki godzinowej. Mapa
sezonowa jest od dat niezalezna (to suma po calym sezonie), wiec pozostaje
scisla; kalendarz dekadowy dla wojewodztwa bylby juz przyblizeniem.

ZASTRZEZENIE, KTORE ROSNIE ZE SKALA
Tablica wydajnosci byla sprawdzana pod katem Hrubieszowszczyzny. Siedemnascie
klas uznalem za nieistotne, bo dawaly tam 1.2% - ale gryka, sady czy slonecznik
moga gdzie indziej dominowac, a maja u mnie klase B albo C. Fasola
wielokwiatowa to w ogole specjalnosc jednego powiatu.

Uruchomienie:
    python wojewodztwo.py
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import numpy as np
import pandas as pd
import pyogrio
import rasterio
import requests
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.signal import fftconvolve

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir() if p.is_dir()]   # moduly projektu z katalogow obok

import potencjal_gsa as P

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

PIKSEL = 100
PIKSEL_RASTER = 20
LAMBDA_M, ZASIEG_M = 1000, 3000
ROK = 2025
KROK_METEO_M = 25_000

CACHE_METEO = WYNIKI / "cache" / "woj_meteo_siatka.csv"
CACHE_SPLOT = WYNIKI / "cache" / "woj_splot_2025.npz"   # przemianowany w etapie sezonow


def siatka_meteo(bounds) -> pd.DataFrame:
    """Punkty co ~25 km; Open-Meteo przyjmuje wiele lokalizacji w jednym
    zapytaniu, wiec calosc idzie kilkoma zapytaniami zamiast czterdziestoma."""
    if CACHE_METEO.exists():
        return pd.read_csv(CACHE_METEO, parse_dates=["data"])
    l, b, r, t = bounds
    xs = np.arange(l + KROK_METEO_M / 2, r, KROK_METEO_M)
    ys = np.arange(b + KROK_METEO_M / 2, t, KROK_METEO_M)
    do4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    pkt = [(x, y) + do4326.transform(x, y) for x in xs for y in ys]
    print(f"  punktow meteo: {len(pkt)}")

    czesci = []
    for i in range(0, len(pkt), 25):
        blok = pkt[i:i + 25]
        rr = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": ",".join(f"{p[3]:.4f}" for p in blok),
            "longitude": ",".join(f"{p[2]:.4f}" for p in blok),
            "start_date": f"{ROK}-01-01", "end_date": f"{ROK}-08-01",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Warsaw"}, timeout=300)
        rr.raise_for_status()
        odp = rr.json()
        odp = odp if isinstance(odp, list) else [odp]
        for p_, o in zip(blok, odp):
            d = o["daily"]
            czesci.append(pd.DataFrame({
                "data": pd.to_datetime(d["time"]),
                "Tmax": d["temperature_2m_max"], "Tmin": d["temperature_2m_min"],
                "x": p_[0], "y": p_[1]}))
        print(f"    pobrano {min(i+25, len(pkt))}/{len(pkt)}")
    df = pd.concat(czesci, ignore_index=True)
    df.to_csv(CACHE_METEO, index=False)
    return df


def kwitnienie(df: pd.DataFrame, baza: float, d0: int, prog: float) -> pd.DataFrame:
    """DOY pelni kwitnienia rzepaku w kazdym punkcie siatki."""
    out = []
    for (x, y), s in df.groupby(["x", "y"]):
        s = s.sort_values("data")
        doy = s["data"].dt.dayofyear.to_numpy()
        gdd = np.maximum((s["Tmax"].to_numpy() + s["Tmin"].to_numpy()) / 2 - baza, 0)
        gdd[doy < d0] = 0
        i = np.searchsorted(np.cumsum(gdd), prog)
        out.append({"x": x, "y": y, "doy": int(doy[i]) if i < len(doy) else np.nan})
    return pd.DataFrame(out)


def jadro(lam: float = LAMBDA_M, zasieg: float = ZASIEG_M) -> np.ndarray:
    r = int(zasieg // PIKSEL)
    i = np.arange(-r, r + 1)
    dx, dy = np.meshgrid(i, i)
    o = np.hypot(dx, dy) * PIKSEL
    return np.where(o <= zasieg, np.exp(-o / lam), 0.0)


# Jadra SEZONOWE - zmierzone dystanty lotu roznia sie czterokrotnie miedzy
# wiosna a latem (Couvillon i in. 2014: 493 m / 2156 m / 1275 m). Jedno stale
# jadro rozmywalo rzepak trzykrotnie za szeroko, a pozytki letnie obcinalo
# prawie o polowe. Parametry policzone w jadro_sezonowe.py.
JADRA_SEZONOWE = {
    "wiosna": (294.0, 1178.0),
    "lato":   (1285.0, 5142.0),
    "jesien": (760.0, 3041.0),
}


def pora_kwitnienia(doy: float) -> str:
    """Pora wg daty pelni kwitnienia gatunku."""
    if doy < 152:
        return "wiosna"
    return "lato" if doy < 244 else "jesien"


# NORMALIZACJA JADER - poprawka po pomiarze z etapu 29.
#
# Jadra sezonowe roznia sie suma az 19-krotnie (wiosna 50, lato 943, jesien
# 330), bo szersze jadro obejmuje wiecej pikseli. Splot nieznormalizowany
# przenosil te roznice wprost do wyniku: hektar pozytku letniego wchodzil
# do sumy 19 razy mocniej niz hektar wiosennego - z geometrii, nie z biologii.
#
# Skutek byl absurdalny i mierzalny: rzepak (150 626 ha, najwieksza pozycja
# bilansu, 50.9% cukrow wojewodztwa) dawal na mapie 8.8%, a gryka - majaca
# JEDENASCIE RAZY mniej powierzchni - dawala 23.5%.
#
# Rzecz jest tym bardziej odwrotna, ze pszczoly lataja latem dalej WLASNIE
# DLATEGO, ZE KWIATOW JEST MNIEJ (to wniosek Couvillon i in. 2014). Surowe
# jadro premiowalo wiec niedobor: im rzadszy pozytek, tym szersze jadro,
# tym wyzszy wynik.
#
# Po normalizacji do sumy 1 splot mierzy GESTOSC pozytku wazona dostepnoscia.
# Udzialy gatunkow odtwarzaja wtedy bilans z hektarow i wydajnosci co do
# dziesiatej czesci punktu (rzepak 51.0 vs 50.9, TUZ 12.0 vs 12.0, malina
# 7.3 vs 7.3) - czyli splot zachowuje cukier, zamiast liczyc geometrie.
# Zmierzony dystans lotu nadal steruje SZEROKOSCIA rozmycia; traci tylko
# nieuzasadniona premie za sama szerokosc.
#
# SKALA BEZWZGLEDNA: po normalizacji mnozymy przez stala sume jadra
# odniesienia (lambda 1000 m, zasieg 3000 m - jadro uzywane w calym projekcie
# przed etapem 27). Dzieki temu jednostki i rzedy wielkosci pozostaja zgodne
# z wczesniejszymi etapami, w tym ze sprawdzianem GUS, a jednoczesnie zadna
# pora nie dostaje premii za szerokosc.
SUMA_ODNIESIENIA = jadro(1000.0, 3000.0).sum()   # ~502.89


def jadro_dla(nazwa: str, jadra: dict | None = None) -> np.ndarray:
    """Znormalizowane jadro pasujace do pory kwitnienia gatunku."""
    import potencjal_gsa as _P
    p0 = _P.POZYTKI[nazwa][2]
    pora = pora_kwitnienia(p0)
    if jadra is not None and pora in jadra:
        return jadra[pora]
    K = jadro(*JADRA_SEZONOWE[pora])
    K = K / K.sum() * SUMA_ODNIESIENIA
    if jadra is not None:
        jadra[pora] = K
    return K


if __name__ == "__main__":
    info = pyogrio.read_info(SHP)
    l, b, r, t = info["total_bounds"]
    l, b = np.floor(l / PIKSEL) * PIKSEL, np.floor(b / PIKSEL) * PIKSEL
    r, t = np.ceil(r / PIKSEL) * PIKSEL, np.ceil(t / PIKSEL) * PIKSEL
    nx, ny = int((r - l) / PIKSEL), int((t - b) / PIKSEL)
    print(f"WOJEWODZTWO LUBELSKIE")
    print(f"  zasieg {(r-l)/1000:.0f} x {(t-b)/1000:.0f} km, siatka {nx} x {ny} px")
    print(f"  dzialek w pliku: {info['features']:,}\n")

    tf = from_origin(l, t, PIKSEL, PIKSEL)

    # ---------------------------------------------------------- meteo i kwitnienie
    print("Meteo na siatce...")
    dfm = siatka_meteo((l, b, r, t))
    fin = json.loads((WYNIKI / "json" / "fenologia_final.json").read_text(encoding="utf-8"))
    m = fin["model"]
    d0 = m.get("start_doy", {"1I": 1, "1II": 32}.get(m["start"], 32))
    kw = kwitnienie(dfm, m["baza"], d0, m["prog"])
    print(f"  termin kwitnienia {ROK}: {kw['doy'].min():.0f} - {kw['doy'].max():.0f} DOY "
          f"(rozrzut {kw['doy'].max()-kw['doy'].min():.0f} dni w wojewodztwie)")

    # ---------------------------------------------------------- splot na klase
    if CACHE_SPLOT.exists():
        with np.load(CACHE_SPLOT) as z:
            splot = {k: z[k] for k in z.files}
        print(f"\nsplot wczytany z cache ({len(splot)} klas)")
        # STRAZNIK KOMPLETNOSCI CACHE.
        # Petla sumujaca warstwy (nizej) idzie po CACHE, nie po POZYTKI - wiec
        # uprawa dodana do POZYTKI po zapisaniu cache NIE trafialaby do mapy,
        # a suma policzylaby sie bez bledu i bez ostrzezenia. Tak wlasnie
        # zniknal drugi pokos TUZ (9.4% cukrow) po rozbiciu laki na dwa
        # kwitnienia. Blad byl niewidoczny, bo mapa nadal wygladala sensownie.
        brak = [n for n in P.POZYTKI if n not in splot]
        if brak:
            raise SystemExit(
                f"\nCACHE NIEAKTUALNY - brak klas: {', '.join(brak)}\n"
                f"Usun {CACHE_SPLOT.name} i uruchom ponownie, zeby przeliczyc "
                "sploty od nowa.\nInaczej mapa po cichu pominelaby te klasy.")
    else:
        print("\nRasteryzacja i splot na klase (calosc wojewodztwa):")
        splot, kro, _jadra = {}, PIKSEL // PIKSEL_RASTER, {}
        for nazwa in P.POZYTKI:
            # "TUZ odrost" to druga faza kwitnienia tej samej powierzchni,
            # nie osobna uprawa - bierze geometrie uprawy zrodlowej
            g = pyogrio.read_dataframe(
                SHP, encoding="utf-8",
                where=f"roslina = '{P.uprawa_zrodlowa(nazwa)}'")
            if g.empty:
                continue
            r20 = rasterize(((geom, 1) for geom in g.geometry),
                            out_shape=(ny * kro, nx * kro),
                            transform=from_origin(l, t, PIKSEL_RASTER,
                                                  PIKSEL_RASTER),
                            fill=0, dtype="uint8")
            udzial = r20.reshape(ny, kro, nx, kro).mean(axis=(1, 3))
            del r20
            Kg = jadro_dla(nazwa, _jadra)
            splot[nazwa] = fftconvolve(udzial, Kg, mode="same").astype("float32")
            print(f"  {nazwa[:26]:28s} {udzial.sum():9,.0f} ha  "
                  f"maks {splot[nazwa].max():7.1f}")
            del udzial
        np.savez_compressed(CACHE_SPLOT, **splot)
        print(f"  zapisano cache: {CACHE_SPLOT.name}")

    # ---------------------------------------------------------- warstwy
    # Petla idzie po CACHE, nie po POZYTKI - i to jest pulapka: uprawa
    # dodana do POZYTKI po zapisaniu cache nie trafilaby do mapy, a suma
    # policzylaby sie bez bledu i bez ostrzezenia. Dlatego kompletnosc
    # cache jest sprawdzana straznikiem przy wczytywaniu (wyzej).
    sezon = np.zeros((ny, nx), "float32")
    for nazwa, mm in splot.items():
        if nazwa not in P.POZYTKI:      # cache moze miec uprawy wykluczone
            continue
        sezon += mm * P.POZYTKI[nazwa][0]
    rzep = splot.get("rzepak ozimy", 0) * P.POZYTKI["rzepak ozimy"][0]

    # maska: tylko tam, gdzie splot mial pelne otoczenie (3 km od brzegu danych)
    marg = int(ZASIEG_M / PIKSEL)
    waz = np.zeros((ny, nx), bool)
    waz[marg:-marg, marg:-marg] = True

    prof = {"driver": "GTiff", "height": ny, "width": nx, "count": 1,
            "dtype": "float32", "crs": "EPSG:2180", "transform": tf,
            "compress": "deflate", "nodata": np.nan}
    for nazwa, mm in (("woj_sezon", sezon), ("woj_rzepak", rzep)):
        with rasterio.open(WYNIKI / "rastry" / f"{nazwa}.tif", "w", **prof) as dst:
            dst.write(np.where(waz, mm, np.nan).astype("float32"), 1)

    # mapa terminu kwitnienia - interpolacja z siatki meteo na raster
    from scipy.interpolate import griddata
    yy, xx = np.mgrid[0:ny, 0:nx]
    px = l + (xx + .5) * PIKSEL
    py = t - (yy + .5) * PIKSEL
    doy_map = griddata(kw[["x", "y"]].to_numpy(), kw["doy"].to_numpy(),
                       (px, py), method="linear")
    with rasterio.open(WYNIKI / "rastry" / "woj_kwitnienie.tif", "w", **prof) as dst:
        dst.write(doy_map.astype("float32"), 1)

    v = sezon[waz]
    print(f"\nPOTENCJAL SEZONOWY W WOJEWODZTWIE (t cukrow w zasiegu lotu)")
    for q in (50, 90, 99, 100):
        print(f"  percentyl {q:3d}: {np.percentile(v, q)/1000:6.1f} t")

    # gdzie wypada obszar pilotazowy
    tr = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    hx, hy = tr.transform(P.STACJA_LON, P.STACJA_LAT)
    j, i = int((hx - l) / PIKSEL), int((t - hy) / PIKSEL)
    wart = sezon[i, j]
    print(f"\n  obszar pilotazowy (Hrubieszow): {wart/1000:.1f} t")
    print(f"  to percentyl {100*(v < wart).mean():.1f} wojewodztwa")

    (WYNIKI / "json" / "wojewodztwo.json").write_text(json.dumps({
        "zasieg_km": [round((r-l)/1000), round((t-b)/1000)],
        "siatka": [nx, ny], "piksel_m": PIKSEL, "rok": ROK,
        "kwitnienie_doy": {"min": int(kw["doy"].min()), "max": int(kw["doy"].max())},
        "percentyle_t": {str(q): float(np.percentile(v, q)/1000)
                         for q in (10, 25, 50, 75, 90, 99, 100)},
        "pilotazowy": {"wartosc_t": float(wart/1000),
                       "percentyl": float(100*(v < wart).mean())},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nZapisano woj_*.tif i wojewodztwo.json")
