"""
ETAP 39 - czy zmiana rewizyty Sentinela-1 tlumaczy niestabilnosc szeregu.

HIPOTEZA
Sentinel-1B ulegl awarii w grudniu 2021 (misje zamknieto w sierpniu 2022),
a Sentinel-1C wystartowal w grudniu 2024. Rewizyta wynosila wiec:

    2019 - XII 2021    1A + 1B     6 dni
    2022 - 2024        tylko 1A   12 dni
    2025 ->            1A + 1C     6 dni

Okna cech sa POLMIESIECZNE. Przy rewizycie 6 dni okno lapie 2-3 przeloty,
przy 12 dniach - jeden, czasem zero. Warstwa radarowa dla lat 2022-2024
jest wiec z definicji rzadsza, a radar odpowiada za 53% waznosci cech.

Czesc niestabilnosci miedzyrocznej przypisalismy "szumowi klasyfikacji" -
byc moze ma ona konkretna, nazywalna przyczyne.

CO SPRAWDZAMY
Liczba scen Sentinel-1 nad wojewodztwem w kazdym sezonie, zestawiona
z odchyleniem arealowym po kalibracji. Jesli lata 2022-2024 maja
systematycznie mniej scen I systematycznie inne areały, hipoteza sie broni.

Uruchomienie:
    python skrypty/detekcja/rewizyta_s1.py
"""
from __future__ import annotations
import json
from pathlib import Path
import ee, numpy as np

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "wyniki"
LATA = range(2019, 2027)
AOI = ee.Geometry.Rectangle([21.5, 50.2, 24.2, 52.3]) if False else None


if __name__ == "__main__":
    ee.Initialize(project=(ROOT / ".ee_projekt").read_text().strip())
    aoi = ee.Geometry.Rectangle([21.5, 50.2, 24.2, 52.3])

    print("DOSTEPNOSC SCEN SENTINEL-1 NAD LUBELSZCZYZNA\n")
    print(f"{'sezon':>7}{'scen IX-IX':>12}{'na okno':>10}{'satelity':>22}")
    dane = {}
    for rok in LATA:
        col = (ee.ImageCollection("COPERNICUS/S1_GRD")
               .filterBounds(aoi)
               .filterDate(f"{rok-1}-09-01", f"{rok}-09-01")
               .filter(ee.Filter.eq("instrumentMode", "IW"))
               .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING")))
        n = int(col.size().getInfo())
        # ktore platformy
        plat = col.aggregate_array("platform_number").distinct().getInfo()
        plat = sorted(set(str(x) for x in plat if x))
        dane[rok] = {"scen": n, "na_okno": round(n / 26, 1),
                     "platformy": plat}
        print(f"{rok:>7}{n:>12}{n/26:>10.1f}{','.join(plat) or '?':>22}")

    print("\nZESTAWIENIE Z ODCHYLENIEM AREALOWYM")
    kal = json.loads((WYNIKI / "json" / "kalibracja_arealowa.json")
                     .read_text(encoding="utf-8"))["areal_po_korekcie"]
    gat = ["rzepak ozimy", "gryka zwyczajna", "malina", "słonecznik"]
    sr = {g: np.mean([kal[str(r)][g] for r in LATA if str(r) in kal])
          for g in gat}
    print(f"\n{'sezon':>7}{'scen':>7}" + "".join(f"{g.split()[0][:9]:>11}" for g in gat))
    odch = {}
    for rok in LATA:
        if str(rok) not in kal:
            continue
        w = [(kal[str(rok)][g] / sr[g] - 1) * 100 for g in gat]
        odch[rok] = w
        print(f"{rok:>7}{dane[rok]['scen']:>7}" +
              "".join(f"{x:>+10.0f}%" for x in w))

    # korelacja: liczba scen a odchylenie bezwzgledne
    print("\nKORELACJA: liczba scen S1 a odchylenie od sredniej")
    for i, g in enumerate(gat):
        x = [dane[r]["scen"] for r in odch]
        y = [abs(odch[r][i]) for r in odch]
        if len(x) > 2 and np.std(x) > 0:
            r = float(np.corrcoef(x, y)[0, 1])
            print(f"  {g[:20]:22s} r = {r:+.3f}")

    lat_malo = [r for r in dane if dane[r]["scen"] < np.median(
        [d["scen"] for d in dane.values()])]
    print(f"\n  sezony ponizej mediany scen: {sorted(lat_malo)}")

    (WYNIKI / "json" / "rewizyta_s1.json").write_text(json.dumps({
        "hipoteza": "zmiana rewizyty S1 (awaria 1B w XII 2021, start 1C "
                    "w XII 2024) tlumaczy czesc niestabilnosci szeregu",
        "sceny_wg_sezonu": dane,
        "odchylenie_arealowe_pct": {str(k): [round(x, 1) for x in v]
                                    for k, v in odch.items()},
        "gatunki": gat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nzapisano json/rewizyta_s1.json")
