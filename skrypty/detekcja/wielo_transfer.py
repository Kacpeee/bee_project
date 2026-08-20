"""
ETAP 16c - czy wykrywarka przenosi sie na INNY rok.

PO CO
Produkt to mapa cukru dla pszczelarza na lata BEZ deklaracji. GSA jest tylko
za 2025 i 2026, wiec jedyny twardy test wstecz to: nauczka na 2025, cechy
i etykiety z 2026, porownanie PO SPLOCIE 3 km - tak jak mapa naprawde liczy.

F1 na pikselu i r w kwadracie 10 km tu nie rozstrzygaja. Malina myli sie z
porzeczka w tym samym rejonie; po splocie cukru (160 vs 36 kg/ha) to wychodzi.

STALE UPRAWY vs JARE
Sad/malina/porzeczka/TUZ nie jezdza po polach. Dla nich "zgadza sie 2026"
moze byc pamiecia geografii 2025. Dlatego jest tez naiwny wzorzec: najblizsza
dzialka z proby 2025 w promieniu 3 km. Fasola i gryka musza BIC ten wzorzec,
inaczej model nie widzi uprawy, tylko powiat.

Uruchomienie:
    python skrypty/detekcja/wielo_transfer.py
"""

from __future__ import annotations

import json
from pathlib import Path

import ee
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

import sys as _sys
from pathlib import Path as _P
_sys.path[:0] = [str(p) for p in _P(__file__).resolve().parents[1].iterdir()
                 if p.is_dir()]

import gee_klasyfikator_rzepaku as K
import klasyfikator_wielo as W
import potencjal_gsa as P
from wielo_diagnoza import MAX_ZER, ODRZUC, SCAL

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
SHP26 = ROOT / "dane" / "gsa_lubelskie_2026" / "2026_uprawy_woj_06_akt_public.shp"
CACHE_PKT26 = WYNIKI / "cache" / "wielo_punkty_2026.csv"
CACHE_CECH26 = WYNIKI / "cache" / "wielo_cechy_2026.csv"

ROK26 = 2026
LAM_M, ZASIEG_M = 1000.0, 3000.0
DRZEW, ZIARNO = 300, 42
PROG_R = 0.85

GRUPA = {
    "koniczyna czerwona": "motylkowe pastewne",
    "lucerna mieszańcowa": "motylkowe pastewne",
}
JAGODY = {"malina": "jagodniki", "porzeczka": "jagodniki"}
STALE = {"Sad", "malina", "porzeczka", "TUZ", "jagodniki",
         "motylkowe pastewne"}

KG = {n: v[0] for n, v in P.POZYTKI.items()}
KG["gorczyca"] = KG["gorczyca biała"]
KG["słonecznik"] = KG["słonecznik"]
KG["motylkowe pastewne"] = KG["koniczyna czerwona"]
KG["jagodniki"] = 0.5 * (KG["malina"] + KG["porzeczka"])
KG["inne"] = 0.0


def przygotuj(df: pd.DataFrame, X: pd.DataFrame, kol: list[str]) -> pd.DataFrame:
    d = df.reset_index(drop=True).join(X[kol])
    d = d.dropna(subset=kol)
    d = d[~d.etykieta.isin(ODRZUC)].copy()
    d["etykieta"] = d.etykieta.replace(SCAL).replace(GRUPA)
    return d


def splot_punktow(xy: np.ndarray, waga: np.ndarray,
                  lam: float = LAM_M, zasieg: float = ZASIEG_M) -> np.ndarray:
    """Suma waga * exp(-d/lam) w kole zasiegu. To samo jadro co mapa."""
    xy = np.asarray(xy, float)
    waga = np.asarray(waga, float).reshape(-1)
    n = len(xy)
    out = np.zeros(n, float)
    if n == 0 or waga.max() == 0:
        return out
    tree = cKDTree(xy)
    nbrs = tree.query_ball_tree(tree, zasieg)
    for i, js in enumerate(nbrs):
        if not js:
            continue
        dxy = xy[js] - xy[i]
        d = np.hypot(dxy[:, 0], dxy[:, 1])
        out[i] = float(np.dot(waga[js], np.exp(-d / lam)))
    return out


def r_splot(xy: np.ndarray, prawda: np.ndarray, pred: np.ndarray) -> float:
    a = splot_punktow(xy, prawda.astype(float))
    b = splot_punktow(xy, pred.astype(float))
    if a.std() < 1e-12 or b.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def naiwna_geografia(xy25: np.ndarray, et25: np.ndarray,
                     xy26: np.ndarray) -> np.ndarray:
    """Etykieta najblizszego punktu 2025 w zasiegu lotu; inaczej 'inne'."""
    tree = cKDTree(xy25)
    d, j = tree.query(xy26, k=1)
    out = np.array(["inne"] * len(xy26), dtype=object)
    ok = d <= ZASIEG_M
    out[ok] = et25[j[ok]]
    return out


