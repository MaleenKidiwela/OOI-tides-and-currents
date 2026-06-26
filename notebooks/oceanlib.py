"""
oceanlib.py — shared helpers for exploring the OOI seafloor mSEED dataset.

The data originally shipped as two *byte-identical* folders (`currentmeter/` and
`tidal/`) — same files, copied. The duplicate may since have been deleted;
`DATA_DIR` below auto-selects whichever folder still exists. Each daily mSEED
file holds ONE channel for ONE station/day.

NOTE: despite the `currentmeter/` name, there is NO current/velocity data here —
the only channels are pressure (`*DO`) and temperature (`*K1`).

Filename convention (SEED day-volume style)::

    OO.{STA}.{LOC}.{CHA}.{YYYY}.{DOY}.{HH}.{MM}.{SS}.{mmm}-{end...}.mseed
    e.g. OO.AXBA1.10.UDO.2014.244.00.00.06.735-2014.244.23.59.51.684.mseed

Two physical variables ("data types") are present per station, encoded in the
SEED channel code:

    *DO  (UDO / LDO)  -> seafloor PRESSURE  (the tidal / sea-level signal)
    *K1  (UK1 / LK1)  -> TEMPERATURE        (per SEED 2nd-letter convention 'K')

Band code (1st letter) reflects sample interval: U-band ≈ 15 s, L-band = 1 s.

Stations: AXBA1 (Axial Base), HYSB1 (Slope Base), HYS14.  Coverage 2014–2025.

This module deliberately has no exotic dependencies — just obspy / numpy /
pandas / matplotlib, all already in the environment.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from obspy import read, UTCDateTime, Stream

# ---------------------------------------------------------------------------
# Paths & basic vocabulary
# ---------------------------------------------------------------------------

# Project root = parent of this file's folder (.../data_exploration)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The data originally shipped as two identical folders (`currentmeter/` and
# `tidal/`); the duplicate may have been (or be in the middle of being) removed.
# Pick whichever candidate folder currently holds the most .mseed files, so a
# half-deleted leftover folder is never chosen.
def _pick_data_dir():
    cands = {d: len(glob.glob(os.path.join(ROOT, d, "*.mseed")))
             for d in ("tidal", "currentmeter") if os.path.isdir(os.path.join(ROOT, d))}
    best = max(cands, key=cands.get) if cands else "tidal"
    return os.path.join(ROOT, best)

DATA_DIR = _pick_data_dir()
FIG_DIR = os.path.join(ROOT, "figures")

STATIONS = ["AXBA1", "HYSB1", "HYS14"]

# --- Unit calibration --------------------------------------------------------
# The pressure channels are stored as integer "counts". The conversion to
# physical units is 1e-4 dbar per count.  This factor is not shipped in the
# mSEED files, but it is pinned down four independent ways:
#   * AXBA1 / HYSB1 / HYS14 mean pressures -> 2656 / 2960 / 793 dbar, which match
#     those sites' known deployment depths (≈2607 / 2900 / 790 m; dbar ≈ depth-m);
#   * the fitted M2 tide comes out ≈0.83 dbar ≈ 0.83 m, the textbook NE-Pacific value.
# In seawater 1 dbar ≈ 1.02 m, so a dbar reading is also (very nearly) the depth
# in metres, and a pressure *anomaly* in dbar is essentially sea-level change in m.
COUNTS_PER_DBAR = 1.0e4

# Map the two physical variables to channel codes + display units.
# (band letter differs by station, so we match on the last two letters.)
VARIABLES = {
    "pressure": {"suffix": "DO", "label": "Seafloor pressure", "units": "dbar"},
    "temperature": {"suffix": "K1", "label": "Temperature", "units": "°C"},
}


def _to_physical(series, variable, raw=False):
    """Convert raw counts to physical units (pressure -> dbar). Temperature is
    already in °C. Pass raw=True to keep counts."""
    if raw or variable != "pressure":
        return series
    return series / COUNTS_PER_DBAR

# Hand-picked long, gap-free windows (found by scanning the catalog) — handy
# defaults so every notebook opens on data that actually plots cleanly.
DEMO = {
    "AXBA1": {"channel": "UDO", "start": "2015-03-09", "end": "2016-07-11"},  # 15 s, 491 d
    "HYSB1": {"channel": "LDO", "start": "2019-07-29", "end": "2020-05-09"},  # 1 Hz, 286 d
    "HYS14": {"channel": "LDO", "start": "2018-10-02", "end": "2019-07-26"},  # 1 Hz, 298 d
}

_FNAME_RE = re.compile(
    r"OO\.(?P<sta>[A-Z0-9]+)\.(?P<loc>\d+)\.(?P<cha>[A-Z0-9]+)\."
    r"(?P<year>\d{4})\.(?P<doy>\d{3})\."
)


# ---------------------------------------------------------------------------
# Filename parsing & catalog
# ---------------------------------------------------------------------------

def parse_name(path: str) -> dict | None:
    """Pull station / channel / year / day-of-year out of a filename."""
    m = _FNAME_RE.search(os.path.basename(path))
    if not m:
        return None
    d = m.groupdict()
    d["year"] = int(d["year"])
    d["doy"] = int(d["doy"])
    # date = Jan 1 of year + (doy-1) days
    d["date"] = pd.Timestamp(d["year"], 1, 1) + pd.Timedelta(days=d["doy"] - 1)
    cha = d["cha"]
    d["variable"] = (
        "pressure" if cha.endswith("DO")
        else "temperature" if cha.endswith("K1") or cha.endswith("KO")
        else "velocity" if cha in ("LOE", "LON", "LOZ")
        else "other"
    )
    d["path"] = path
    return d


def build_catalog(data_dir: str = DATA_DIR) -> pd.DataFrame:
    """One row per mSEED file — fast, parses filenames only (no data read)."""
    rows = [parse_name(p) for p in glob.glob(os.path.join(data_dir, "*.mseed"))]
    df = pd.DataFrame([r for r in rows if r])
    return df.sort_values(["sta", "cha", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------

def channels_for(station: str, variable: str, data_dir: str = DATA_DIR) -> pd.Series:
    """All channel codes carrying `variable` at `station`, ordered by file count.

    Several stations have BOTH a U-band (15 s) and an L-band (1 s) channel for
    the same variable (e.g. HYS14 has UDO and LDO).  Returns a Series indexed by
    channel code with the file count as value (most data first).
    """
    suffix = VARIABLES[variable]["suffix"]
    # channel codes are 3 letters: <band><instrument><orientation>, e.g. 'UDO'.
    hits = glob.glob(os.path.join(data_dir, f"OO.{station}.*.?{suffix}.*.mseed"))
    chans = pd.Series([parse_name(h)["cha"] for h in hits])
    if chans.empty:
        raise FileNotFoundError(f"No {variable} files for {station}")
    return chans.value_counts()


def channel_for(station: str, variable: str, data_dir: str = DATA_DIR) -> str:
    """Primary (most-data) channel code for a station/variable."""
    return channels_for(station, variable, data_dir).index[0]


def load(station: str, variable: str, start, end,
         data_dir: str = DATA_DIR, merge: bool = True, channel: str | None = None) -> Stream:
    """Load a station/variable between two dates (inclusive of the day range).

    `start`/`end` accept anything pandas can parse ('2018-01-10', datetime, …).
    Pass `channel=` to force a specific code when a station has both bands
    (e.g. 'LDO' vs 'UDO'); otherwise the primary channel is used.
    Returns an obspy Stream; gaps are left as separate traces unless merged.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cha = channel or channel_for(station, variable, data_dir)

    st = Stream()
    day = start.normalize()
    while day <= end:
        doy = day.dayofyear
        pat = os.path.join(data_dir, f"OO.{station}.*.{cha}.{day.year}.{doy:03d}.*.mseed")
        for f in glob.glob(pat):
            st += read(f)
        day += pd.Timedelta(days=1)

    if len(st):
        st.trim(UTCDateTime(start), UTCDateTime(end + pd.Timedelta(days=1)))
    if merge and len(st) > 1:
        # fill_value=None keeps gaps as masked arrays (won't fabricate data)
        st.merge(method=1, fill_value=None)
    return st


