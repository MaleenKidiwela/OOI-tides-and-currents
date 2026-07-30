# Web viewer — pressure, tides &amp; currents

A small local web UI for the OOI seafloor data. Pick a **station** and a
**start/end datetime**, and it plots the seafloor **pressure** (the tide), with
optional **temperature**, a **de-tide** view (predicted tide + non-tidal residual
+ tidal-constituent table), and the **current-meter** velocity for the same
window.

It's a thin [Flask](https://flask.palletsprojects.com/) JSON API that wraps the
existing loaders in [`../notebooks/oceanlib.py`](../notebooks/oceanlib.py), plus a
single [Plotly](https://plotly.com/javascript/) page — no build step, no npm.

## Run

```bash
pip install -r ../requirements.txt      # flask (+ obspy/numpy/pandas/scipy)
pip install utide                       # optional: latitude-aware tidal model

cd webapp
python app.py                           # serves http://127.0.0.1:8000
# (port 8000 by default; override with:  PORT=8080 python app.py)
```

Then open <http://127.0.0.1:8000>. The app reads the mSEED straight from your
local `tidal/` and `currentmeter/` folders (discovered via `oceanlib`), so those
must be present — the raw data is not shipped in the repo.

## What each control does

- **Station / Pressure band** — which site (AXBA1, HYSB1, HYS14) and which
  pressure channel (e.g. `LDO` 1 s vs `UDO` 15 s) when a station has both.
- **Start / End (UTC)** — the exact datetime window to plot; the server picks a
  sensible decimation rule so the payload stays small, then trims to your window.
- **Temperature** — add the bottom-water temperature panel.
- **De-tide** — fit a tidal model and show the predicted tide over the pressure,
  the residual in its own panel, and the constituent table + form factor. Uses
  **utide** (keyed on the station's latitude) when installed, else the built-in
  least-squares fit.
- **Current meter** — add a velocity panel (speed + east/north). Enabled only for
  stations that have current-meter data (currently mainly HYSB1).

## API (for scripting)

| endpoint | returns |
|---|---|
| `GET /api/meta` | stations, channels, coverage, lat/lon/depth, demo windows |
| `GET /api/series?station=&start=&end=&vars=pressure,temperature&channel=&rule=auto` | plot-ready time/value arrays |
| `GET /api/detide?station=&start=&end=&channel=` | tide, residual, constituents, form factor |
| `GET /api/current?station=&start=&end=&rule=auto` | east/north/up/speed/dir |

`start`/`end` accept any ISO-ish datetime (`2019-08-01`, `2019-08-01T06:30`).
Times are UTC.
