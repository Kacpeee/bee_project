"""
ETAP 34 - czy KSZTALT jadra ma znaczenie.

ZASTRZEZENIE
Dystanse lotu sa udokumentowane (Couvillon i in. 2014), ale POSTAC funkcji
spadku - exp(-d/lambda) - zostala wybrana konwencjonalnie, bez zrodla.
Kalibracja lambda dopasowuje tylko SREDNIA, a te sama srednia da sie
osiagnac wieloma roznymi krzywymi.

METODA
Trzy ksztalty, kazdy skalibrowany do TEJ SAMEJ zmierzonej sredniej (493 m
wiosna itd.) i znormalizowany do tej samej masy. Porownanie map.

Uruchomienie:
    python skrypty/potencjal/wrazliwosc_ksztaltu.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import potencjal_gsa as P
from wojewodztwo import SUMA_ODNIESIENIA, JADRA_SEZONOWE, pora_kwitnienia
from jadro_sezonowe import DYSTANS

WYNIKI = ROOT / "wyniki"
PIKSEL = 100

def siatka(R):
    r = int(R // PIKSEL)
    i = np.arange(-r, r + 1)
    dx, dy = np.meshgrid(i, i)
    return np.hypot(dx, dy) * PIKSEL

KSZTALTY = {
    "wykladniczy": lambda d, p: np.exp(-d / p),
    "gaussowski":  lambda d, p: np.exp(-(d ** 2) / (2 * p ** 2)),
    "liniowy":     lambda d, p: np.maximum(1 - d / p, 0),
}

def zbuduj(ksztalt, p, R):
    d = siatka(R)
    K = np.where(d <= R, KSZTALTY[ksztalt](d, p), 0.0)
    return K, d

def srednia(K, d):
    return float((d * K).sum() / K.sum())

def dobierz(ksztalt, cel, R):
    lo, hi = 5.0, R * 3
    for _ in range(60):
        s = (lo + hi) / 2
        K, d = zbuduj(ksztalt, s, R)
        if K.sum() <= 0 or srednia(K, d) < cel:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2

if __name__ == "__main__":
    from scipy.signal import fftconvolve
    import pyogrio, os
    os.environ.setdefault("PROJ_DATA", str(Path(__import__("rasterio").__file__).parent / "proj_data"))
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

    print("KALIBRACJA KSZTALTOW DO TEJ SAMEJ ZMIERZONEJ SREDNIEJ\n")
    jadra = {}
    for ks in KSZTALTY:
        jadra[ks] = {}
        for pora, cel in DYSTANS.items():
            R = JADRA_SEZONOWE[pora][1]
            p = dobierz(ks, cel, R)
            K, d = zbuduj(ks, p, R)
            K = K / K.sum() * SUMA_ODNIESIENIA
            jadra[ks][pora] = K
            print(f"  {ks:13s} {pora:8s} param {p:7.0f}  srednia "
                  f"{srednia(K, d):6.0f} m (cel {cel:.0f})")

    info = pyogrio.read_info(SHP); l, b, r, t = info["total_bounds"]
    l, b = np.floor(l/PIKSEL)*PIKSEL, np.floor(b/PIKSEL)*PIKSEL
    r, t = np.ceil(r/PIKSEL)*PIKSEL, np.ceil(t/PIKSEL)*PIKSEL
    nx, ny = int((r-l)/PIKSEL), int((t-b)/PIKSEL); kro = 5

    print("\nrasteryzacja i splot trzema ksztaltami...", flush=True)
    mapy = {k: np.zeros((ny, nx), "float64") for k in KSZTALTY}
    for nazwa in P.POZYTKI:
        g = pyogrio.read_dataframe(SHP, encoding="utf-8",
                                   where=f"roslina = '{P.uprawa_zrodlowa(nazwa)}'")
        if g.empty: continue
        r20 = rasterize(((q, 1) for q in g.geometry), out_shape=(ny*kro, nx*kro),
                        transform=from_origin(l, t, 20, 20), fill=0, dtype="uint8")
        u = r20.reshape(ny, kro, nx, kro).mean(axis=(1, 3)); del r20
        pora = pora_kwitnienia(P.POZYTKI[nazwa][2])
        for ks in KSZTALTY:
            mapy[ks] += fftconvolve(u, jadra[ks][pora], mode="same") * P.POZYTKI[nazwa][0]
        del u
    print("gotowe\n")

    baza = mapy["wykladniczy"]; maska = baza > 0
    prog = np.percentile(baza[maska], 90); top0 = maska & (baza >= prog)
    print(f"{'ksztalt':15s}{'korelacja':>12}{'top-10% wspolne':>18}")
    wyn = {}
    for ks, m in mapy.items():
        rr = float(np.corrcoef(baza[maska], m[maska])[0, 1])
        tp = maska & (m >= np.percentile(m[maska], 90))
        w = float((tp & top0).sum() / top0.sum() * 100)
        wyn[ks] = {"korelacja": rr, "top10_wspolne_proc": w}
        print(f"{ks:15s}{rr:>12.3f}{w:>17.0f}%")

    naj = min(wyn.values(), key=lambda x: x["korelacja"])
    print(f"\nNAJGORSZY PRZYPADEK: r = {naj['korelacja']:.3f}, "
          f"top-10% {naj['top10_wspolne_proc']:.0f}%")
    (WYNIKI / "json" / "wrazliwosc_ksztaltu.json").write_text(json.dumps({
        "pytanie": "czy postac funkcji spadku (nieudokumentowana) zmienia mape",
        "metoda": "trzy ksztalty skalibrowane do tej samej zmierzonej sredniej "
                  "i znormalizowane do tej samej masy",
        "wyniki": wyn}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano json/wrazliwosc_ksztaltu.json")