def to_series(st: Stream) -> pd.Series:
    """Flatten a (merged) Stream into a single time-indexed pandas Series.

    Masked / gap samples become NaN.  Index is UTC DatetimeIndex.
    """
    parts = []
    for tr in st:
        # tz-naive UTC index (all OOI timestamps are UTC); keeps slicing & plotting simple
        idx = pd.to_datetime(tr.times("timestamp"), unit="s")
        data = tr.data.astype(float)
        if np.ma.isMaskedArray(tr.data):
            data = tr.data.filled(np.nan).astype(float)
        parts.append(pd.Series(data, index=idx))
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="first")]


def load_series(station, variable, start, end, data_dir=DATA_DIR, channel=None,
                raw=False) -> pd.Series:
    """Convenience: load() + to_series() in one call, returned in physical units
    (pressure in dbar, temperature in °C). Pass raw=True to keep instrument counts."""
    s = to_series(load(station, variable, start, end, data_dir, channel=channel))
    return _to_physical(s, variable, raw=raw)


def load_decimated(station, variable, start, end, rule="1h",
                   how="mean", data_dir=DATA_DIR, channel: str | None = None,
                   raw: bool = False) -> pd.Series:
    """Load a LONG span memory-cheaply by resampling each daily file before
    concatenating.  Ideal for multi-month / multi-year ('long-term') views.
    Returned in physical units (dbar / °C) unless raw=True.

    `rule` is any pandas offset ('1h', '10min', '1D').  `how` in {mean, median}.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    cha = channel or channel_for(station, variable, data_dir)

    chunks = []
    day = start.normalize()
    while day <= end:
        doy = day.dayofyear
        pat = os.path.join(data_dir, f"OO.{station}.*.{cha}.{day.year}.{doy:03d}.*.mseed")
        for f in glob.glob(pat):
            s = to_series(read(f))
            if len(s):
                r = s.resample(rule)
                chunks.append(r.mean() if how == "mean" else r.median())
        day += pd.Timedelta(days=1)

    if not chunks:
        return pd.Series(dtype=float)
    s = pd.concat(chunks).sort_index()
    s = s[~s.index.duplicated(keep="first")]
    s = s.loc[start:end + pd.Timedelta(days=1)]
    return _to_physical(s, variable, raw=raw)


# ===========================================================================
# CURRENT-METER dataset  (the `currentmeter/` folder)
# ===========================================================================
# A SEPARATE dataset from the pressure-gauge data above. It lives in
# `currentmeter/<year>/`, uses location code "20", and carries a current meter's
# 3-D water VELOCITY plus temperature:
#
#     LOE -> eastward  velocity (m/s)     LOZ -> vertical (up) velocity (m/s)
#     LON -> northward velocity (m/s)     LKO -> temperature (°C)
#
# Velocity is already in physical units (m/s) and can be negative (west/south/down).
CUR_DIR = os.path.join(ROOT, "currentmeter")
CUR_COMPONENTS = {"east": "LOE", "north": "LON", "up": "LOZ"}   # column -> channel
CUR_TEMP = "LKO"

# A long, gap-free, GOOD-QUALITY 3-component window at HYSB1 (the station with
# almost all the data). Avoids 2016, which has ~19% unphysical/fill values.
CUR_DEMO = {"HYSB1": {"start": "2018-10-02", "end": "2019-04-19"}}

# Bottom currents here are <~1 m/s; speeds far beyond that are fill/spike values.
CUR_QC_MAX = 3.0  # m/s — components with |value| above this are masked to NaN


def _cur_channel_series(station, cha, start, end, rule=None) -> pd.Series:
    """Load one current-meter channel across the (year-foldered) day range."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    chunks = []
    day = start.normalize()
    while day <= end:
        pat = os.path.join(CUR_DIR, str(day.year),
                            f"OO.{station}.*.{cha}.{day.year}.{day.dayofyear:03d}.*.mseed")
        for f in glob.glob(pat):
            s = to_series(read(f))
            if rule and len(s):
                s = s.resample(rule).mean()
            if len(s):
                chunks.append(s)
        day += pd.Timedelta(days=1)
    if not chunks:
        return pd.Series(dtype=float)
    s = pd.concat(chunks).sort_index()
    s = s[~s.index.duplicated(keep="first")]
    return s.loc[start:end + pd.Timedelta(days=1)]


