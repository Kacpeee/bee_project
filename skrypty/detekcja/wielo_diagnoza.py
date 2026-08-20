"""
ETAP 16b - diagnoza i poprawa klasyfikatora wieloklasowego.

DWA BLEDY W PIERWSZYM PODEJSCIU

1. PUSTE OKNA ZIMOWE WYPELNIANE ZEREM.
   W polowie stycznia 100% punktow ma dokladnie 0 - nad Lubelszczyzna nie
   bylo w tym oknie ANI JEDNEGO zdjecia bez chmur. W II polowie lutego 59%,
   w I polowie grudnia 47%. unmask(0) zamienia "brak danych" na "anomalia
   rowna zero", czyli na twierdzenie o roslinie. To ok. 10 z 52 cech bedacych
   szumem. Tu: okna z ponad 25% zer sa usuwane.

2. KLASY BEDACE TYM SAMYM GATUNKIEM.
   Deklaracje maja etykiety zbiorcze i szczegolowe naraz: "gorczyca" obok
   "gorczyca biala", "slonecznik" obok "slonecznik oleisty". Model karany byl
   za nierozroznienie rzeczy nierozroznialnych - stad pomylki 33% i 28%.
   Rzepak jary to ten sam gatunek co ozimy (1350 ha, 0.25% cukru) - odpada.

POROWNANIE JEST CELEM
Liczymy cztery warianty na tych samych danych, zeby bylo widac, ile daje
kazda poprawka - a nie tylko koncowy wynik.

Dodatkowo: test BINARNY rzepaku na tych samych cechach, zeby porownac
z dedykowanym klasyfikatorem (F1 0.90) i sprawdzic, czy szereg polmiesieczny
jest gorszy od okien recznych, czy tylko inaczej oceniany.

Uruchomienie:
    python skrypty/detekcja/wielo_diagnoza.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
ZIARNO = 42
DRZEW = 300
MAX_ZER = 0.25          # okno odrzucane, gdy tyle punktow ma dokladne 0

# etykiety deklaracji opisujace ten sam pozytek
SCAL = {
    "gorczyca biała": "gorczyca",
    "słonecznik oleisty": "słonecznik",
}
ODRZUC = ["rzepak jary"]          # ten sam gatunek co ozimy, 0.25% cukru

# udzial w cukrach wojewodztwa (do policzenia pokrycia)
CUKIER = {"rzepak ozimy": 57.2, "TUZ": 18.4, "malina": 6.3,
          "gryka zwyczajna": 6.1, "fasola wielokwiatowa": 5.1,
          "porzeczka": 2.5, "lucerna mieszańcowa": 0.9,
          "koniczyna czerwona": 0.8, "słonecznik": 0.8, "Sad": 0.3,
          "gorczyca": 0.3, "bobik": 0.1}


def wczytaj():
    df = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    X = pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
    kol = [c for c in X.columns if c.startswith(("ndvi", "ndyi"))]
    d = df.reset_index(drop=True).join(X[kol].sort_index())
    return d.dropna(subset=kol), kol


def ocen(d, kol, nazwa, cel="etykieta"):
    tr, te = d[d.test == 0], d[d.test == 1]
    las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                 random_state=ZIARNO)
    las.fit(tr[kol], tr[cel])
    pred = las.predict(te[kol])
    f1m = f1_score(te[cel], pred, average="macro")
    kl = sorted(d[cel].unique())
    m = confusion_matrix(te[cel], pred, labels=kl).astype(float)
    wy = {}
    for i, n in enumerate(kl):
        tp, sn, sp = m[i, i], m[i].sum(), m[:, i].sum()
        p, c = tp / max(sp, 1e-9), tp / max(sn, 1e-9)
        wy[n] = {"precyzja": p, "czulosc": c,
                 "f1": 2 * p * c / max(p + c, 1e-9), "n": int(sn)}
    print(f"{nazwa:44s} F1-makro {f1m:.3f}  ({len(kol)} cech, "
          f"{len(kl)} klas)")
    return wy, f1m, m, kl


if __name__ == "__main__":
    d, kol = wczytaj()
    print(f"punktow {len(d):,}, cech {len(kol)}\n")

    zer = (d[kol] == 0).mean()
    dobre = [c for c in kol if zer[c] <= MAX_ZER]
    print(f"okna odrzucone jako puste (>{MAX_ZER:.0%} zer): "
          f"{len(kol) - len(dobre)} z {len(kol)}")
    print("  " + ", ".join(sorted(set(c for c in kol if zer[c] > MAX_ZER))))

    d2 = d[~d.etykieta.isin(ODRZUC)].copy()
    d2["etykieta"] = d2.etykieta.replace(SCAL)
    print(f"klas po scaleniu: {d2.etykieta.nunique()} "
          f"(scalono {len(SCAL)}, odrzucono {len(ODRZUC)})\n")

    print("WARIANTY")
    wA, fA, *_ = ocen(d, kol, "A. jak bylo (wszystko)")
    wB, fB, *_ = ocen(d2, kol, "B. + scalone etykiety tego samego gatunku")
    wC, fC, *_ = ocen(d, dobre, "C. + bez pustych okien zimowych")
    wD, fD, mD, klD = ocen(d2, dobre, "D. obie poprawki")

    print(f"\nWYNIK KONCOWY (wariant D)\n{'gatunek':26s}{'n':>6}"
          f"{'precyzja':>10}{'czulosc':>9}{'F1':>7}  glowna pomylka")
    for i, n in enumerate(klD):
        w = wD[n]
        poza = [(mD[i, j], klD[j]) for j in range(len(klD)) if j != i]
        gl, udz = (max(poza)[1], max(poza)[0] / max(w["n"], 1)) if poza else ("-", 0)
        print(f"{n[:24]:26s}{w['n']:>6}{w['precyzja']:>10.3f}"
              f"{w['czulosc']:>9.3f}{w['f1']:>7.3f}  {gl[:20]} ({udz:.0%})")

    # test binarny rzepaku - porownanie z dedykowanym modelem (F1 0.90)
    db = d.copy()
    db["rz"] = (db.etykieta == "rzepak ozimy").astype(int)
    trb, teb = db[db.test == 0], db[db.test == 1]
    lb = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                random_state=ZIARNO).fit(trb[dobre], trb.rz)
    pb = lb.predict(teb[dobre])
    mb = confusion_matrix(teb.rz, pb)
    (tn, fp), (fn, tp) = mb
    pr, cz = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    print(f"\nTEST BINARNY rzepaku na tych samych cechach: "
          f"precyzja {pr:.3f} czulosc {cz:.3f} "
          f"F1 {2*pr*cz/max(pr+cz,1e-9):.3f}")
    print("  (dedykowany klasyfikator 8-cechowy: F1 0.90)")

    # ---- WLASCIWA MIARA: zgodnosc PO AGREGACJI, nie na pikselu.
    # Mapa rozmywa wszystko jadrem zasiegu lotu (3 km), wiec pomylka miedzy
    # sasiednimi dzialkami maliny i porzeczki znika, a liczy sie, czy model
    # trafia w ZAGESZCZENIE rejonu. Komorka 10 km jako przyblizenie splotu.
    # (Rzepak: F1 0.69 na pikselu, ale r = 0.94 na mapie po rozmyciu.)
    d3 = d2.copy()
    d3["grupa"] = d3.etykieta.replace(
        {"koniczyna czerwona": "motylkowe pastewne",
         "lucerna mieszańcowa": "motylkowe pastewne"})
    tr3, te3 = d3[d3.test == 0], d3[d3.test == 1]
    las3 = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                  random_state=ZIARNO).fit(tr3[dobre],
                                                           tr3["grupa"])
    te3 = te3.assign(pred=las3.predict(te3[dobre]),
                     cx=(te3.x // 10000).astype(int),
                     cy=(te3.y // 10000).astype(int))
    print(f"\nZGODNOSC PO AGREGACJI (komorka 10 km)\n"
          f"{'gatunek':26s}{'F1 piksel':>11}{'r komorka':>11}{'komorek':>9}")
    agr = {}
    from sklearn.metrics import f1_score as f1s
    for g in sorted(te3.grupa.unique()):
        f1 = f1s((te3.grupa == g).astype(int), (te3.pred == g).astype(int))
        a = te3.groupby(["cx", "cy"]).apply(
            lambda s: pd.Series({"p": (s.pred == g).sum(),
                                 "t": (s.grupa == g).sum()}),
            include_groups=False)
        a = a[a.sum(axis=1) > 0]
        r = (float(np.corrcoef(a.p, a.t)[0, 1])
             if len(a) > 3 and a.p.std() > 0 else float("nan"))
        agr[g] = {"f1_piksel": f1, "r_komorka": r, "komorek": int(len(a))}
        print(f"{g[:24]:26s}{f1:>11.3f}{r:>11.3f}{len(a):>9}")

    prog_r = 0.85
    ok = [n for n, w in agr.items() if w["r_komorka"] >= prog_r and n != "inne"]
    pok = sum(CUKIER.get(n, 0) for n in ok)
    if "motylkowe pastewne" in ok:
        pok += CUKIER["koniczyna czerwona"] + CUKIER["lucerna mieszańcowa"]
    print(f"\nklasy z r >= {prog_r} w komorce: {', '.join(sorted(ok))}")
    print(f"pokrycie cukru przez nie: {pok:.1f}%")

    (WYNIKI / "json" / "wielo_diagnoza.json").write_text(json.dumps({
        "warianty_f1_makro": {"A_jak_bylo": fA, "B_scalone": fB,
                              "C_bez_pustych_okien": fC, "D_obie": fD},
        "okna_odrzucone": [c for c in kol if zer[c] > MAX_ZER],
        "scalone": SCAL, "odrzucone": ODRZUC,
        "wyniki_D": wD, "binarny_rzepak": {"precyzja": pr, "czulosc": cz},
        "agregacja_10km": agr, "klasy_powyzej_progu": ok,
        "pokrycie_cukru_pct": pok, "prog_r": prog_r,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("zapisano wielo_diagnoza.json")
