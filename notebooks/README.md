# OOI seafloor data — exploration notebooks (intern-friendly)

A guided, **teach-from-zero** tour of the OOI seafloor mSEED data. No prior
oceanography, seismology, or signal processing assumed. Notebooks 00→04 cover the
**pressure-gauge / tide** dataset in order; notebook 05 covers the
**current-meter** dataset. Each notebook has:

- 🎯 **learning objectives** up top,
- plain-language **concept primers** before every technique,
- **commented code**,
- 👀 **"what you're seeing"** notes after each plot,
- 📖 **key-term** callouts and a glossary (end of notebook 00),
- ✏️ **"try it yourself"** exercises and a recap.

All notebooks share helpers in **`oceanlib.py`**.

## What the data actually is — TWO separate datasets

**1. `tidal/` — the pressure-gauge dataset** (location code `10`, flat folder).
Originally shipped duplicated as `currentmeter/` too, but those were byte-identical
copies; the duplicate has since been removed. Two channels per station:

| channel | variable | units | used for |
|---------|----------|-------|----------|
| `*DO` (UDO/LDO) | seafloor **pressure** | **dbar** (≈ m of sea level) | tides / sea level |
| `*K1` (UK1/LK1) | **temperature** | °C | bottom-water temp |

Band letter = sample interval (**U ≈ 15 s, L = 1 s**); some stations have both.
Stations: **AXBA1** (Axial Base), **HYSB1** (Slope Base), **HYS14**; 2014–2025.

**2. `currentmeter/` — the current-meter dataset** (location code `20`, in
`currentmeter/<year>/` subfolders). A 3-component water **velocity** record:

| channel | variable | units |
|---------|----------|-------|
| `LOE` / `LON` / `LOZ` | velocity **east / north / up** | m/s |
| `LKO` | temperature | °C |

> ⚠️ **Partial download.** The current-meter data is currently almost entirely
> **HYSB1**; more stations will arrive later. The notebook and helpers
> **discover available stations automatically**, so they'll pick up new data with
> no edits. The loader also applies QC (masks speeds > `ol.CUR_QC_MAX` = 3 m/s as
> fill/spikes — e.g. 2016 has ~19% bad samples).

## Notebooks (run in order, or independently)

| # | file | what it does |
|---|------|--------------|
| 00 | `00_dataset_overview.ipynb` | catalog, coverage map, files/year, channel inventory |
| 01 | `01_signals_separately.ipynb` | each variable alone — one-day (native rate) + long-term (decimated) |
| 02 | `02_signals_together.ipynb` | pressure & temperature together — twin-axis, stacked, correlation |
| 03 | `03_daily_plots.ipynb` | day grid, daily overlay, hour-vs-date heatmap (spring–neap) |
| 04 | `04_detide_harmonic_analysis.ipynb` | **remove the tide** via least-squares harmonic analysis (Thomson & Emery) |
| 05 | `05_current_meter.ipynb` | **current-meter velocity** — components, speed/direction, stick & progressive-vector plots, current rose, current-vs-tide |
| 06 | `06_tide_current_relationship.ipynb` | **relate tide & currents** — principal-axis current, overlay, lagged cross-correlation, coherence/phase spectrum, per-constituent phase lag |

Figures are written to `../figures/`. Build one notebook without disturbing the
others' executed outputs: `python _build_notebooks.py 05_current_meter.ipynb`.

## Tide removal (notebook 04)

Implements classical harmonic analysis from Thomson & Emery, *Data Analysis
Methods in Physical Oceanography* (Ch. 5): fit a fixed set of astronomical
constituents (M2, S2, N2, K1, O1, …) by least squares, predict the tide, and
subtract it to get the non-tidal residual. Pure NumPy — no extra packages. If
`utide` is installed (`pip install utide`) the notebook also cross-checks
against it (utide = the packaged Foreman/Pawlowicz version of the same method).

## Helper API (`oceanlib.py`)

```python
import oceanlib as ol
# --- pressure-gauge / tide dataset (tidal/) ---
ol.build_catalog()                              # DataFrame, one row per file
ol.load_series(sta, var, start, end)            # full-rate pandas Series
ol.load_decimated(sta, var, start, end, "1h")   # resample-while-loading (long spans)
ol.channels_for(sta, var)                        # available channel codes + counts
ol.DEMO                                          # long gap-free windows per station

# --- current-meter dataset (currentmeter/) ---
ol.current_stations()                            # stations with velocity data (auto-discovered)
ol.primary_current_station()                     # station with the most data (good default)
ol.current_window(sta)                           # a clean gap-free window for that station
ol.load_current(sta, start, end, rule="10min")   # DataFrame: east/north/up/speed/dir (+QC)

# --- analysis helpers (shared) ---
ol.harmonic_fit(series, constituents=None)        # least-squares tidal fit -> amps/phases/tide/residual
ol.principal_axis(east, north)                    # current's main axis -> (unit_vec, orient_deg, projection)
```

`var` is `"pressure"` or `"temperature"`. Loaders return **physical units** —
pressure in **dbar** (≈ metres of sea level; raw counts ÷ `ol.COUNTS_PER_DBAR`,
a factor verified against the sites' known depths and the ~0.83 m M2 tide),
temperature in **°C**, current velocity in **m/s**. Pass `raw=True` to get
instrument counts; `channel="UDO"`/`"LDO"` to pick a band; `qc_max=None` to
disable current-speed QC.

`load_current` returns columns `east`/`north`/`up` (m/s, can be negative),
`speed` (horizontal), and `dir` (compass degrees the flow heads *toward*). It
auto-discovers stations and applies QC, so it scales to new downloads with no
code changes.

To regenerate all notebooks: `python _build_notebooks.py`. To rebuild just one
(without wiping others' outputs): `python _build_notebooks.py 05_current_meter.ipynb`.
