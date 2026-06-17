"""
Obrobka danych meteo i GDD wierzby iwy.

Wejscie:  historia_meteo_2024_2025.csv (temperatury dzienne stacji)
Wyjscie:  polaczone_wyniki_wierzba_polrocze.csv  (analiza / mapy)
           ../data/station_temperatures.csv       (do db-init)
           ../data/station_gdd_cache.csv          (do db-init)
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "data"

METEO_INPUT = ROOT / "historia_meteo_2024_2025.csv"
WYNIKI_OUTPUT = ROOT / "polaczone_wyniki_wierzba_polrocze.csv"
STATION_DAILY_OUTPUT = DATA_DIR / "station_temperatures.csv"
STATION_GDD_OUTPUT = DATA_DIR / "station_gdd_cache.csv"

PLANT_ID = "salix_caprea"
SALIX_BASE = 5.0
GDD_MIN = 100.0
GDD_MAX = 200.0


def przypisz_faze(gdd: float) -> str:
    if gdd < GDD_MIN:
        return "before"
    if gdd <= GDD_MAX:
        return "blooming"
    return "after"


def main() -> None:
    if not METEO_INPUT.exists():
        raise FileNotFoundError(f"Brak pliku wejsciowego: {METEO_INPUT}")

    print(f"Wczytuje dane meteo: {METEO_INPUT}")
    df = pd.read_csv(METEO_INPUT)
    df["data_dnia"] = pd.to_datetime(df["data_dnia"]).dt.date
    df = df.sort_values(["stationId", "data_dnia"]).reset_index(drop=True)

    print(
        f"  stacji: {df['stationId'].nunique()}, "
        f"dni: {len(df)}, "
        f"okres: {df['data_dnia'].min()} - {df['data_dnia'].max()}"
    )

    df["Wierzba_iwa_GDD_dzienne"] = round(
        (df["T_srednia"] - SALIX_BASE).clip(lower=0), 2
    )
    df["rok"] = pd.to_datetime(df["data_dnia"]).dt.year
    df["Wierzba_iwa_GDD_suma"] = (
        df.groupby(["stationId", "rok"])["Wierzba_iwa_GDD_dzienne"]
        .cumsum()
        .round(2)
    )

    df["dzien_kwitniecia"] = 0
    maska_kwitnienia = (df["Wierzba_iwa_GDD_suma"] > GDD_MIN) & (
        df["Wierzba_iwa_GDD_suma"] <= GDD_MAX
    )
    df.loc[maska_kwitnienia, "dzien_kwitniecia"] = (
        df.loc[maska_kwitnienia].groupby(["stationId", "rok"]).cumcount() + 1
    )

    df_wynik = df.drop(columns=["rok"])
    df_wynik.to_csv(WYNIKI_OUTPUT, index=False)
    print(f"Zapisano wyniki analizy: {WYNIKI_OUTPUT}")

    daily = df_wynik.rename(
        columns={
            "stationId": "station_id",
            "data_dnia": "date",
            "T_min": "t_min",
            "T_max": "t_max",
            "T_srednia": "t_mean",
        }
    )[["station_id", "date", "t_min", "t_max", "t_mean"]]
    daily.to_csv(STATION_DAILY_OUTPUT, index=False)
    print(f"Zapisano temperatury do bazy: {STATION_DAILY_OUTPUT}")

    gdd = df_wynik.rename(
        columns={
            "stationId": "station_id",
            "data_dnia": "date",
            "T_min": "t_min",
            "T_max": "t_max",
            "T_srednia": "t_mean",
            "Wierzba_iwa_GDD_dzienne": "gdd_daily",
            "Wierzba_iwa_GDD_suma": "gdd_cumulative",
            "dzien_kwitniecia": "bloom_day",
        }
    )
    gdd["plant_id"] = PLANT_ID
    gdd["bloom_phase"] = gdd["gdd_cumulative"].apply(przypisz_faze)
    gdd = gdd[
        [
            "station_id",
            "plant_id",
            "date",
            "t_min",
            "t_max",
            "t_mean",
            "gdd_daily",
            "gdd_cumulative",
            "bloom_day",
            "bloom_phase",
        ]
    ]
    gdd.to_csv(STATION_GDD_OUTPUT, index=False)
    print(f"Zapisano GDD do bazy: {STATION_GDD_OUTPUT}")

    print("\nPodglad dni kwitnienia (pierwsze 20 wierszy):")
    kwitnienie = df_wynik[df_wynik["dzien_kwitniecia"] > 0]
    if kwitnienie.empty:
        print("Zadna stacja nie osiagnela progu GDD 100-200.")
    else:
        print(
            kwitnienie[
                [
                    "stationId",
                    "data_dnia",
                    "T_srednia",
                    "Wierzba_iwa_GDD_suma",
                    "dzien_kwitniecia",
                ]
            ].head(20)
        )


if __name__ == "__main__":
    main()
