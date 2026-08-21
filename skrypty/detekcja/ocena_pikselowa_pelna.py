"""
Pelna ocena pikselowa: ze zbozami, w prewalencji rzeczywistej,
i z porownaniem pokolen modelu na TYM SAMYM zbiorze.

TRZY RZECZY, KTORYCH BRAKOWALO

1. KLASA "INNE". Pierwsza wersja probkowala same gatunki pozytkowe, wiec
   rzepak nie mial szansy pomylic sie z pszenica. To zawyzalo precyzje,
   bo w terenie zboza zajmuja wiekszosc gruntow ornych.

2. PREWALENCJA. Proba jest zrownowazona (260 dzialek na gatunek), a w terenie
   proporcje sa skrajnie nierowne. Czulosc od tego nie zalezy, ale PRECYZJA
   owszem: im wiecej w terenie klasy, ktora bywa mylona z rzepakiem, tym
   wiecej falszywych alarmow na jedno trafienie. Przewazenie robi sie na
   macierzy pomylek, wagami z arealu ARiMR - bez ponownego liczenia modelu.

3. POROWNANIE POKOLEN. Stary pomiar (0,689) dotyczyl modelu 3-cechowego
   i calego rastra; nowy - modelu S1+S2 na probce pikseli. Zeby zestawienie
   mialo sens, oba warianty cech ocenia sie TUTAJ, na tych samych pikselach.
   Cechy stare odtwarzane z okien polmiesiecznych: jesien = pazdziernik +
   listopad, marzec = okna 12-13 (tak samo numeruje przedkwitnieniowy.py).

Uruchomienie:
    python skrypty/detekcja/ocena_pikselowa_pelna.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

sys.path[:0] = [str(p) for p in Path(__file__).resolve().parents[1].iterdir()
                if p.is_dir()]

from wielo_diagnoza import ODRZUC, SCAL                       # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
C = WYNIKI / "cache"
GRUPA = {"koniczyna czerwona": "motylkowe pastewne",
         "lucerna mieszańcowa": "motylkowe pastewne"}
DRZEW, ZIARNO = 300, 42


def zbior_testowy() -> pd.DataFrame:
    """Piksele pozytkowe + 'inne', z cechami."""
    a = pd.read_csv(C / "piksele_punkty.csv")
    Xa = pd.read_csv(C / "piksele_cechy.csv").set_index("i")
    b = pd.read_csv(C / "piksele_inne_punkty.csv")
    Xb = pd.read_csv(C / "piksele_inne_cechy.csv").set_index("i")
    d = pd.concat([a, b], ignore_index=True)
    X = pd.concat([Xa, Xb])
    return d.join(X, on="i")


def stare_cechy(d: pd.DataFrame) -> pd.DataFrame:
    """Trzy cechy pokolenia 1 odtworzone z okien polmiesiecznych."""
    d = d.copy()
    d["jesien_ndvi"] = d[[f"ndvi_{i:02d}" for i in (2, 3, 4, 5)]].mean(axis=1)
    d["marzec_ndvi"] = d[["ndvi_12", "ndvi_13"]].mean(axis=1)
    d["marzec_ndyi"] = d[["ndyi_12", "ndyi_13"]].mean(axis=1)
    return d


def miary_z_macierzy(Cm, klasy, kl, wagi=None):
    """Precyzja/czulosc/F1 dla klasy kl, opcjonalnie przewazone.

    Wagi mnoza WIERSZE (klasy prawdziwe), bo to liczebnosc klasy w terenie
    decyduje, ile jej pikseli trafi do fałszywych alarmów innej klasy.
    """
    i = klasy.index(kl)
    M = Cm.astype(float).copy()
    if wagi is not None:
        M = M * np.array([wagi.get(k, 1.0) for k in klasy])[:, None]
    tp = M[i, i]
    fp = M[:, i].sum() - tp
    fn = M[i, :].sum() - tp
    prec = tp / max(tp + fp, 1e-9)
    czul = tp / max(tp + fn, 1e-9)
    return {"precyzja": float(prec), "czulosc": float(czul),
            "f1": float(2 * prec * czul / max(prec + czul, 1e-9))}


if __name__ == "__main__":
    from sklearn.metrics import confusion_matrix

    te = zbior_testowy()
    te = te[~te.etykieta.isin(ODRZUC)].copy()
    te["grupa"] = te.etykieta.replace(SCAL).replace(GRUPA)

    tr = pd.read_csv(C / "wielo_punkty.csv")
    Xt = (pd.read_csv(C / "wielo_cechy.csv").set_index("i")
          .join(pd.read_csv(C / "wielo_cechy_s1.csv").set_index("i")))
    tr = tr.reset_index(drop=True).join(Xt)
    tr = tr[(tr.test == 0) & (~tr.etykieta.isin(ODRZUC))].copy()
    tr["grupa"] = tr.etykieta.replace(SCAL).replace(GRUPA)

    nowe = [c for c in Xt.columns
            if c.startswith(("ndvi", "ndyi", "vv_", "vh_", "rat_"))
            and c in te.columns]
    tr_s, te_s = stare_cechy(tr), stare_cechy(te)
    stare = ["jesien_ndvi", "marzec_ndvi", "marzec_ndyi"]

    wyniki = {}
    for nazwa, kol, T, E in (("pokolenie 1 (3 cechy optyczne)", stare, tr_s, te_s),
                             ("pokolenie 2 (S1+S2, 130 cech)", nowe, tr, te)):
        T2 = T.dropna(subset=kol)
        E2 = E.dropna(subset=kol).copy()
        las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                     random_state=ZIARNO).fit(T2[kol], T2.grupa)
        E2["pred"] = las.predict(E2[kol])
        klasy = sorted(set(E2.grupa) | set(E2.pred))
        Cm = confusion_matrix(E2.grupa, E2.pred, labels=klasy)
        m = miary_z_macierzy(Cm, klasy, "rzepak ozimy")
        f1m = f1_score(E2.grupa, E2.pred, average="macro")
        print(f"\n{nazwa}")
        print(f"  pikseli {len(E2):,}, cech {len(kol)}")
        print(f"  F1-makro {f1m:.3f}   rzepak: precyzja {m['precyzja']:.3f} "
              f"czulosc {m['czulosc']:.3f} F1 {m['f1']:.3f}")
        wyniki[nazwa] = {"f1_makro": float(f1m), "rzepak": m,
                         "n_pikseli": int(len(E2)), "n_cech": len(kol)}
        if kol is nowe:
            Cm_n, klasy_n, E_n = Cm, klasy, E2

    # ---------------------------------------------- prewalencja rzeczywista
    kal = json.loads((WYNIKI / "json" / "kalibracja_arealowa.json")
                     .read_text(encoding="utf-8"))
    areal = dict(kal["areal_gsa"])
    # "inne" = reszta gruntow ornych wojewodztwa; przyblizenie z ARiMR:
    # powierzchnia uzytkow rolnych minus zsumowane gatunki pozytkowe
    UR_HA = 1_400_000        # uzytki rolne w wojewodztwie lubelskim (GUS)
    areal_pozytki = sum(areal.values())
    areal["inne"] = max(UR_HA - areal_pozytki, areal_pozytki)
    ud_ter = {k: v / sum(areal.values()) for k, v in areal.items()}

    licz = E_n.grupa.value_counts()
    ud_pr = (licz / licz.sum()).to_dict()
    wagi = {k: (ud_ter.get(k, ud_ter.get("inne", 0)) / ud_pr[k])
            for k in ud_pr if ud_pr[k] > 0}
    m_prew = miary_z_macierzy(Cm_n, klasy_n, "rzepak ozimy", wagi)

    print("\nPREWALENCJA RZECZYWISTA (wagi z arealu ARiMR)")
    print(f"  udzial rzepaku w probie   {ud_pr.get('rzepak ozimy', 0)*100:5.1f}%")
    print(f"  udzial rzepaku w terenie  {ud_ter.get('rzepak ozimy', 0)*100:5.1f}%")
    print(f"  udzial 'inne' w terenie   {ud_ter.get('inne', 0)*100:5.1f}%")
    print(f"  rzepak: precyzja {m_prew['precyzja']:.3f} "
          f"czulosc {m_prew['czulosc']:.3f} F1 {m_prew['f1']:.3f}")

    print("\nZ CZYM MYLONY RZEPAK (pokolenie 2, piksele)")
    fal = E_n[(E_n.grupa != "rzepak ozimy") & (E_n.pred == "rzepak ozimy")]
    for k, n in fal.grupa.value_counts().head(5).items():
        print(f"   falszywy alarm <- {k:24s} {n}")

    (WYNIKI / "json" / "ocena_pikselowa_pelna.json").write_text(json.dumps({
        "opis": "ocena pikselowa ze zbozami; model uczony tylko na blokach "
                "treningowych; porownanie pokolen na tym samym zbiorze",
        "pokolenia": wyniki,
        "prewalencja_rzeczywista": {
            "rzepak": m_prew,
            "udzial_w_probie": {k: float(v) for k, v in ud_pr.items()},
            "udzial_w_terenie": {k: float(v) for k, v in ud_ter.items()},
            "zrodlo_wag": "areal_gsa z kalibracja_arealowa.json + UR z GUS",
        },
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano wyniki/json/ocena_pikselowa_pelna.json")
