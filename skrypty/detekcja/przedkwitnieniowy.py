"""
ETAP 36 - klasyfikator PRZEDKWITNIENIOWY: gdzie rzepak stoi, zanim zakwitnie.

PO CO
Projekt przewiduje TERMIN kwitnienia (z pogody), ale nie LOKALIZACJE upraw
na nadchodzacy sezon - detekcja wymaga zdjec z sezonu, ktory ma byc
zmapowany, a te powstaja dopiero po fakcie. Pszczelarz dostaje wiec
odpowiedz "kiedy", ale nie "gdzie w tym roku".

DLACZEGO TO MOZE ZADZIALAC
Rzepak OZIMY sieje sie w sierpniu i wrzesniu, zimuje jako zielona rozeta
i rusza z wegetacja w marcu. Jest wiec widoczny na zdjeciach NA DLUGO
przed kwitnieniem - tylko obecny klasyfikator z tego nie korzysta, bo uzywa
okien rozciagnietych na caly rok i musi zobaczyc cala krzywa do konca.

METODA
Ta sama metoda, co przy prognozie fenologicznej: obcinamy cechy do dnia
decyzji i mierzymy, ile skutecznosci zostaje. Okna sa polmiesieczne od
wrzesnia poprzedniego roku (00-01 = IX, 02-03 = X, ... 12-13 = III,
14-15 = IV), wiec:

    do konca XII   okna 00-07    decyzja zimowa
    do konca I     okna 00-09
    do konca II    okna 00-11
    do konca III   okna 00-13    ~6 tygodni przed kwitnieniem
    caly sezon     okna 00-25    stan obecny (po fakcie)

Uruchomienie:
    python skrypty/detekcja/przedkwitnieniowy.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wielo_diagnoza import SCAL, ODRZUC, ZIARNO, DRZEW

WYNIKI = ROOT / "wyniki"
MIES = {7: "XII", 9: "I", 11: "II", 13: "III", 15: "IV", 25: "cały sezon"}


if __name__ == "__main__":
    df = pd.read_csv(WYNIKI / "cache" / "wielo_punkty.csv")
    X2 = pd.read_csv(WYNIKI / "cache" / "wielo_cechy.csv").set_index("i")
    X1 = pd.read_csv(WYNIKI / "cache" / "wielo_cechy_s1.csv").set_index("i")
    X = X2.join(X1, how="inner", rsuffix="_s1")
    d = df.reset_index(drop=True).join(X.sort_index())
    d["etykieta"] = d.etykieta.replace(SCAL)
    d = d[~d.etykieta.isin(ODRZUC)]
    print(f"punktow: {len(d):,}, klas: {d.etykieta.nunique()}")

    def okna_do(k):
        """Cechy z okien 00..k wlacznie, S2 i S1."""
        kol = []
        for c in X.columns:
            if "_" not in c:
                continue
            try:
                nr = int(c.rsplit("_", 1)[-1])
            except ValueError:
                continue
            if nr <= k and c.split("_")[0] in ("ndvi", "ndyi", "vv", "vh", "rat"):
                kol.append(c)
        return kol

    print(f"\n{'dane do':>12}{'okien':>7}{'cech':>7}{'F1-makro':>11}"
          f"{'F1 rzepak':>12}{'wyprzedzenie':>14}")
    wyniki = {}
    for k, et in MIES.items():
        kol = okna_do(k)
        dd = d.dropna(subset=kol)
        tr, te = dd[dd.test == 0], dd[dd.test == 1]
        las = RandomForestClassifier(n_estimators=DRZEW, n_jobs=-1,
                                     random_state=ZIARNO)
        las.fit(tr[kol], tr.etykieta)
        pred = las.predict(te[kol])
        f1m = f1_score(te.etykieta, pred, average="macro")
        maska = te.etykieta == "rzepak ozimy"
        f1r = f1_score(maska, pred == "rzepak ozimy")
        wypr = {7: "~5 mies.", 9: "~4 mies.", 11: "~10 tyg.",
                13: "~6 tyg.", 15: "~2 tyg.", 25: "po fakcie"}[k]
        wyniki[et] = {"okno_do": k, "n_cech": len(kol), "f1_makro": float(f1m),
                      "f1_rzepak": float(f1r), "wyprzedzenie": wypr}
        print(f"{et:>12}{k+1:>7}{len(kol):>7}{f1m:>11.3f}{f1r:>12.3f}{wypr:>14}")

    peln = wyniki["cały sezon"]
    mar = wyniki["III"]
    print(f"\nWNIOSEK")
    print(f"  Rzepak w koncu marca: F1 {mar['f1_rzepak']:.3f} wobec "
          f"{peln['f1_rzepak']:.3f} po calym sezonie "
          f"({mar['f1_rzepak']/peln['f1_rzepak']*100:.0f}% skutecznosci).")
    if mar["f1_rzepak"] >= 0.85 * peln["f1_rzepak"]:
        print("  To wystarcza, zeby wskazac pola rzepaku ok. szesc tygodni")
        print("  przed kwitnieniem - lancuch 'gdzie' + 'kiedy' domyka sie.")
    else:
        print("  Za slabo, zeby oprzec na tym decyzje - potrzebne wiecej okien.")

    (WYNIKI / "json" / "przedkwitnieniowy.json").write_text(json.dumps({
        "pytanie": "ile skutecznosci detekcji zostaje, gdy obetniemy cechy "
                   "do dnia decyzji przed kwitnieniem",
        "okna": "polmiesieczne od IX poprzedniego roku; 12-13 = marzec",
        "wyniki": wyniki,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/przedkwitnieniowy.json")
