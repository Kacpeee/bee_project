# Apiary Siting Model — Lubelskie Voivodeship

Finds **where to place a beehive** and **when the rapeseed will bloom**, from
farmer crop declarations, Sentinel-1/2 detection and a thermal phenology model.
Covers the whole voivodeship on a 100 m grid (1 px = 1 ha).

> Provenance of every parameter, plus the negative results, is in
> [ZRODLA.md](ZRODLA.md) *(Polish)*.

---

## Open it

**Open `index.html`.** Nothing to install — the pages run straight from disk,
including from a copied folder or a USB stick. Maps and charts are embedded in
the files, so nothing breaks when you email them.

| page | what it shows | needs internet |
|---|---|---|
| `index.html` | entry point | no |
| `prognoza.html` | when rapeseed blooms at a chosen spot | **yes** — live weather |
| `kalendarz.html` | what blooms when, per district | no |
| `raport.html` | full results, validation, caveats | no |
| `mechanika.html` | step by step, where the numbers come from | no |

The forecast page **computes in your browser** — the thermal model is ported to
JavaScript, weather comes from Open-Meteo. Agreement with the Python original is
tested, not assumed: `test_rownowaznosc.py` runs the same points through both.
It already caught one real divergence — Python rounds halves to even,
JavaScript rounds them up, which sent the two into different weather cells.

---

## What it computes — and what it does not

**It computes nectar-sugar potential** — how much sugar a bee starting at a
given point can actually reach, weighted by distance through an exponential
kernel calibrated on measured waggle-dance distances (Couvillon et al. 2014):
1.2 km in spring, 5.1 km in summer.

**It is not a honey-yield forecast.** Colony strength, competing apiaries and
siting permissions all sit between potential and harvest, and the model has
none of them. It **has never been validated against a real harvest** — the
largest open gap.

**Learned components cover rapeseed only** — about half the voivodeship's
nectar sugar, and the only species with its own bloom-date model. Everything
else uses fixed literature windows, because timing depends on an unknown
sowing date.

---

## Results

All figures are spatial-block cross-validation (2.5 km blocks) or
leave-one-out, never in-sample.

### Which crop is in the field

| sensor | F1-macro | features |
|---|---|---|
| Sentinel-2 only | 0.683 | 44 |
| Sentinel-1 only | 0.585 | 78 |
| **both** | **0.718** | 122 |

Radar carries **52.9%** of model importance. Its real advantage is coverage:
**zero empty half-month windows against eight for optics** — in the first half
of January, 100% of points have no cloud-free scene at all.

| species | F1 | note |
|---|---|---|
| **winter rapeseed** | **0.940** | three unmistakable signals a year: green rosette in winter, yellow in May, stubble in July |
| runner bean | 0.922 | |
| permanent grassland | 0.725 | radar lifts it from 0.593 — it sees the mowing |
| sunflower | 0.605 | spring-sown |
| buckwheat | 0.583 | spring-sown; looks like any fresh field for months |

### Parcel centre or pixel?

The F1 above is measured at **one representative point inside each parcel**.
Deployment classifies **every** pixel, edges included. Measured on 18,489
held-out pixels (model trained only on training blocks, cereals included):

| level | precision | recall | F1 |
|---|---|---|---|
| parcel centre | 0.938 | 0.942 | **0.940** |
| single pixel, balanced sample | 0.790 | 0.872 | 0.829 |
| single pixel, **real crop proportions** | 0.528 | 0.872 | **0.658** |

At real prevalence roughly **every second pixel called rapeseed is not
rapeseed** — 87% of farmland is something else, mostly cereals, so even a low
per-pixel error rate produces many false positives. Recall is unaffected, as
it should be.

Almost all of that error sits at the field boundary:

| distance from parcel edge | pixels | F1 |
|---|---|---|
| **0–10 m** | 12,152 | **0.762** |
| 10–20 m | 4,410 | 0.917 |
| 20–40 m | 1,651 | 0.975 |
| > 40 m | 276 | 1.000 |

**66% of pixels lie within 10 m of a boundary** — parcels here are narrow
strips, and a 10 m Sentinel pixel on a boundary physically contains two crops.
This is why the maps never use raw pixels: everything is blurred by flight
range and area-calibrated first, and after blurring the density agreement is
r = 0.940.

### When it blooms

Growing-degree days above **1.5 °C**, accumulated from **15 March**, bloom at
**430 GDD**.

| metric | result |
|---|---|
| **RMSE, leave-one-out** | **3.21 days** *(n = 145, 19 areas, 9 seasons)* |
| in-sample RMSE | 3.15 days |
| baseline "always the average date" | 7.3 days |

The sample was tripled from 7 to 19 areas to test whether this was an artefact
of site choice. It was not: same error, same parameters.

**In-season forecasting** only becomes useful late — April decides the date:

| decision day | lead time | RMSE |
|---|---|---|
| 15 Feb – 1 Apr | 6–12 weeks | 6.8–7.3 d |
| 15 Apr | 4 weeks | 4.5 d |
| **1 May** | **2 weeks** | **3.4 d** |

### Where it will be, before it blooms

Truncating features to the decision day still finds rapeseed months ahead —
**93% of full-season accuracy six weeks before bloom**. This is also what keeps
the bloom date from being learned circularly from the bloom itself.

| data through | lead time | F1 rapeseed |
|---|---|---|
| December | ~5 months | 0.826 |
| February | ~10 weeks | 0.840 |
| **March** | **~6 weeks** | **0.869** |
| whole season | after the fact | 0.939 |

