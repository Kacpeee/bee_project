# Programowanie Aplikacji Geoinformatycznych - Szablon Projektu

Gotowy do uruchomienia szablon aplikacji geoinformatycznej oparty na otwartych technologiach.
Studenci rozwijaja projekt, podmieniajac dane przykladowe na wlasne i rozszerzajac kod.

## Technologie

| Technologia | Rola |
|-------------|------|
| **FastAPI** | REST API backendu |
| **PostGIS** | Baza danych przestrzennych (dane wektorowe) |
| **pgSTAC** | Rozszerzenie PostgreSQL do katalogu STAC |
| **stac-fastapi** | Serwer STAC API (OGC STAC 1.0) |
| **TiTiler** | Serwowanie kafli rastrowych z plikow COG |
| **tipg** | Serwowanie kafli wektorowych MVT z PostGIS |
| **Streamlit** | Interfejs uzytkownika z mapa MapLibre GL |
| **Docker + UV** | Konteneryzacja i zarzadzanie srodowiskiem Python |

## Architektura

```
Przegladarka
    |
    +-- MapLibre JS (kafle MVT) --> tipg :8083 --> PostGIS
    +-- MapLibre JS (kafle XYZ) --> TiTiler :8082 --> COG (URL)
    |
Streamlit :8502
    |
    +-- httpx --> FastAPI :8000 --> PostGIS
    +-- httpx --> STAC API :8088 --> PostGIS (pgSTAC)
```

