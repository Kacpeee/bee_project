"""
Mapy do raportu: gdzie jest rzepak (lewy panel) i gdzie postawic ul (prawy).

DLACZEGO DWA PANELE, A NIE JEDNA MAPA Z OBRYSAMI
Poprzednia wersja rysowala dzialki na heatmapie. Nie dzialalo to z dwoch
powodow. Po pierwsze przy szerokosci 20 km dzialka 1-hektarowa ma ulamek
milimetra - obrysy byly faktura udajaca informacje, nie do odczytania. Po drugie
mieszaly komunikat: heatmapa mowi, gdzie STOISZ, a dzialki gdzie jest POLE.
Rozdzielone, kazdy panel odpowiada na jedno pytanie.

DLACZEGO KLASY, A NIE CIAGLA RAMPA
Powierzchnia po splocie z jadrem 3 km jest z natury gladka, wiec ciagla rampa
daje jednolity dysk, z ktorego nie da sie odczytac decyzji. Klasy kwantylowe
mowia wprost: to jest najlepsze 20% bufora.

DLACZEGO CZERWIEN
Jeden odcien, jasny -> ciemny, z najlepszymi wartosciami na ciemnym koncu.
Nosnikiem informacji jest jasnosc, wiec czyta sie takze przy zaburzeniach
widzenia barw.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path

os.environ.setdefault(
    "PROJ_DATA",
    str(Path(__import__("rasterio").__file__).parent / "proj_data"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyogrio
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
SHP = ROOT / "dane" / "gsa_lubelskie_2025" / "2025_uprawy_woj_06_akt_public.shp"

KLASY_KOLOR = ["#fee0d2", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]
KLASY_OPIS = ["najsłabsze 20%", "20–40%", "40–60%", "60–80%", "najlepsze 20%"]
POLE = "#4a5a50"
TLO = "#fcfcfb"
ATRAMENT = "#141b16"
MUTED = "#6b756e"

NAZWY = {"caly sezon": "cały sezon", "sam rzepak": "sam rzepak",
         "po rzepaku": "po rzepaku"}


def _podzialka(ax, x0, y0, dl=5000):
    ax.add_patch(Rectangle((x0, y0), dl, 240, facecolor=ATRAMENT,
                           edgecolor="none", zorder=8))
    ax.add_patch(Rectangle((x0, y0), dl / 2, 240, facecolor="#ffffff",
                           edgecolor=ATRAMENT, linewidth=.5, zorder=9))
    ax.text(x0 + dl / 2, y0 + 620, f"{dl // 1000} km", ha="center", va="bottom",
            fontsize=8, color=ATRAMENT, zorder=9)


def _ramka(ax, sx, sy, r):
    ax.set_xlim(sx - r, sx + r)
    ax.set_ylim(sy - r, sy + r)
    ax.set_xticks([])
    ax.set_yticks([])
    for k in ax.spines.values():
        k.set_visible(False)


def para(tif: Path, pot: dict, tytul_prawy: str, jednostka: str,
         punkty: dict | None = None) -> tuple[str, list[float]]:
    """Dwa panele: rozmieszczenie rzepaku i klasy potencjalu."""
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]

    with rasterio.open(tif) as s:
        a = s.read(1)
        b = s.bounds
    from pyproj import Transformer
    tx = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    sx, sy = tx.transform(pot["stacja"]["lon"], pot["stacja"]["lat"])
    pr = pot["stacja"]["promien_m"]
    r = pr + 2200

    dane = a / 1000.0
    v = dane[~np.isnan(dane)]
    progi = [float(np.percentile(v, q)) for q in (0, 20, 40, 60, 80, 100)]
    cmap = ListedColormap(KLASY_KOLOR)
    norm = BoundaryNorm(progi, cmap.N)

    fig, (axL, axP) = plt.subplots(1, 2, figsize=(12.6, 6.9), dpi=175)
    fig.patch.set_facecolor(TLO)

    # ---------------------------------------------------------- lewy: rzepak
    axL.set_facecolor(TLO)
    rz = pyogrio.read_dataframe(SHP, bbox=(b.left, b.bottom, b.right, b.top),
                                encoding="utf-8")
    rz = rz[rz["roslina"] == "rzepak ozimy"]
    c = rz.geometry.centroid
    odl = np.hypot(c.x - sx, c.y - sy)
    rz[odl > pr].plot(ax=axL, color="#d5dad6", edgecolor="none", zorder=1)
    rz[odl <= pr].plot(ax=axL, color=POLE, edgecolor="none", zorder=2)
    axL.add_patch(plt.Circle((sx, sy), pr, fill=False, lw=1.1,
                             edgecolor=ATRAMENT, alpha=.45, zorder=3))
    _podzialka(axL, sx - r + 1000, sy - r + 1000)
    _ramka(axL, sx, sy, r)
    axL.set_title("Gdzie jest rzepak", fontsize=13, weight="bold",
                  color=ATRAMENT, loc="left", pad=8)
    # legendy pod panelami, nie na mapie - w rogu przykrywaly punkt "po rzepaku"
    fig.legend(handles=[Patch(facecolor=POLE, label="rzepak ozimy, ARiMR GSA 2025"),
                        Patch(facecolor="#d5dad6", label="poza buforem 10 km")],
               loc="upper left", bbox_to_anchor=(0.015, 0.115), ncol=2,
               fontsize=9, frameon=False)

    # ---------------------------------------------------------- prawy: klasy
    axP.set_facecolor(TLO)
    axP.imshow(np.ma.masked_invalid(dane), cmap=cmap, norm=norm,
               extent=[b.left, b.right, b.bottom, b.top],
               interpolation="nearest", zorder=1)
    axP.add_patch(plt.Circle((sx, sy), pr, fill=False, lw=1.1,
                             edgecolor=ATRAMENT, alpha=.45, zorder=3))
    axP.plot(sx, sy, marker="P", markersize=10, color="#ffffff",
             markeredgecolor=ATRAMENT, markeredgewidth=1.1, zorder=6)

    if punkty:
        for nazwa, p in sorted(punkty.items()):
            X, Y = tx.transform(p["lon"], p["lat"])
            kat = np.arctan2(Y - sy, X - sx)
            axP.annotate(NAZWY.get(nazwa, nazwa), xy=(X, Y),
                         xytext=(sx + (pr + 1500) * np.cos(kat),
                                 sy + (pr + 1500) * np.sin(kat)),
                         ha="center" if abs(np.cos(kat)) < .5 else
                            ("left" if np.cos(kat) > 0 else "right"),
                         va="center", fontsize=9.5, weight="bold",
                         color=ATRAMENT, zorder=7,
                         arrowprops=dict(arrowstyle="-", color=ATRAMENT,
                                         lw=.9, alpha=.55, shrinkA=0, shrinkB=5))
            axP.plot(X, Y, marker="o", markersize=7, markerfacecolor="#ffffff",
                     markeredgecolor=ATRAMENT, markeredgewidth=1.5, zorder=8)

    _podzialka(axP, sx - r + 1000, sy - r + 1000)
    _ramka(axP, sx, sy, r)
    axP.set_title(tytul_prawy, fontsize=13, weight="bold", color=ATRAMENT,
                  loc="left", pad=8)
    fig.legend(handles=[Patch(facecolor=KLASY_KOLOR[i],
                              label=f"{progi[i]:.1f}–{progi[i+1]:.1f}")
                        for i in range(5)],
               loc="upper right", bbox_to_anchor=(0.985, 0.115), ncol=5,
               fontsize=9, frameon=False, columnspacing=1.1,
               title=f"{jednostka}  ·  ciemniej = lepiej", title_fontsize=9)

    fig.text(0.5, 0.018,
             "krzyżyk — stacja meteorologiczna · okrąg — bufor 10 km "
             "reprezentatywności · pięć klas kwantylowych po 20% powierzchni bufora",
             fontsize=8.5, color=MUTED, ha="center")
    fig.subplots_adjust(left=.01, right=.99, top=.94, bottom=.14, wspace=.04)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    return ("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            progi)


def klasy(tif: Path, pot: dict, tytul: str, jednostka: str,
          rozmiar: float = 6.3) -> tuple[str, list[float]]:
    """Sam panel klas - do porownania wariantow kryterium."""
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(tif) as s_:
        a = s_.read(1)
        b = s_.bounds
    from pyproj import Transformer
    tx = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    sx, sy = tx.transform(pot["stacja"]["lon"], pot["stacja"]["lat"])
    pr = pot["stacja"]["promien_m"]

    dane = a / 1000.0
    v = dane[~np.isnan(dane)]
    progi = [float(np.percentile(v, q)) for q in (0, 20, 40, 60, 80, 100)]
    cmap = ListedColormap(KLASY_KOLOR)

    fig, ax = plt.subplots(figsize=(rozmiar, rozmiar * 1.12), dpi=175)
    fig.patch.set_facecolor(TLO)
    ax.set_facecolor(TLO)
    ax.imshow(np.ma.masked_invalid(dane), cmap=cmap,
              norm=BoundaryNorm(progi, cmap.N),
              extent=[b.left, b.right, b.bottom, b.top],
              interpolation="nearest", zorder=1)
    ax.add_patch(plt.Circle((sx, sy), pr, fill=False, lw=1.1,
                            edgecolor=ATRAMENT, alpha=.45, zorder=3))
    ax.plot(sx, sy, marker="P", markersize=9, color="#ffffff",
            markeredgecolor=ATRAMENT, markeredgewidth=1.1, zorder=6)
    _podzialka(ax, sx - pr - 1200, sy - pr - 1000)
    _ramka(ax, sx, sy, pr + 2200)
    ax.set_title(tytul, fontsize=12, weight="bold", color=ATRAMENT,
                 loc="left", pad=7)
    fig.legend(handles=[Patch(facecolor=KLASY_KOLOR[i],
                              label=f"{progi[i]:.1f}–{progi[i+1]:.1f}")
                        for i in range(5)],
               loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=5,
               fontsize=8, frameon=False, columnspacing=.8,
               title=jednostka, title_fontsize=8)
    fig.subplots_adjust(left=.02, right=.98, top=.93, bottom=.14)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    return ("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            progi)


if __name__ == "__main__":
    import json
    WY = ROOT / "wyniki"
    pot = json.loads((WY / "json" / "potencjal_gsa.json").read_text(encoding="utf-8"))
    d, progi = para(WY / "rastry" / "gsa_sezon.tif", pot, "Gdzie postawić ul",
                    "tony cukrów w zasięgu lotu", pot["kryteria"])
    (ROOT / "mapy" / "podglad_mapy.png").write_bytes(base64.b64decode(d.split(",")[1]))
    print("progi klas:", [round(x, 1) for x in progi], "-> podglad_mapy.png")


def seria(tif_dekady: Path, pot: dict, lot: dict | None = None,
          rozmiar: float = 13.0) -> str:
    """Seria map przez sezon - jak optimum wedruje wraz z kwitnieniem.

    Wspolna skala barw dla wszystkich paneli. Bez tego kazdy panel bylby
    rozciagniety na wlasny zakres i czerwcowa dziura wygladalaby tak samo
    bogato jak szczyt rzepakowy - a to wlasnie ta roznica jest trescia rysunku.

    lot - slownik sprawnosci lotnej per dekada; jesli podany, panele pokazuja
    ile da sie ZEBRAC, a nie ile wisi na polach.
    """
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(tif_dekady) as s:
        stos = s.read().astype("float64") / 1000.0
        b = s.bounds
        opisy = list(s.descriptions)
    dek = pot["dekady"]

    if lot:
        for i, d in enumerate(dek):
            stos[i] *= lot.get(str(d), 0.0)

    # panele tylko dla dekad, w ktorych cokolwiek jest
    sumy = [np.nansum(stos[i]) for i in range(len(dek))]
    prog = max(sumy) * 0.01
    idx = [i for i, v in enumerate(sumy) if v > prog]
    if not idx:
        idx = list(range(len(dek)))
    idx = list(range(min(idx), max(idx) + 1))

    vmax = float(np.nanmax(stos[idx]))
    progi = [vmax * f for f in (0, .2, .4, .6, .8, 1.0)]
    cmap = ListedColormap(KLASY_KOLOR)
    norm = BoundaryNorm(progi, cmap.N)

    from pyproj import Transformer
    tx = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    sx, sy = tx.transform(pot["stacja"]["lon"], pot["stacja"]["lat"])
    pr = pot["stacja"]["promien_m"]

    kol = min(5, len(idx))
    wier = int(np.ceil(len(idx) / kol))
    fig, osie = plt.subplots(wier, kol, figsize=(rozmiar, rozmiar / kol * wier * 1.12),
                             dpi=170)
    fig.patch.set_facecolor(TLO)
    osie = np.atleast_1d(osie).ravel()

    for ax, i in zip(osie, idx):
        ax.set_facecolor(TLO)
        ax.imshow(np.ma.masked_invalid(stos[i]), cmap=cmap, norm=norm,
                  extent=[b.left, b.right, b.bottom, b.top],
                  interpolation="nearest")
        ax.add_patch(plt.Circle((sx, sy), pr, fill=False, lw=.8,
                                edgecolor=ATRAMENT, alpha=.35))
        _ramka(ax, sx, sy, pr + 1200)
        ax.set_title(f"{opisy[i] or dek[i]}", fontsize=10.5, weight="bold",
                     color=ATRAMENT, loc="left", pad=4)
        szczyt = np.nanmax(stos[i])
        ax.text(.97, .03, f"maks. {szczyt:.1f} t", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=8.5, color=MUTED)
    for ax in osie[len(idx):]:
        ax.set_visible(False)

    fig.legend(handles=[Patch(facecolor=KLASY_KOLOR[i],
                              label=f"{progi[i]:.1f}–{progi[i+1]:.1f}")
                        for i in range(5)],
               loc="lower center", bbox_to_anchor=(.5, .005), ncol=5,
               fontsize=9, frameon=False, columnspacing=1.2,
               title=("tony cukrów możliwe do zebrania w dekadzie"
                      if lot else "tony cukrów dostępne w dekadzie"),
               title_fontsize=9.5)
    fig.subplots_adjust(left=.01, right=.99, top=.94, bottom=.10,
                        wspace=.05, hspace=.18)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def dwa_szczyty(tif_dekady: Path, pot: dict, lot: dict,
                wiosna: list[int], lato: list[int],
                rozmiar: float = 12.6) -> str:
    """Dwa rezimy pozytkowe obok siebie, wspolna skala.

    Zastapilo serie 11 paneli przez sezon. Tamta byla zla, bo szesc paneli
    bylo pustych - uzywala map do pokazania NIEOBECNOSCI. Przerwa miedzy
    pozytkami to fakt czasowy i nalezy do wykresu kalendarza; mapy maja
    pokazac to, czego wykres nie potrafi, czyli ze oba szczyty leza gdzie indziej.
    """
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    with rasterio.open(tif_dekady) as s:
        stos = s.read().astype("float64") / 1000.0
        b = s.bounds
    dek = pot["dekady"]
    idx = {d: i for i, d in enumerate(dek)}

    def suma(okres):
        return np.nansum([stos[idx[d]] * lot.get(str(d), 0.0) for d in okres],
                         axis=0)

    A, B = suma(wiosna), suma(lato)
    vmax = float(max(np.nanmax(A), np.nanmax(B)))
    progi = [vmax * f for f in (0, .2, .4, .6, .8, 1.0)]
    cmap, norm = ListedColormap(KLASY_KOLOR), BoundaryNorm(
        [vmax * f for f in (0, .2, .4, .6, .8, 1.0)], 5)

    from pyproj import Transformer
    tx = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    sx, sy = tx.transform(pot["stacja"]["lon"], pot["stacja"]["lat"])
    pr = pot["stacja"]["promien_m"]

    fig, osie = plt.subplots(1, 2, figsize=(rozmiar, rozmiar * .58), dpi=175)
    fig.patch.set_facecolor(TLO)
    dat = pot["daty"]
    opisy = [(A, f"Szczyt wiosenny · {dat[str(wiosna[0])]}–{dat[str(wiosna[-1])]}",
              "rzepak ozimy"),
             (B, f"Szczyt letni · {dat[str(lato[0])]}–{dat[str(lato[-1])]}",
              "fasola wielokwiatowa")]

    for ax, (m, tyt, pod) in zip(osie, opisy):
        ax.set_facecolor(TLO)
        ax.imshow(np.ma.masked_invalid(np.where(np.isnan(stos[0]), np.nan, m)),
                  cmap=cmap, norm=norm,
                  extent=[b.left, b.right, b.bottom, b.top],
                  interpolation="nearest")
        ax.add_patch(plt.Circle((sx, sy), pr, fill=False, lw=1.1,
                                edgecolor=ATRAMENT, alpha=.4))
        ax.plot(sx, sy, marker="P", markersize=9, color="#ffffff",
                markeredgecolor=ATRAMENT, markeredgewidth=1.1)
        # najlepszy punkt tego rezimu
        mm = np.where(np.isnan(stos[0]), -np.inf, m)
        i, j = np.unravel_index(np.nanargmax(mm), mm.shape)
        X = b.left + (j + .5) * 100
        Y = b.top - (i + .5) * 100
        ax.plot(X, Y, marker="o", markersize=9, markerfacecolor="none",
                markeredgecolor=ATRAMENT, markeredgewidth=1.8)
        ax.annotate("optimum", xy=(X, Y), xytext=(0, 16),
                    textcoords="offset points", ha="center", fontsize=9,
                    weight="bold", color=ATRAMENT)
        _podzialka(ax, sx - pr - 900, sy - pr - 700)
        _ramka(ax, sx, sy, pr + 2000)
        # tytul wyzej, zeby podtytul sie pod nim zmiescil
        ax.set_title(tyt, fontsize=13, weight="bold", color=ATRAMENT,
                     loc="left", pad=26)
        ax.text(0, 1.012, pod, transform=ax.transAxes, fontsize=10.5,
                color=MUTED, va="bottom")
        ax.text(.98, .02, f"maks. {np.nanmax(m):.1f} t", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=9, color=MUTED)

    fig.legend(handles=[Patch(facecolor=KLASY_KOLOR[i],
                              label=f"{progi[i]:.1f}–{progi[i+1]:.1f}")
                        for i in range(5)],
               loc="lower center", bbox_to_anchor=(.5, .01), ncol=5,
               fontsize=9, frameon=False, columnspacing=1.2,
               title="tony cukrów możliwe do zebrania w okresie · ciemniej = lepiej",
               title_fontsize=9.5)
    fig.subplots_adjust(left=.01, right=.99, top=.90, bottom=.13, wspace=.04)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=TLO)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