def load_current(station, start, end, rule=None, with_temp=False,
                 qc_max=CUR_QC_MAX) -> pd.DataFrame:
    """Load current-meter velocity as a DataFrame with columns east/north/up (m/s),
    indexed by UTC time. Pass `rule` (e.g. '10min', '1h') to decimate long spans,
    `with_temp=True` to also include a 'temp' column (°C).

    Quality control: components with |value| > `qc_max` m/s (fill/spike values)
    are masked to NaN *before* decimation; set qc_max=None to disable.
    Adds derived columns `speed` (horizontal, m/s) and `dir` (compass degrees the
    flow is heading TOWARD: 0°=N, 90°=E)."""
    # Load raw (no resample yet) so QC happens before averaging.
    raw_cols = {name: _cur_channel_series(station, cha, start, end, rule=None)
                for name, cha in CUR_COMPONENTS.items()}
    if with_temp:
        raw_cols["temp"] = _cur_channel_series(station, CUR_TEMP, start, end, rule=None)
    df = pd.DataFrame(raw_cols).sort_index()

    if qc_max:
        for c in ("east", "north", "up"):
            if c in df:
                df.loc[df[c].abs() > qc_max, c] = np.nan
    if rule:
        df = df.resample(rule).mean()

    if {"east", "north"}.issubset(df.columns):
        df["speed"] = np.hypot(df["east"], df["north"])
        df["dir"] = (np.degrees(np.arctan2(df["east"], df["north"])) % 360)
    return df


