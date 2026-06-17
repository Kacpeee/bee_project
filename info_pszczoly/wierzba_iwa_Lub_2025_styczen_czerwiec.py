import plotly.express as px
import json
import pandas as pd

print("\nGenerowanie animowanej mapy...")

# 1. Wczytanie Twojego pliku GeoJSON
sciezka_geojson = "lubelskie_edwin_voronoi.geojson"
df_wynik=pd.read_csv("polaczone_wyniki_wierzba_polrocze.csv")

with open(sciezka_geojson, 'r', encoding='utf-8') as f:
    woj_lubelskie_geojson = json.load(f)

# 2. Tworzenie kolumny tekstowej z fazą rozwoju (dla ładnej legendy)
def przypisz_faze(gdd):
    if gdd < 100:
        return '1. Przed kwitnieniem (Uśpienie)'
    elif 100 <= gdd <= 200:
        return '2. Kwitnienie'
    else:
        return '3. Po kwitnieniu (Przekwitanie)'

df_wynik['Faza_rozwoju'] = df_wynik['Wierzba_iwa_GDD_suma'].apply(przypisz_faze)

# Plotly wymaga daty w formie tekstu do osi czasu animacji
df_wynik['data_animacji'] = df_wynik['data_dnia'].astype(str) 

# Zabezpieczenie: sortowanie, aby klatki animacji szły chronologicznie
df_wynik = df_wynik.sort_values('data_animacji')