## Wymagania

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Make](https://www.gnu.org/software/make/) (Windows: `choco install make` lub Git Bash)

## Szybki start

```bash
# 1. Sklonuj repozytorium
git clone <url>
cd python1-project

# 2. Skopiuj plik konfiguracyjny
cp .env.example .env

# 3. Zbuduj i uruchom serwisy
make build
make up

# 4. Poczekaj ~30 sekund, sprawdz status
make ps

# 5. Otworz aplikacje
# Streamlit:  http://localhost:8502
# FastAPI:    http://localhost:8000/docs
# STAC API:   http://localhost:8088
# TiTiler:    http://localhost:8082/docs
# tipg:       http://localhost:8083
```

> **Uwaga:** Serwis `db-init` zaladuje dane przykladowe przy pierwszym uruchomieniu i zakonczy sie automatycznie (status `Exited 0`).

## Dostepne komendy Make

```bash
make up        # Uruchom serwisy w tle
make down      # Zatrzymaj serwisy
make build     # Zbuduj obrazy Dockera
make logs      # Sledz logi (Ctrl+C aby wyjsc)
make ps        # Status serwisow
make reset     # Zatrzymaj i usun dane (volumes) - UWAGA: kasuje baze
make shell-db  # Otworz powloke psql
```

## Struktura projektu

```
python1-project/
|
|- docker-compose.yml          # Definicja wszystkich serwisow
|- .env.example                # Przykladowe zmienne srodowiskowe
|- Makefile                    # Skroty do czesto uzywanych komend
|
|- data/                       # Dane przykladowe (zastap swoimi!)
|   |- sample_features.geojson # Punkty Krakowa -> PostGIS
|   |- stac_collection.json    # Definicja kolekcji STAC
|   +- stac_items.json         # Itemy STAC z linkami do COG
|
|- scripts/                    # Jednorazowe ladowanie danych (db-init)
|   |- ingest_data.py          # Glowny skrypt ingestion
|   |- Dockerfile
|   +- pyproject.toml
|
|- backend/                    # FastAPI - tu piszesz logike biznesowa
|   |- src/app/
|   |   |- main.py             # Konfiguracja aplikacji
|   |   |- config.py           # Zmienne srodowiskowe (pydantic-settings)
|   |   |- database.py         # Klasa Database (asyncpg)
|   |   |- models.py           # Modele danych (Pydantic)
|   |   |- dependencies.py     # Dependency injection (get_db)
|   |   +- routers/
|   |       |- health.py       # GET /health
|   |       +- locations.py    # CRUD dla lokalizacji
|   |- Dockerfile
|   +- pyproject.toml
|
|- frontend/                   # Streamlit - tu piszesz UI
|   |- src/
|   |   |- app.py              # Glowna aplikacja Streamlit
|   |   +- config.py           # Adresy serwisow
|   |- Dockerfile
|   +- pyproject.toml
|
|- stac-api/                   # stac-fastapi-pgstac (minimalna konfiguracja)
|   |- main.py
|   |- Dockerfile
|   +- pyproject.toml
|
+- tipg/                       # tipg - serwer kafli wektorowych
    |- Dockerfile
    +- pyproject.toml
```

## Jak rozszerzyc projekt

### 1. Podmien dane

Edytuj lub zastap pliki w `data/`:
- `sample_features.geojson` - twoje dane wektorowe (GeoJSON)
- `stac_collection.json` - definicja kolekcji STAC
- `stac_items.json` - linki do twoich plikow COG

Zmodyfikuj `scripts/ingest_data.py` - klasa `DataIngester`:
- `_setup_tables()` - schemat tabel
- `_load_vector_data()` - ladowanie danych wektorowych
- `_load_stac_catalog()` - ladowanie katalogu STAC

Przeladuj dane:
```bash
make reset   # usuwa baze
make up      # uruchamia ponownie z nowa baza i odswiezonym db-init
```

### 2. Dodaj nowy endpoint w FastAPI

Stwórz plik `backend/src/app/routers/moj_router.py`:

```python
from fastapi import APIRouter, Depends
from ..database import Database
from ..dependencies import get_db

router = APIRouter()

@router.get("/moje-dane")
async def get_moje_dane(db: Database = Depends(get_db)) -> list:
    rows = await db.fetch("SELECT * FROM app.moja_tabela")
    return [dict(row) for row in rows]
```

Zarejestruj router w `backend/src/app/main.py`:
```python
from .routers import moj_router
app.include_router(moj_router.router, prefix="/moje-dane", tags=["moje-dane"])
```

Dzieki `--reload` zmiany sa widoczne natychmiast (bez przebudowy obrazu).

### 3. Rozszerz mape w Streamlit

Edytuj `frontend/src/app.py`. Przyklad dodania nowej warstwy wektorowej:

```python
m.add_source("moja-warstwa", VectorTileSource(
    tiles=[f"{settings.public_tipg_url}/collections/app.moja_tabela/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}"]
))
m.add_layer(Layer(
    type=LayerType.FILL,
    id="moja-warstwa-fill",
    source="moja-warstwa",
    source_layer="default",  # tipg zawsze uzywa nazwy "default" w MVT
    paint={"fill-color": "#4264fb", "fill-opacity": 0.5},
))
```

## Serwisy - szczegoly

### PostGIS + pgSTAC (`:5432`)
Baza danych PostgreSQL z rozszerzeniami PostGIS (dane przestrzenne) i pgSTAC (katalog STAC).
Schemat `app` przechowuje dane aplikacji. Schemat `pgstac` - dane katalogu STAC.

### STAC API (`:8088`)
Implementacja OGC STAC API 1.0. Endpointy:
- `GET /collections` - lista kolekcji
- `GET /collections/{id}/items` - lista itemow
- `POST /search` - wyszukiwanie przestrzenne i temporalne

### TiTiler (`:8082`)
Dynamiczny serwer kafli rastrowych dla plikow Cloud Optimized GeoTIFF (COG).
Przyklady: `/cog/info?url=...`, `/cog/tiles/{z}/{x}/{y}?url=...`

### tipg (`:8083`)
Serwer kafli wektorowych MVT bezposrednio z tabel PostGIS (schemat `app`).
Endpointy OGC API Features + Tiles. Tabele sa odkrywane automatycznie.

### FastAPI (`:8000`)
Backend REST API z automatyczna dokumentacja Swagger UI pod `/docs`.

### Streamlit (`:8502`)
Frontend z mapa MapLibre GL, przegladarka STAC i informacje o projekcie.

## Zmienne srodowiskowe

Plik `.env` (skopiowany z `.env.example`):

```
POSTGRES_USER=geoapp      # uzytkownik bazy danych
POSTGRES_PASSWORD=geoapp  # haslo
POSTGRES_DB=geoapp        # nazwa bazy
```

---

## Opis mojego projektu - optymalizacja mobilnego pszczelarstwa (woj. lubelskie)

Projekt zaliczeniowy oparty na powyzszym szablonie. Aplikacja wspiera mobilne
pszczelarstwo poprzez analize kwitnienia wierzby iwy w oparciu o dane stacji
pogodowych i obszary Voronoi w wojewodztwie lubelskim.

### Temat

Pszczelarz mobilny przemieszcza ule miedzy pasiekami w zaleznosci od kwitnienia
roslin miododajnych. Aplikacja pokazuje:

- strefy wplywu stacji pogodowych (komorki Voronoi PME/IUNG),
- faze kwitnienia wierzby iwy (GDD od 1 stycznia, zakres 100-200),
- model terenu (Copernicus DEM 30 m) jako warstwe rastrowa.

### Uzyte dane

| Plik | Opis |
|------|------|
| `data/lubelskie_edwin_voronoi.geojson` | 42 stref wokol stacji pogodowych (polygon) |
| `data/honey_plants.json` | Slownik roslin miododajnych (na razie: wierzba iwa) |
| `data/station_temperatures_2025.csv` | Temperatury dzienne stacji (01.01-28.06.2025) |
| `data/station_gdd_cache.csv` | Obliczone GDD i fazy kwitnienia wierzby iwy |
| `data/stac_collection.json` | Kolekcja STAC: `lubelskie-dem` |
| `data/stac_items.json` | Kafle Copernicus DEM GLO-30 (N50/N51, E021-E023) |

Zrodlo temperatur: API Edwin (dane zapisane lokalnie w CSV).

### Zmiany w kodzie (wzgledem szablonu)

| Plik | Co zostalo zmienione |
|------|----------------------|
| `scripts/ingest_data.py` | Ladowanie Voronoi, roslin, temperatur i GDD do PostGIS |
| `backend/src/app/routers/cells.py` | Endpointy stacji i `ST_Contains` |
| `backend/src/app/routers/blooming.py` | Endpoint fazy kwitnienia |
| `frontend/src/app.py` | Mapa Lubelskiego, zakladka Kwitnienie |

### Endpointy FastAPI (moj projekt)

- `GET /cells/stations` - lista stacji pogodowych
- `GET /cells/at-point?lon=&lat=` - znajdz strefe dla punktu (`ST_Contains`)
- `GET /blooming/?station_id=&date=&plant_id=salix_caprea` - faza kwitnienia

### Przeladowanie danych po zmianach

```bash
docker compose run --rm db-init
```

### Dalszy rozwoj

- Dodanie kolejnych roslin miododajnych (rzepak, gryka, facelia)
- Pobranie temperatur dla 14 brakujacych stacji z API Edwin
- Kolorowanie mapy wg fazy kwitnienia na wybrana date