def build_current_catalog() -> pd.DataFrame:
    """One row per current-meter file (parses names under currentmeter/<year>/)."""
    rows = [parse_name(p) for p in glob.glob(os.path.join(CUR_DIR, "*", "*.mseed"))]
    df = pd.DataFrame([r for r in rows if r])
    return df.sort_values(["sta", "cha", "date"]).reset_index(drop=True)


def current_stations() -> list:
    """Stations that currently have current-meter velocity data on disk.
    Discovered dynamically, so newly-downloaded stations appear automatically."""
    paths = glob.glob(os.path.join(CUR_DIR, "*", "OO.*.20.LOE.*.mseed"))
    return sorted({m["sta"] for p in paths if (m := parse_name(p))})


def primary_current_station() -> str:
    """The current-meter station with the most data (a sensible notebook default
    that updates itself as more stations are downloaded)."""
    paths = glob.glob(os.path.join(CUR_DIR, "*", "OO.*.20.LOE.*.mseed"))
    counts = pd.Series([m["sta"] for p in paths if (m := parse_name(p))]).value_counts()
    return counts.index[0]


def longest_current_window(station) -> dict:
    """Longest gap-free run of days with eastward-velocity data for a station.
    Used as an automatic fallback window for stations not pinned in CUR_DEMO."""
    cat = build_current_catalog()
    d = (cat[(cat.sta == station) & (cat.cha == "LOE")]
         .drop_duplicates("date").sort_values("date"))
    if d.empty:
        raise FileNotFoundError(f"No current-meter data for {station}")
    dates = d.date.reset_index(drop=True)
    grp = (dates.diff().dt.days.fillna(1) != 1).cumsum()
    runs = dates.groupby(grp).agg(["min", "max", "count"]).sort_values("count", ascending=False)
    best = runs.iloc[0]
    return {"start": str(best["min"].date()), "end": str(best["max"].date())}


def current_window(station) -> dict:
    """A good demo window for `station`: the hand-picked clean one if we have it,
    otherwise the longest gap-free run found automatically."""
    return CUR_DEMO.get(station) or longest_current_window(station)


