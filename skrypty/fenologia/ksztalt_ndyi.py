"""
Szerokosc okna kwitnienia rzepaku z wieloletnich krzywych NDYI.

DLACZEGO NIE STALA Z 2022
-10/+12 dni bylo zmierzone na JEDNEJ krzywej. Pozostale sezony maja luki
w chmurach i ogony, wiec nie wolno zalozyc, ze kazdy rok uklada sie tak samo.

CO JEST LICZONE
Dla kazdego sezonu: ile dni od piku NDYI do polowy jego wysokosci, w gore
i w dol osobno. Interpolacja tylko miedzy sasiednimi przelotami; jesli luka
> 12 dni, ramie odpada (nie zgadujemy przez chmury). Wynik: mediana lat
z pomiarem ramienia, zaokraglona do pelnego dnia.

To NADAL nie jest krzywa nektaru. To szerokosc zoltego piku na Sentinelu,
mierzona na wielu latach zamiast na jednym.

Uruchomienie (bez GEE, na istniejącym fenologia.json):
    python ksztalt_ndyi.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
PROG_SZCZYTU = 0.5
MAX_LUKA_DNI = 12


def _ramie(xs: np.ndarray, ys: np.ndarray, pik: float, ymax: float,
           strona: int, f: float, max_luka: int) -> float | None:
    """Dni od piku do przeciecia f*ymax. strona -1 = przed, +1 = po."""
    prog = f * ymax
    if strona < 0:
        m = xs <= pik
        xx, yy = xs[m][::-1], ys[m][::-1]
    else:
        m = xs >= pik
        xx, yy = xs[m], ys[m]
    if len(xx) == 0:
        return None
    prev_x, prev_y = float(pik), float(ymax)
    for x, y in zip(xx, yy):
        if abs(x - prev_x) > max_luka:
            return None
        if y < prog:
            if prev_y == y:
                return abs(x - pik)
            t = (prev_y - prog) / (prev_y - y)
            return abs(prev_x + t * (x - prev_x) - pik)
        prev_x, prev_y = float(x), float(y)
    return None


def ksztalt_z_krzywych(krzywe: dict, obs: dict,
                       f: float = PROG_SZCZYTU,
                       max_luka: int = MAX_LUKA_DNI) -> dict:
    per_rok = {}
    przed, po = [], []
    for rok in sorted(int(r) for r in krzywe):
        kr = krzywe[str(rok)] if str(rok) in krzywe else krzywe[rok]
        pik = float(obs[str(rok)] if str(rok) in obs else obs[rok])
        scal: dict[int, list[float]] = {}
        for v in kr:
            scal.setdefault(int(v["doy"]), []).append(v["nadwyzka"])
        xs = np.array(sorted(scal), float)
        ys = np.array([float(np.mean(scal[int(x)])) for x in xs])
        ymax = float(ys.max()) if len(ys) else 0.0
        u = p = None
        if ymax > 0:
            u = _ramie(xs, ys, pik, ymax, -1, f, max_luka)
            p = _ramie(xs, ys, pik, ymax, +1, f, max_luka)
        per_rok[str(rok)] = {
            "przed": None if u is None else round(float(u), 1),
            "po": None if p is None else round(float(p), 1),
        }
        if u is not None:
            przed.append(float(u))
        if p is not None:
            po.append(float(p))
    if not przed or not po:
        raise SystemExit("za malo ramion NDYI do mediany okna")
    md_przed, md_po = float(np.median(przed)), float(np.median(po))
    return {
        "przed_pelnia": int(round(md_przed)),
        "po_pelni": int(round(md_po)),
        "mediany_dni": {"przed": round(md_przed, 1), "po": round(md_po, 1)},
        "zakres_dni": {
            "przed": [round(min(przed), 1), round(max(przed), 1)],
            "po": [round(min(po), 1), round(max(po), 1)],
        },
        "n_przed": len(przed),
        "n_po": len(po),
        "prog_szczytu": f,
        "max_luka_dni": max_luka,
        "per_rok": per_rok,
        "metoda": "polowa szczytu nadwyzki NDYI; interpolacja tylko przy luce "
                  f"≤{max_luka} dni; mediana lat z pomiarem ramienia "
                  "(nie stala z 2022)",
    }


if __name__ == "__main__":
    fen_p = WYNIKI / "json" / "fenologia.json"
    fen = json.loads(fen_p.read_text(encoding="utf-8"))
    k = ksztalt_z_krzywych(fen["krzywe"], fen["obserwacje"])
    fen["ksztalt_kwitnienia"] = k
    fen_p.write_text(json.dumps(fen, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"okno rzepaku: -{k['przed_pelnia']} / +{k['po_pelni']} dni "
          f"(mediana NDYI, n_przed={k['n_przed']}, n_po={k['n_po']})")
    print(f"  zakres przed {k['zakres_dni']['przed']}, "
          f"po {k['zakres_dni']['po']}")
    for rok, v in k["per_rok"].items():
        znacznik = "ok" if v["przed"] is not None and v["po"] is not None \
            else "luka"
        print(f"  {rok}: przed={v['przed']}  po={v['po']}  {znacznik}")

    gdd_p = WYNIKI / "json" / "gdd.json"
    if gdd_p.exists():
        gdd = json.loads(gdd_p.read_text(encoding="utf-8"))
        gdd["ksztalt_kwitnienia"] = {
            "przed_pelnia": k["przed_pelnia"],
            "po_pelni": k["po_pelni"],
            "zrodlo": "fenologia.json, mediana NDYI wielu lat",
        }
        gdd_p.write_text(json.dumps(gdd, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print(f"zapisano {fen_p.name} i {gdd_p.name}")
    else:
        print(f"zapisano {fen_p.name}")
