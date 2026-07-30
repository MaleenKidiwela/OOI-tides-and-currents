"""Flask JSON API for the OOI pressure-gauge web viewer.

A thin wrapper around ``notebooks/oceanlib.py``: it does no science of its own,
it just slices the requested station/date window with the existing loaders and
returns compact, plot-ready JSON. Run it and open http://localhost:5000 .

    cd webapp && python app.py

Endpoints
    GET /                 -> the single-page UI (static/index.html)
    GET /api/meta         -> stations, channels, coverage, geography, demo windows
    GET /api/series       -> pressure &/or temperature for a window
    GET /api/detide       -> tidal model (tide + residual + constituents)
    GET /api/current      -> current-meter velocity for the same window
"""
from __future__ import annotations

import math
import os
import sys

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider

# --- make oceanlib importable (it lives in ../notebooks) --------------------
HERE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOKS = os.path.join(os.path.dirname(HERE), "notebooks")
sys.path.insert(0, NOTEBOOKS)
import oceanlib as ol  # noqa: E402

def _finite(x):
    """Recursively replace non-finite floats (NaN/Inf) with None. Bare NaN/Inf are
    valid to Python's json but NOT to the browser's JSON.parse, so we scrub them."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_finite(v) for v in x]
    return x


class SafeJSONProvider(DefaultJSONProvider):
    """JSON provider that emits `null` for NaN/Infinity so responses are valid,
    browser-parseable JSON."""
    def dumps(self, obj, **kwargs):
        return super().dumps(_finite(obj), **kwargs)


app = Flask(__name__, static_folder="static", static_url_path="/static")
app.json = SafeJSONProvider(app)


@app.errorhandler(Exception)
def _errors_as_json(e):
    """Return *every* error as JSON so the browser never gets an HTML error page
    (which would blow up the frontend's JSON parsing)."""
    from werkzeug.exceptions import HTTPException
    code = e.code if isinstance(e, HTTPException) else 500
    return jsonify({"error": f"{type(e).__name__}: {e}"}), code


# Catalog is built from ~30k filenames; do it once and keep it.
_CATALOG = None


def catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = ol.build_catalog()
    return _CATALOG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def choose_rule(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Pick a decimation rule so a plotted window stays ≲ ~4000 points."""
    hours = max((end - start).total_seconds() / 3600.0, 0.0)
    for limit_h, rule in [(48, "1min"), (24 * 7, "5min"), (24 * 31, "30min"),
                          (24 * 120, "1h"), (24 * 730, "6h")]:
        if hours <= limit_h:
            return rule
    return "1D"


def series_json(s: pd.Series) -> dict:
    """Time-indexed Series -> {t: ISO strings, v: floats/None}. NaN -> None."""
    if s is None or len(s) == 0:
        return {"t": [], "v": []}
    t = s.index.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()
    v = [None if pd.isna(x) else float(x) for x in s.to_numpy()]
    return {"t": t, "v": v}


def parse_window():
    """Read & validate station/start/end from the query string."""
    station = request.args.get("station", "")
    if station not in ol.STATIONS:
        raise ValueError(f"unknown station {station!r} (expected one of {ol.STATIONS})")
    try:
        start = pd.Timestamp(request.args["start"])
        end = pd.Timestamp(request.args["end"])
    except (KeyError, ValueError) as e:
        raise ValueError(f"start/end must be parseable datetimes: {e}")
    if end <= start:
        raise ValueError("end must be after start")
    return station, start, end


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/meta")
def meta():
    cat = catalog()
    have_current = set(ol.current_stations())
    stations = []
    for sta in ol.STATIONS:
        g = cat[cat.sta == sta]
        m = ol.STATION_META.get(sta, {})
        try:
            pressure_ch = list(ol.channels_for(sta, "pressure").index)
        except FileNotFoundError:
            pressure_ch = []
        try:
            temp_ch = list(ol.channels_for(sta, "temperature").index)
        except FileNotFoundError:
            temp_ch = []
        stations.append({
            "code": sta,
            "name": m.get("name", sta),
            "lat": m.get("lat"), "lon": m.get("lon"), "depth_m": m.get("depth_m"),
            "pressure_channels": pressure_ch,
            "temperature_channels": temp_ch,
            "coverage": None if g.empty else {
                "start": str(g.date.min().date()), "end": str(g.date.max().date())},
            "has_current": sta in have_current,
            "demo": ol.DEMO.get(sta),
        })
    return jsonify({"stations": stations})


@app.route("/api/series")
def series():
    try:
        station, start, end = parse_window()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    variables = [v for v in request.args.get("vars", "pressure").split(",") if v]
    channel = request.args.get("channel") or None
    rule = request.args.get("rule") or "auto"
    if rule == "auto":
        rule = choose_rule(start, end)

    out = {"rule": rule}
    for var in variables:
        if var not in ol.VARIABLES:
            return jsonify({"error": f"unknown variable {var!r}"}), 400
        # `channel` picks a pressure band; temperature uses its own primary band.
        ch = channel if var == "pressure" else None
        s = ol.load_decimated(station, var, start, end, rule=rule, channel=ch)
        s = s.loc[start:end]  # trim precisely to the requested [start, end]
        out[var] = series_json(s)
    return jsonify(out)


@app.route("/api/detide")
def detide():
    try:
        station, start, end = parse_window()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    channel = request.args.get("channel") or None
    # Hourly is the right resolution for tidal analysis (fastest tide ~12 h).
    s = ol.load_decimated(station, "pressure", start, end, rule="1h", channel=channel)
    s = s.loc[start:end].interpolate(limit=3).dropna()
    if len(s) < 48:
        return jsonify({"error": "need at least ~2 days of continuous pressure to fit tides"}), 400

    lat = ol.STATION_META.get(station, {}).get("lat")
    model = ol.tidal_model(s, lat=lat)  # utide if available, else NumPy fallback
    top = sorted(model["constituents"], key=lambda c: c["amp"], reverse=True)[:12]
    return jsonify({
        "method": model["method"],
        "tide": series_json(model["tide"]),
        "residual": series_json(model["residual"]),
        "constituents": top,
        "form_factor": model["form_factor"],
        "kind": model["kind"],
        "variance_explained": model["variance_explained"],
    })


@app.route("/api/current")
def current():
    try:
        station, start, end = parse_window()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if station not in set(ol.current_stations()):
        return jsonify({"available": False,
                        "message": f"no current-meter data for {station}"})

    rule = request.args.get("rule") or "auto"
    if rule == "auto":
        rule = choose_rule(start, end)
    df = ol.load_current(station, start, end, rule=rule)
    if not df.empty:
        df = df.loc[start:end]
    if df.empty or "speed" not in df or df["speed"].dropna().empty:
        return jsonify({"available": False,
                        "message": f"no current-meter samples for {station} in this window"})

    idx = df.index.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()
    def col(name):
        return [None if pd.isna(x) else float(x) for x in df[name].to_numpy()]
    return jsonify({
        "available": True, "rule": rule, "t": idx,
        "east": col("east"), "north": col("north"), "up": col("up"),
        "speed": col("speed"), "dir": col("dir"),
    })


if __name__ == "__main__":
    # Default to 8000, NOT 5000 — on macOS the AirPlay Receiver (Control Center)
    # squats on port 5000 and will intercept requests. Override with PORT=... .
    port = int(os.environ.get("PORT", "8000"))
    print(f" * OOI viewer on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