# ===========================================================================
# Harmonic (tidal) analysis — shared by the de-tide and tide/current notebooks
# ===========================================================================
# Standard constituent speeds in degrees per mean solar hour.
TIDAL_SPEEDS = {
    "Mm": 0.5443747, "Mf": 1.0980331,
    "Q1": 13.3986609, "O1": 13.9430356, "P1": 14.9589314, "K1": 15.0410686,
    "N2": 28.4397295, "M2": 28.9841042, "S2": 30.0000000, "K2": 30.0821373,
    "M4": 57.9682084, "MS4": 58.9841042,
}


def harmonic_fit(series, constituents=None, with_trend=True, t0=None):
    """Least-squares tidal harmonic fit of a time-indexed Series (Thomson & Emery).

    Models y ≈ mean (+ trend) + Σ[a_k cos(2πf_k t) + b_k sin(2πf_k t)], so each
    constituent has amplitude √(a²+b²) and phase atan2(b,a). Phases are measured
    from `t0` (default = first sample); fit two series with the SAME `t0` to make
    their phases directly comparable.

    Returns dict with: `amps` (DataFrame: amplitude, phase_deg, period_h per
    constituent), `tide` (reconstructed Series, mean+constituents, no trend),
    `residual` (series − tide), `coef`, `t0`.
    """
    series = series.dropna()
    speeds = TIDAL_SPEEDS if constituents is None else {k: TIDAL_SPEEDS[k] for k in constituents}
    freqs = {k: v / 360.0 for k, v in speeds.items()}
    t0 = series.index[0] if t0 is None else pd.Timestamp(t0)
    th = ((series.index - t0) / pd.Timedelta(hours=1)).values.astype(float)
    y = series.values.astype(float)

    cols, names = [np.ones_like(th)], ["mean"]
    if with_trend:
        cols.append(th); names.append("trend")
    for k, f in freqs.items():
        w = 2 * np.pi * f
        cols += [np.cos(w * th), np.sin(w * th)]
        names += [f"{k}_cos", f"{k}_sin"]
    beta, *_ = np.linalg.lstsq(np.column_stack(cols), y, rcond=None)
    coef = dict(zip(names, beta))

    rows = []
    for k, f in freqs.items():
        a, b = coef[f"{k}_cos"], coef[f"{k}_sin"]
        rows.append({"constituent": k, "period_h": 1 / f,
                     "amplitude": np.hypot(a, b),
                     "phase_deg": np.degrees(np.arctan2(b, a)) % 360})
    amps = pd.DataFrame(rows).set_index("constituent")

    tide = np.full_like(th, coef["mean"])
    for k, f in freqs.items():
        w = 2 * np.pi * f
        tide += coef[f"{k}_cos"] * np.cos(w * th) + coef[f"{k}_sin"] * np.sin(w * th)
    tide = pd.Series(tide, index=series.index)
    return {"amps": amps, "tide": tide, "residual": series - tide, "coef": coef, "t0": t0}


def principal_axis(east, north):
    """Major axis of a current's variability (PCA on the east/north scatter).

    Returns (unit_vector[ex, ny], orientation_deg, major_projection_series).
    The projection is the current resolved along its dominant oscillation axis —
    i.e. the scalar 'tidal current'. Orientation is 0–180° clockwise from North."""
    ec = (east - east.mean()).values
    nc = (north - north.mean()).values
    cov = np.cov(np.vstack([ec, nc]))
    evals, evecs = np.linalg.eigh(cov)         # ascending
    v = evecs[:, -1]                            # major-axis unit vector [e, n]
    proj = pd.Series(ec * v[0] + nc * v[1], index=east.index)
    orient = np.degrees(np.arctan2(v[0], v[1])) % 180
    return v, orient, proj


# ---------------------------------------------------------------------------
# Small plotting / formatting helpers
# ---------------------------------------------------------------------------

def savefig(fig, name: str):
    """Save into ../figures with a consistent style."""
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, name)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("saved", out)
    return out


def label_for(variable: str) -> str:
    v = VARIABLES[variable]
    return f"{v['label']} [{v['units']}]"


@dataclass
class Span:
    """Tiny helper to describe a time window for the notebooks."""
    start: str
    end: str
    def __iter__(self):
        return iter((self.start, self.end))
