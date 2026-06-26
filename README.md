# OOI tides and currents

Exploration of seafloor data from the **Ocean Observatories Initiative (OOI)** off
the Pacific Northwest — pairing a **bottom pressure gauge** (tides / sea level)
with a **current meter** (water velocity), and analysing how they relate.

The work is a set of guided, **teach-from-zero** Jupyter notebooks (no prior
oceanography or signal-processing assumed) sharing a small helper library,
[`notebooks/oceanlib.py`](notebooks/oceanlib.py).

## The two datasets

| dataset | folder | location code | channels | what it is |
|---------|--------|---------------|----------|------------|
| **pressure gauge** | `tidal/` | `10` | `*DO` pressure (dbar), `*K1` temperature (°C) | tides / sea level |
| **current meter** | `currentmeter/<year>/` | `20` | `LOE/LON/LOZ` velocity east/north/up (m/s), `LKO` temperature | bottom currents |

Stations: **AXBA1** (Axial Base), **HYSB1** (Slope Base), **HYS14**.
The raw mSEED data (~17 GB) is **not** in the repo — point the loaders at your
local `tidal/` and `currentmeter/` folders.

## Notebooks

| # | notebook | topic |
|---|----------|-------|
| 00 | `notebooks/00_dataset_overview.ipynb` | catalog, coverage, channel inventory |
| 01 | `notebooks/01_signals_separately.ipynb` | each variable, short- & long-term |
| 02 | `notebooks/02_signals_together.ipynb` | pressure & temperature together |
| 03 | `notebooks/03_daily_plots.ipynb` | day views, spring–neap, tidal drift |
| 04 | `notebooks/04_detide_harmonic_analysis.ipynb` | **remove the tide** (Thomson & Emery harmonic analysis) |
| 05 | `notebooks/05_current_meter.ipynb` | **current velocity** — speed/direction, stick & progressive-vector plots, current rose |
| 06 | `notebooks/06_tide_current_relationship.ipynb` | **relate tide & currents** — coherence, phase lag, cross-correlation |

See [`notebooks/README.md`](notebooks/README.md) for full details, the helper API,
and the data-quality / units notes.

## Key finding

At HYSB1 the bottom currents are **tidally driven**: coherence with the tide is
~0.95 (diurnal) / 0.77 (semidiurnal) — concentrated in the tidal bands — and the
current leads the rise and fall of sea level by ~1.5–2 h, consistently across the
major constituents. The tidal current runs nearly N–S (principal axis ~2° from
North), indicating a mixed, mainly-progressive tidal regime.

## Setup

```bash
# Python 3 with: obspy, numpy, pandas, scipy, matplotlib, jupyter
pip install obspy numpy pandas scipy matplotlib jupyterlab
# optional cross-check for notebook 04:
pip install utide

jupyter lab          # then open notebooks/00_dataset_overview.ipynb
```

Regenerate the notebooks from source: `python notebooks/_build_notebooks.py`
(or one at a time: `python notebooks/_build_notebooks.py 06_tide_current_relationship.ipynb`).