### Independent checks

| check | result |
|---|---|
| detection vs ARiMR declarations, 2025 | r = 0.948 |
| detection vs EUCROPMAP, 2022 | r = 0.918 |
| ERA5 vs IMGW Zamość weather station | RMSE 1.13 K, r = 0.986 |

---

## Rebuilding

```bash
python skrypty/serwis/eksport_paczka.py     # build all pages + navigation + index
python skrypty/serwis/test_strony.py        # do they open from disk without JS errors
python skrypty/serwis/test_rownowaznosc.py  # does the JS match Python
```

An optional Flask service (`bash skrypty/serwis/restart.sh`, port 8000) adds a
`/prognoza?lat=&lon=` API. **It needs the full 4.6 GB of inputs**, which this
repository does not carry — a fresh clone runs the static pages, not the service.

<details>
<summary><b>Full processing pipeline</b> — order matters, each step reads the previous one's cache</summary>

```bash
# Phenology
python skrypty/fenologia/meteo_gdd.py           # weather 2000-2026, first GDD threshold
python skrypty/fenologia/fenologia_wielo.py     # bloom dates, 19 areas (long, resumable)
python skrypty/fenologia/walidacja_krzyzowa.py  # leave-one-out
python skrypty/fenologia/fenologia_final.py     # final model: base 1.5, 15 III, 430

# Multi-species detection (Sentinel-1 + Sentinel-2)
python skrypty/detekcja/klasyfikator_wielo.py   # 21k parcels + S2 features, ~70 min GEE
python skrypty/detekcja/wielo_diagnoza.py       # label merging
python skrypty/detekcja/wielo_s1s2.py           # does radar help
python skrypty/detekcja/wielo_lata.py           # maps 2019-2024
python skrypty/detekcja/kalibracja_arealowa.py  # area calibration + EUCROPMAP check

# Potential maps
python skrypty/potencjal/wojewodztwo.py         # 100 m grid, convolution
python skrypty/potencjal/sredni_rok.py          # typical year + reliability layer
python skrypty/potencjal/najlepsze_punkty.py    # 12 best locations

# Outputs
python skrypty/kalendarz/eksport_interaktywny.py
python skrypty/raport/raport_buduj.py
python skrypty/raport/mechanika.py
```

`wielo_lata.py` writes a model into `projects/<project>/assets/modele/`; create
that folder once in the Earth Engine Code Editor, or the export fails with
"Asset does not exist".

</details>

### Requirements

```bash
pip install earthengine-api geopandas pyogrio rasterio scipy matplotlib requests
earthengine authenticate
```

Earth Engine project id goes in `.ee_projekt`.

---

## Input data

| source | span | note |
|---|---|---|
| ARiMR GSA crop declarations | 2025, 2026 | only two years are published — hence the satellite work |
| Sentinel-2 L2A | 2018–2026 | Earth Engine |
| Sentinel-1 GRD | 2018–2026 | IW, descending, VV+VH |
| EUCROPMAP (JRC) | 2018, 2022 | independent cross-check |
| ERA5 via Open-Meteo | 2000–2026 | |
| ESA WorldCover | 2021 | arable mask |

`dane/` (3.9 GB) and `wyniki/cache/` are not versioned. The detection cache
`woj_prawd_*.npy` represents ~10 hours of Earth Engine compute — do not delete it.

---

## Limitations worth knowing

- **Declarations exist for 2025 and 2026 only.** Everything multi-year rests on
  satellite detection, and the satellite layer is 84% rapeseed by sugar — it is
  not an independent second opinion, it is rapeseed plus 16%.
- **Phenology is dynamic for rapeseed only.** Spring-sown crops get fixed
  literature dates out of necessity, so the width of the June gap is partly an
  artefact.
- **The series starts in 2018** with Sentinel-2; earlier years are
  extrapolation. MODIS is too coarse (500 m vs 1.16 ha median parcel), Landsat
  too sparse — both tested.
- **"Observations" are satellite-derived**, not field BBCH records, so the
  3.21-day RMSE measures agreement with remote-sensing phenology.
- **Pixel-level detection is weaker than regional** (~0.7 precision at 100 m);
  maps use it only after blurring by flight range.

## What is missing

**Validation against a real honey harvest** — by far the biggest gap — plus
competition from existing apiaries, and a bloom model for species other than
rapeseed.

**Nectar crops not yet in the map.** The declarations cover 1,513,132 parcels
and 513 distinct crops, so per-pixel ground truth exists for all of them; the
map uses 16. A scan of the rest found **25 nectar-relevant crops with at least
300 parcels**, enough to train on:

| crop | parcels |
|---|---|
| **phacelia** | 3,712 |
| pumpkin (oil + common) | 9,644 |
| strawberry | 9,580 |
| chokeberry | 7,749 |
| highbush blueberry | 2,025 |

Phacelia is the clearest omission — it is sown deliberately *for bees*, has a
well-documented yield, and appears nowhere in `ZRODLA.md`, so it was never
weighed and rejected, just missed. Some of the others (apple, cherry, plum,
pear) are probably already inside the single `Sad` orchard class.

Adding them is limited by the project rule that a species enters the map only
with a documented kg-of-sugar-per-hectare figure — not by data availability.
More classes would also not raise detection quality: buckwheat and sunflower
already sit at F1 0.58–0.61 with 1,400 training parcels each, because
spring-sown crops look like bare soil for half the season.