if __name__ == "__main__":
    print("1/4  próbka działek GSA 2026")
    df26 = W.probka(shp=SHP26, cache=CACHE_PKT26)

    print("\n2/4  cechy Sentinel-2 sezon 2026 (GEE, ~godzina przy braku cache)")
    K.start()
    K.AOI = ee.Geometry.Rectangle(
        [pd.to_numeric(df26.lon).min() - .1, pd.to_numeric(df26.lat).min() - .1,
         pd.to_numeric(df26.lon).max() + .1, pd.to_numeric(df26.lat).max() + .1],
        "EPSG:4326", False)
    obraz, nazwy = W.cechy_szereg(ROK26)
    X26 = W.pobierz_cechy(obraz, nazwy, df26, cache=CACHE_CECH26)

    print("\n3/4  ucz 2025, test 2026")
    df25 = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    X25 = pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
    kol = [c for c in X25.columns if c.startswith(("ndvi", "ndyi"))]
    d25 = przygotuj(df25, X25, kol)
    d26 = przygotuj(df26, X26, kol)
    # Okno musi byc kompletne w OBU latach. Liczenie zer tylko na 2025
    # dawalo test nieuczciwy: sezon 2026 jeszcze trwa, wiec oba okna
    # wrzesniowe i polowa sierpniowych sa u niego puste (100% i 37% zer),
    # a model uczony na pelnym 2025 pytal je o wartosci. Uderzalo to
    # dokladnie w rosliny pozne - slonecznik, gryke, fasole - czyli w te,
    # ktore "nie przeszly". Rzepak przezywal, bo jego sygnatura siedzi
    # w pazdzierniku i marcu-maju, kompletnych w obu latach.
    zer25 = (d25[kol] == 0).mean()
    zer26 = (d26[kol] == 0).mean()
    dobre = [c for c in kol if zer25[c] <= MAX_ZER and zer26[c] <= MAX_ZER]
    stracone = [c for c in kol if zer25[c] <= MAX_ZER < zer26[c]]
    print(f"  okna wspolne: {len(dobre)}/{len(kol)}  "
          f"n25={len(d25):,}  n26={len(d26):,}")
    if stracone:
        print(f"  odrzucone przez niedokonczony sezon 2026: "
              f"{', '.join(sorted(stracone))}")

    las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                 random_state=ZIARNO)
    las.fit(d25[dobre], d25["etykieta"])
    d26 = d26.assign(pred=las.predict(d26[dobre]))

    xy25 = d25[["x", "y"]].to_numpy()
    xy26 = d26[["x", "y"]].to_numpy()
    geo = naiwna_geografia(xy25, d25.etykieta.to_numpy(), xy26)
    d26["pred_geo"] = geo

    # jagodniki - osobna ocena pary malina/porzeczka
    d26j = d26.copy()
    d26j["cel"] = d26j.etykieta.replace(JAGODY)
    d26j["pred_j"] = d26j.pred.replace(JAGODY)

    print("\n4/4  F1 na punkcie vs r po splocie 3 km (to samo jadro co mapa)")
    print(f"{'gatunek':24s}{'F1':>8}{'r splot':>10}{'r kg':>8}"
          f"{'r geo':>8}{'n':>7}")
    klasy = sorted(set(d26.etykieta) | set(d26.pred))
    per, ok = {}, []
    for g in klasy:
        if g == "inne":
            continue
        f1 = f1_score((d26.etykieta == g).astype(int),
                      (d26.pred == g).astype(int))
        r = r_splot(xy26, d26.etykieta == g, d26.pred == g)
        kg = float(KG.get(g, 0))
        rkg = r_splot(xy26,
                      (d26.etykieta == g).astype(float) * kg,
                      (d26.pred == g).astype(float) * kg)
        rgeo = r_splot(xy26, d26.etykieta == g, d26.pred_geo == g)
        n = int((d26.etykieta == g).sum())
        per[g] = {"f1": f1, "r_splot": r, "r_kg": rkg, "r_geografia": rgeo,
                  "n": n, "stala": g in STALE}
        znacznik = ""
        if not np.isnan(r) and r >= PROG_R:
            ok.append(g)
            znacznik = " <<"
        print(f"{g[:22]:24s}{f1:8.3f}{r:10.3f}{rkg:8.3f}{rgeo:8.3f}{n:7d}{znacznik}")

    f1_jag = f1_score((d26j.cel == "jagodniki").astype(int),
                      (d26j.pred_j == "jagodniki").astype(int))
    r_jag = r_splot(xy26, d26j.cel == "jagodniki", d26j.pred_j == "jagodniki")
    print(f"{'jagodniki (mal+porz)':24s}{f1_jag:8.3f}{r_jag:10.3f}")

    cuk_t = np.array([KG.get(a, 0) for a in d26.etykieta])
    cuk_p = np.array([KG.get(a, 0) for a in d26.pred])
    r_cuk = r_splot(xy26, cuk_t, cuk_p)
    print(f"\ncukier po splocie, wszystkie klasy: r = {r_cuk:.3f}")
    print(f"klasy z r_splot >= {PROG_R}: {', '.join(sorted(ok)) if ok else 'BRAK'}")

    (WYNIKI / "json" / "wielo_transfer.json").write_text(json.dumps({
        "trening": 2025, "test": 2026,
        "n_2025": len(d25), "n_2026": len(d26),
        "n_cech": len(dobre),
        "jadro": {"lambda_m": LAM_M, "zasieg_m": ZASIEG_M},
        "prog_r": PROG_R,
        "per_gatunek": per,
        "jagodniki": {"f1": f1_jag, "r_splot": r_jag},
        "cukier_splot_r": r_cuk,
        "klasy_powyzej_progu": ok,
        "metoda": "nauczka 2025, test 2026; r po jadrach exp(-d/1 km) "
                  "obcietych na 3 km, na punktach dzialek",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano wielo_transfer.json")
