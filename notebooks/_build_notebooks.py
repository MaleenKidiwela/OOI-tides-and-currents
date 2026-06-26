"""Generate the exploration notebooks with nbformat — *teaching* edition.

These notebooks are written for an intern who is completely new to ocean
time-series, mSEED, and tidal analysis. Every technique gets a plain-language
primer, the code is commented, each plot is followed by "what you're seeing",
and there are hands-on exercises.

Run:  python _build_notebooks.py
"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell


def md(s):
    return new_markdown_cell(s.strip("\n"))


def code(s):
    return new_code_cell(s.strip("\n"))


# ---- reusable little markdown builders -------------------------------------

def objectives(*items):
    return md("> 🎯 **What you'll learn in this notebook**\n>\n" +
              "\n".join(f"> - {x}" for x in items))


def questions(*items):
    return md("> ❓ **Questions to answer**\n>\n"
              "> Work these out yourself as you go — jot your answers in a new cell. "
              "The recap at the end lets you check.\n>\n" +
              "\n".join(f"> {i+1}. {x}" for i, x in enumerate(items)))


def seeing(text):
    return md(f"> 👀 **What you're seeing**\n>\n> {text}")


def keyterm(term, definition):
    return md(f"> 📖 **{term}** — {definition}")


def exercise(*items):
    lines = "\n".join(f"> {i+1}. {x}" for i, x in enumerate(items))
    return md("> ✏️ **Try it yourself**\n>\n" + lines)


def recap(text, nxt=None):
    s = f"> ✅ **Recap**\n>\n> {text}"
    if nxt:
        s += f"\n>\n> ➡️ **Next:** {nxt}"
    return md(s)


# Common setup cell, preceded in each notebook by an explanatory markdown cell.
SETUP = """
# --- Standard scientific-Python toolkit -----------------------------------
import warnings; warnings.filterwarnings("ignore")  # hide harmless library chatter
import numpy as np                 # arrays & math
import pandas as pd                # labelled time series (our main data type)
import matplotlib.pyplot as plt    # plotting
import matplotlib.dates as mdates  # nice date axes
import oceanlib as ol              # OUR helper module (sits next to this notebook)

# Make every plot a sensible default size with a light grid.
plt.rcParams.update({"figure.figsize": (12, 4), "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 110})
pd.set_option("display.max_rows", 40)

print("Reading data from:", ol.DATA_DIR)
print("Stations available:", ol.STATIONS)
"""


# ===========================================================================
# 00 — Dataset overview  (START HERE)
# ===========================================================================
def nb00():
    nb = new_notebook()
    nb.cells = [
        md("""
# 00 · Start here — what is this dataset?

**Welcome!** These notebooks walk you from "I've never seen ocean data" to "I can
load it, plot it, remove the tide, and analyse currents". No prior oceanography
or seismology needed.

There are **two separate datasets** here:

* **`tidal/`** — a **pressure gauge** (+ temperature). Notebooks **00–04** use this.
* **`currentmeter/`** — a **current meter** measuring water **velocity**.
  Notebook **05** uses this.

This first notebook explores the **`tidal/` pressure-gauge dataset**.
"""),
        objectives(
            "What the instruments measured and where",
            "How the files are named and organised (the *SEED* convention)",
            "The two **channels** in this dataset (pressure vs temperature)",
            "How to build a quick *catalog* of 30,000 files without opening them",
            "How to see, at a glance, which station has data on which dates",
        ),
        questions(
            "How many distinct channels are there, and what physical quantity does each one carry?",
            "Why does a single station sometimes have two channels for the *same* variable?",
            "Which station has the longest span of data? Which has the least?",
            "Roughly how many years does the whole archive cover?",
        ),
        md("""
## Background: where does this data come from?

These are measurements from instruments sitting on the **seafloor** off the
Pacific Northwest (USA), part of the **Ocean Observatories Initiative (OOI)** —
a network of cabled underwater sensors that stream data continuously for years.

Each instrument records two things we care about here:

1. **Pressure** — the weight of the water column above the sensor. When the
   tide comes in, there's *more* water overhead, so pressure rises. Pressure is
   therefore a direct stand-in for **sea level / tides**.
2. **Temperature** — how warm the near-bottom seawater is.

The data is stored in a file format called **mSEED** (miniSEED), which was
invented for seismometers but is widely used for any continuous sensor stream.
We don't need to know its internals — the `obspy` library reads it for us.
"""),
        keyterm("Time series", "a sequence of measurements taken at successive "
                "times. Almost everything in these notebooks is a time series: "
                "a column of *values* paired with a column of *timestamps*."),
        md("""
## How the files are named

Every file holds **one channel, for one station, for one day**. The name packs
in all the metadata, following the **SEED** naming convention:

```
OO . AXBA1 . 10 . UDO . 2014 . 244 . 00.00.06.735 - 2014.244.23.59.51.684 .mseed
│    │       │    │      │      │     └ start time (HH.MM.SS.mmm)      └ end time
│    │       │    │      │      └ day-of-year (244 = 1 Sep)
│    │       │    │      └ year
│    │       │    └ CHANNEL code (the important bit — see below)
│    │       └ location code
│    └ STATION  (AXBA1 = "Axial Base")
└ network (OO = Ocean Observatories)
```
"""),
        keyterm("Day-of-year (DOY)", "the day's number within the year, 1–365 "
                "(or 366). DOY 1 = 1 Jan, DOY 244 = 1 Sep. Common in geoscience "
                "because it sorts cleanly. We convert it to a normal date for you."),
        keyterm("UTC", "Coordinated Universal Time — the single global clock all "
                "this data uses (no time zones, no daylight saving). Every "
                "timestamp here is UTC."),
        md("""
## The channel code = which variable

The 3-letter **channel** tells you what the numbers mean. The last two letters
matter most:

| channel ends in | variable | rough values | think of it as |
|-----------------|----------|--------------|----------------|
| `DO` (e.g. `UDO`, `LDO`) | **pressure** (→ dbar) | ~790–2960 dbar | the tide / sea level |
| `K1` (e.g. `UK1`, `LK1`) | **temperature** | ~1.8–4 °C | bottom-water warmth |

The **first** letter is just the speed the sensor sampled at: `U` ≈ one reading
every **15 seconds**, `L` = one reading every **1 second**.

> ℹ️ **A bit of history about the folders.** This pressure-gauge data originally
> arrived duplicated in **two byte-identical folders** (`tidal/` and
> `currentmeter/`). The duplicate was later removed and `currentmeter/` was
> repurposed for the genuine **current-meter** dataset (water velocity — see
> notebook 05). So in *this* notebook the two "types of data" are the two
> **channels** — pressure and temperature — within the `tidal/` folder.
> `oceanlib` auto-selects whichever pressure-gauge folder is present.
"""),
        md("## Let's look. First, load the toolkit and our helper module."),
        code(SETUP),
        md("""
### Build a catalog from the filenames

Opening all 30,000 files would be slow. Instead we **parse the filenames** to
build a table (a pandas `DataFrame`) — one row per file — which is instant.
`oceanlib.build_catalog()` does this for us.
"""),
        code("""
cat = ol.build_catalog()                       # one row per file, from names only
print(f"{len(cat):,} files spanning {cat.date.min().date()} → {cat.date.max().date()}")
cat.head()      # peek at the first few rows
"""),
        seeing("A table where each row is one daily file. Key columns: `sta` "
               "(station), `cha` (channel), `date`, and `variable` — which we "
               "derived from the channel code so you can filter by 'pressure' "
               "or 'temperature' directly."),
        md("### How many files do we have, per station and channel?"),
        code("""
counts = cat.groupby(["sta", "cha", "variable"]).size().rename("files").reset_index()
counts
"""),
        seeing("Three stations (AXBA1, HYSB1, HYS14). Notice some stations list "
               "the **same variable twice** under different channels — e.g. "
               "HYS14 has both `UDO` (15 s) and `LDO` (1 s) pressure. That's the "
               "same quantity sampled at two speeds during different deployments."),
        md("`oceanlib` has a helper to show exactly which channels carry each "
           "variable, and how many files each has:"),
        code("""
for sta in ol.STATIONS:
    p = ol.channels_for(sta, "pressure")
    t = ol.channels_for(sta, "temperature")
    print(f"{sta:6s}  pressure: {dict(p)}   temperature: {dict(t)}")
"""),
        md("""
### When does each station have data?

A common first question with any sensor archive: *what are the gaps?*
Instruments get recovered, batteries die, deployments move. This plot puts a
tick mark on every day each station/channel has a file.
"""),
        code("""
fig, ax = plt.subplots(figsize=(12, 4))
labels = []
for i, (key, g) in enumerate(cat.groupby(["sta", "cha"])):
    labels.append(".".join(key))
    ax.plot(g.date, np.full(len(g), i), "|", ms=6)   # one '|' tick per available day
ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
ax.set_title("Daily-file coverage by station.channel")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ol.savefig(fig, "00_coverage.png"); plt.show()
"""),
        seeing("Solid horizontal bands = continuous data; white gaps = missing "
               "days. This is your map for choosing *when* to look — you want a "
               "long solid stretch. (We've pre-picked good ones for you; see the "
               "end of this notebook.)"),
        md("### Data volume per year"),
        code("""
piv = cat.assign(year=cat.date.dt.year).pivot_table(
    index="year", columns="sta", values="path", aggfunc="count", fill_value=0)
ax = piv.plot.bar(stacked=True, figsize=(11, 4))
ax.set_ylabel("daily files"); ax.set_title("Files per year by station")
plt.tight_layout(); ol.savefig(ax.figure, "00_files_per_year.png"); plt.show()
piv
"""),
        md("""
### Pre-picked "good" windows

To save you hunting for gap-free stretches, `oceanlib` ships a few long,
continuous windows — one per station. The later notebooks open on these by
default.
"""),
        code("ol.DEMO"),
        exercise(
            "Change `cat.head()` to `cat.tail()` — what are the *most recent* files?",
            "Filter the catalog to just one station: `cat[cat.sta == 'HYSB1']`.",
            "Count how many *years* HYS14 covers: `cat[cat.sta=='HYS14'].date.dt.year.nunique()`.",
        ),
        recap(
            "You now know the data is OOI seafloor pressure & temperature, stored "
            "as daily mSEED files named by the SEED convention, with two real "
            "data types (pressure `*DO`, temperature `*K1`). You can build a "
            "catalog and read the coverage map.",
            nxt="`01_signals_separately.ipynb` — load and actually plot each variable."),
        md("""
---
## 📖 Mini-glossary (refer back any time)

| term | meaning |
|------|---------|
| **mSEED** | the binary file format the data is stored in; `obspy` reads it |
| **channel** | 3-letter code naming the variable + sample rate (`UDO`, `LK1`, …) |
| **station** | a fixed instrument site (`AXBA1`, `HYSB1`, `HYS14`) |
| **sample rate** | how often a reading is taken (here 1 s or 15 s) |
| **dbar** | decibar, the unit of pressure we report; in seawater 1 dbar ≈ 1.02 m of depth |
| **counts** | the raw integer the instrument stores; `oceanlib` converts pressure counts → dbar for you |
| **tide** | the regular rise & fall of sea level caused by the Moon & Sun |
| **residual** | what's left after removing the tide — the "weather"/ocean signal |
| **catalog** | our table of files (built from names, no data read) |
"""),
    ]
    return nb


# ===========================================================================
# 01 — Each data type separately, short & long term
# ===========================================================================
def nb01():
    nb = new_notebook()
    nb.cells = [
        md("""
# 01 · Loading and plotting each variable

Now we open real data. We'll plot **pressure** and **temperature** *separately*,
at two zoom levels — a single day, and many months.
"""),
        objectives(
            "Load a slice of data with one helper call (no 6 GB read)",
            "Understand what a *pandas Series* of measurements looks like",
            "See the tide directly in a one-day pressure plot",
            "Understand why we *decimate* (down-sample) for long-term views",
            "Compare the same variable across all three stations",
        ),
        questions(
            "In the one-day pressure plot, how many high and low tides occur in 24 h?",
            "Roughly how big is the daily tidal range (in dbar ≈ m)?",
            "Once the tides blur together in the long-term view, what feature dominates the pressure record? Is it the same for temperature?",
            "Does temperature have a seasonal cycle? When is it warmest/coldest?",
        ),
        md("""
## The core idea: ask only for what you need

The full dataset is ~6 GB — far too much to load at once. The golden rule of
time-series work is **load a slice**: pick a *station*, a *variable*, and a
*date range*. `oceanlib.load_series(station, variable, start, end)` does exactly
that and hands back a **pandas `Series`** (values indexed by timestamp).
"""),
        code(SETUP),
        md("Pick a station to explore. `ol.DEMO` gave us a known-good window for "
           "each — we start there. Try changing `STATION` later."),
        code("""
STATION = "AXBA1"          # later: try "HYSB1" or "HYS14"
win = ol.DEMO[STATION]      # a long, gap-free window we pre-found for this station
print(STATION, "demo window:", win)
"""),
        md("""
### What does loaded data actually look like?

Let's load one day of pressure and inspect it before plotting. Always look at
your data as *numbers* first — shape, range, sampling — so a weird plot doesn't
surprise you later.
"""),
        code("""
day = pd.Timestamp(win["start"]) + pd.Timedelta(days=30)   # a day inside the window
p = ol.load_series(STATION, "pressure", day, day)

print("type           :", type(p).__name__)
print("number of points:", len(p))
print("time of 1st point:", p.index[0])
print("spacing (seconds):", (p.index[1] - p.index[0]).total_seconds())
print("value range     :", p.min(), "→", p.max())
p.head()
"""),
        seeing("A `Series`: the left column is the **timestamp** (the index), the "
               "right column is the **value**. `oceanlib` has already converted "
               "pressure from raw counts to **dbar** (decibars), so AXBA1 reads "
               "~2656 dbar — which, since 1 dbar ≈ 1.02 m of seawater, is just the "
               "instrument's depth (~2600 m) plus the tide riding on top. The "
               "spacing between timestamps tells you the sample rate."),
        keyterm("dbar (decibar)", "the pressure unit we use. Handy because in "
                "seawater **1 dbar ≈ 1.02 m of water depth**, so a pressure reading "
                "in dbar is essentially the depth in metres, and a pressure "
                "*change* in dbar is essentially a sea-level change in metres. "
                "(The raw files store integer 'counts'; oceanlib multiplies by "
                "1e-4 dbar/count — a factor verified against the known site depths "
                "and the ~0.83 m M2 tide.)"),
        md("## Short term — one full day at native resolution"),
        code("""
fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
for ax, var, c in zip(axes, ["pressure", "temperature"], ["C0", "C3"]):
    s = ol.load_series(STATION, var, day, day)        # one variable, one day
    ax.plot(s.index, s.values, c, lw=0.7)
    ax.set_ylabel(ol.label_for(var))                  # auto label + units
    ax.set_title(f"{STATION} · {var} · {day.date()}  (n={len(s):,} points)")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))  # show clock time
axes[-1].set_xlabel("UTC time")
plt.tight_layout(); ol.savefig(fig, f"01_{STATION}_oneday.png"); plt.show()
"""),
        seeing("**Top (pressure):** a smooth wave with roughly **two highs and "
               "two lows in 24 hours** — that's the tide! This is the "
               "*semidiurnal* (twice-daily) tide. **Bottom (temperature):** much "
               "flatter — the deep ocean is thermally stable — but you can often "
               "spot small wiggles that line up with the tide (water sloshing "
               "warmer/colder water past the sensor)."),
        md("""
## Long term — months of data, *decimated*

To see seasons and drift we need *months*. But a 9-month span at 1 reading/sec
is ~23 million points — slow to load and impossible to see. The fix is
**decimation**: summarise each hour by its average before plotting.

`oceanlib.load_decimated(..., rule="1h")` resamples *while loading*, so memory
stays tiny.
"""),
        keyterm("Decimation / down-sampling", "reducing the number of points by "
                "summarising (e.g. one hourly average instead of 3600 one-second "
                "readings). It keeps slow features (tides, seasons) while throwing "
                "away fast detail you can't see at this zoom anyway."),
        code("""
fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
for ax, var, c in zip(axes, ["pressure", "temperature"], ["C0", "C3"]):
    s = ol.load_decimated(STATION, var, win["start"], win["end"], rule="1h")
    ax.plot(s.index, s.values, c, lw=0.5)
    ax.set_ylabel(ol.label_for(var))
    ax.set_title(f"{STATION} · {var} · {win['start']} → {win['end']}  (hourly, n={len(s):,})")
axes[-1].set_xlabel("UTC date")
plt.tight_layout(); ol.savefig(fig, f"01_{STATION}_longterm.png"); plt.show()
"""),
        seeing("Now the individual tides are too fast to see and blur into a "
               "thick band — that band's *thickness* is the tidal range. What "
               "stands out instead is the **slow drift**: in pressure, a gentle "
               "trend (partly the instrument settling, partly real sea-level "
               "change); in temperature, a **seasonal swing**. Notebook 04 will "
               "mathematically split the fast tide from this slow part."),
        md("""
## Same variable across all three stations

Different stations sit at different depths, so their *absolute* pressure differs
hugely. To compare their *behaviour*, we subtract each one's mean — leaving the
**anomaly** (deviation from average).
"""),
        keyterm("Anomaly", "a value with its long-term mean removed, so it wiggles "
                "around zero. Lets you overlay signals that otherwise sit at very "
                "different baselines."),
        code("""
var = "pressure"
fig, ax = plt.subplots(figsize=(12, 4.5))
for sta in ol.STATIONS:
    w = ol.DEMO[sta]
    s = ol.load_decimated(sta, var, w["start"], w["end"], rule="6h")
    ax.plot(s.index, s - s.mean(), lw=0.6, label=sta)   # subtract mean = anomaly
ax.legend(); ax.set_ylabel(f"{var} anomaly [{ol.VARIABLES[var]['units']}]")
ax.set_title("Pressure anomaly (mean removed) — each station's demo window")
plt.tight_layout(); ol.savefig(fig, "01_all_stations_pressure.png"); plt.show()
"""),
        seeing("The windows differ per station, so they don't line up in time — "
               "that's expected. The point is the *character*: all show the same "
               "thick tidal band plus slow drift, confirming the physics is "
               "consistent across sites."),
        exercise(
            "Set `STATION = 'HYS14'` at the top and re-run. How does its one-day tide differ?",
            "In the one-day plot, change `day` to a date 5 months later and look for gaps.",
            "Re-run the long-term plot with `rule='1D'` (daily averages). What disappears, what remains?",
            "Plot temperature anomaly across stations by changing `var = 'temperature'`.",
        ),
        recap(
            "You can load any station/variable/date slice, inspect it as numbers, "
            "and plot it short-term (native rate — tides visible) and long-term "
            "(decimated — drift & seasons visible). You met *dbar* (pressure "
            "units, ≈ metres of sea level), *decimation*, and *anomaly*.",
            nxt="`02_signals_together.ipynb` — overlay pressure and temperature to compare them."),
    ]
    return nb


# ===========================================================================
# 02 — Both data types together
# ===========================================================================
def nb02():
    nb = new_notebook()
    nb.cells = [
        md("""
# 02 · Comparing the two variables together

So far we plotted pressure and temperature on separate axes. Here we put them
**together** to ask: *do they move in step?* Does the tide (pressure) leave a
fingerprint on temperature?
"""),
        objectives(
            "Plot two variables with different units on one figure (twin axes)",
            "Plot them as stacked panels for long spans",
            "Understand why we 'high-pass' before correlating",
            "Read a scatter plot and a correlation coefficient",
        ),
        questions(
            "On the twin-axis day plot, does temperature share the tide's rhythm? If so, do its peaks line up with the pressure peaks or lag them?",
            "Is the pressure–temperature correlation strong or weak? Positive or negative?",
            "Does the correlation change when you shorten the high-pass window? What does that suggest?",
            "Which station shows the clearest coupling between the two variables?",
        ),
        md("""
## The challenge: two very different scales

Pressure is hundreds-to-thousands of dbar (dominated by the instrument's depth);
temperature is a few degrees. Plotted on the same y-axis, temperature would be a
flat line at the bottom. Two solutions:

* **Twin axes** — one plot, two y-axes (left = pressure, right = temperature).
  Best for *seeing whether the wiggles align in time*.
* **Stacked panels** — two plots sharing the x-axis. Cleanest for long spans.
"""),
        code(SETUP),
        code("""
STATION = "HYS14"          # try "AXBA1" / "HYSB1"
win = ol.DEMO[STATION]
day = pd.Timestamp(win["start"]) + pd.Timedelta(days=45)
print(STATION, "| one-day:", day.date(), "| long window:", win["start"], "→", win["end"])
"""),
        md("## One day on twin axes — does temperature follow the tide?"),
        code("""
p = ol.load_series(STATION, "pressure", day, day)
t = ol.load_series(STATION, "temperature", day, day)

fig, ax1 = plt.subplots(figsize=(12, 4.5))
ax1.plot(p.index, p.values, "C0", lw=0.8)                 # pressure on the LEFT axis
ax1.set_ylabel(ol.label_for("pressure"), color="C0"); ax1.tick_params(axis="y", colors="C0")

ax2 = ax1.twinx()                                         # a SECOND y-axis sharing the x-axis
ax2.plot(t.index, t.values, "C3", lw=0.8)                 # temperature on the RIGHT axis
ax2.set_ylabel(ol.label_for("temperature"), color="C3"); ax2.tick_params(axis="y", colors="C3")
ax2.grid(False)

ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax1.set_title(f"{STATION} · pressure (blue) vs temperature (red) · {day.date()}")
plt.tight_layout(); ol.savefig(fig, f"02_{STATION}_twin_oneday.png"); plt.show()
"""),
        seeing("Look at the *timing* of the peaks. If temperature rises and falls "
               "with the same ~12-hour rhythm as pressure, the tide is physically "
               "moving water masses of different temperature past the sensor "
               "(**tidal advection**). Often the two are offset by a few hours — "
               "a *phase lag* — which is itself interesting."),
        md("## Long term — stacked panels (hourly)"),
        code("""
P = ol.load_decimated(STATION, "pressure",   win["start"], win["end"], rule="1h")
T = ol.load_decimated(STATION, "temperature", win["start"], win["end"], rule="1h")

fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)   # sharex = aligned time axes
axes[0].plot(P.index, P.values, "C0", lw=0.5); axes[0].set_ylabel(ol.label_for("pressure"))
axes[1].plot(T.index, T.values, "C3", lw=0.5); axes[1].set_ylabel(ol.label_for("temperature"))
axes[0].set_title(f"{STATION} · both variables · {win['start']} → {win['end']} (hourly)")
plt.tight_layout(); ol.savefig(fig, f"02_{STATION}_stacked_longterm.png"); plt.show()
"""),
        seeing("Over months, ask whether the *slow* features line up — e.g. does "
               "a seasonal warming in the bottom panel coincide with anything in "
               "pressure? Stacking with a shared x-axis makes such alignment easy "
               "to eyeball."),
        md("""
## Do they actually co-vary? A first statistic

\"They look related\" isn't proof. We can measure it with a **correlation
coefficient** `r` (−1 = perfect opposite, 0 = unrelated, +1 = perfectly
together).

But first an important step: both series have slow drift. If we correlate them
raw, the drift dominates and tells us nothing about the *fluctuations*. So we
**high-pass** — subtract a 7-day rolling average — to keep only the wiggles
faster than a week, then correlate those.
"""),
        keyterm("High-pass filter", "removing the slow part of a signal to keep "
                "the fast part. Here: value minus its 7-day running mean, leaving "
                "only changes quicker than ~a week."),
        code("""
df = pd.concat({"pressure": P, "temperature": T}, axis=1).dropna()
# subtract a centred 7-day rolling mean from each column -> keep only fast wiggles
anom = df - df.rolling("7D", center=True, min_periods=1).mean()

r = anom["pressure"].corr(anom["temperature"])
print(f"Correlation r (7-day high-passed pressure vs temperature) = {r:+.3f}")

fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(anom["pressure"], anom["temperature"], s=3, alpha=0.2)
ax.set_xlabel("pressure anomaly [dbar]"); ax.set_ylabel("temperature anomaly [°C]")
ax.set_title(f"{STATION} · anomaly scatter (r={r:+.2f})")
plt.tight_layout(); ol.savefig(fig, f"02_{STATION}_scatter.png"); plt.show()
"""),
        seeing("Each dot is one hour: its pressure anomaly vs its temperature "
               "anomaly. A tilted cigar-shaped cloud means they're correlated "
               "(the sign of the tilt tells you whether high tide brings warmer "
               "or colder water). A round blob means little linear relationship. "
               "The number `r` summarises the tilt."),
        exercise(
            "Try each station. Which has the strongest pressure–temperature correlation?",
            "Change the high-pass window from `'7D'` to `'2D'`. Does `r` change? Why might it?",
            "On the twin-axis day plot, estimate the phase lag (hours) between pressure and temperature peaks.",
        ),
        recap(
            "You can display two differently-scaled variables together (twin axes "
            "& stacked panels) and quantify their relationship with a high-passed "
            "correlation and scatter plot. You met *tidal advection*, "
            "*high-pass filtering*, and the correlation coefficient `r`.",
            nxt="`03_daily_plots.ipynb` — zoom into day-by-day structure."),
    ]
    return nb


# ===========================================================================
# 03 — Daily plots
# ===========================================================================
def nb03():
    nb = new_notebook()
    nb.cells = [
        md("""
# 03 · Looking at the signal one day at a time

The tide isn't the same every day — its size grows and shrinks over a ~2-week
cycle, and its timing drifts ~50 minutes later each day. The best way to *see*
these patterns is to slice the record into days and compare them. This notebook
shows three classic "day views".
"""),
        objectives(
            "Build a grid of consecutive single-day plots",
            "Overlay many days on one 24-hour axis ('spaghetti plot')",
            "Make an hour-of-day × date heatmap",
            "Recognise the spring–neap cycle and the daily ~50-min tide drift",
        ),
        questions(
            "Estimate how much later the tide arrives each day. What astronomical fact explains that shift?",
            "From the heatmap, find a spring (big) and a neap (small) period — how many days apart are successive springs?",
            "Does the tide here look diurnal (one cycle/day), semidiurnal (two), or mixed?",
            "Do you see the same patterns if you switch the variable to temperature?",
        ),
        md("""
## Two things to watch for

* **Spring–neap cycle (~14.8 days):** when the Sun's and Moon's tides line up
  you get big tides (*spring*); when they fight you get small tides (*neap*).
* **Lunar-day drift (~50 min/day):** high tide is governed by the Moon, whose
  "day" is ~24 h 50 min, so the tide creeps later each solar day.

Day-by-day plots make both jump out.
"""),
        code(SETUP),
        code("""
STATION = "AXBA1"
VAR = "pressure"
win = ol.DEMO[STATION]
start = pd.Timestamp(win["start"]) + pd.Timedelta(days=20)   # where our day-tour begins
print(STATION, VAR, "starting", start.date())
"""),
        md("""
## View 1 — a grid of consecutive days

Nine days, each in its own little panel, x-axis = hour of day. We subtract each
day's mean so they're vertically comparable (we care about *shape*, not the slow
drift between days).
"""),
        code("""
N = 9
fig, axes = plt.subplots(3, 3, figsize=(13, 8), sharey=True)
for i, ax in enumerate(axes.flat):
    d = start + pd.Timedelta(days=i)
    s = ol.load_series(STATION, VAR, d, d)
    if len(s):
        hrs = (s.index - d) / pd.Timedelta(hours=1)        # convert timestamps -> hours into the day
        ax.plot(hrs, s.values - s.mean(), lw=0.7)          # minus daily mean
    ax.set_title(d.strftime("%Y-%m-%d"), fontsize=9)
    ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24])
fig.suptitle(f"{STATION} {VAR} — {N} consecutive days (each day's mean removed)", y=1.0)
fig.supxlabel("hour of day (UTC)"); fig.supylabel(f"anomaly [{ol.VARIABLES[VAR]['units']}]")
plt.tight_layout(); ol.savefig(fig, f"03_{STATION}_day_grid.png"); plt.show()
"""),
        seeing("Read left-to-right, top-to-bottom (consecutive days). Watch the "
               "twin daily humps **shift slightly rightward** each day (the "
               "50-min lunar drift) and the **overall amplitude grow or shrink** "
               "across the 9 days (heading into spring or neap tides)."),
        md("""
## View 2 — all days overlaid on one 24-hour axis

Now stack 30 days on the *same* 0–24 h axis, colouring each day by how far into
the month it is. This 'spaghetti plot' shows the spread of tidal behaviour.
"""),
        code("""
NDAYS = 30
fig, ax = plt.subplots(figsize=(11, 5))
cmap = plt.cm.viridis
for i in range(NDAYS):
    d = start + pd.Timedelta(days=i)
    s = ol.load_series(STATION, VAR, d, d)
    if not len(s):
        continue
    hrs = (s.index - d) / pd.Timedelta(hours=1)
    ax.plot(hrs, s.values - s.mean(), lw=0.6, color=cmap(i / NDAYS), alpha=0.7)
ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3))
ax.set_xlabel("hour of day (UTC)"); ax.set_ylabel(f"anomaly [{ol.VARIABLES[VAR]['units']}]")
ax.set_title(f"{STATION} {VAR} — {NDAYS} days overlaid (colour = day, dark→bright)")
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, NDAYS))
fig.colorbar(sm, ax=ax, label="days from start")
plt.tight_layout(); ol.savefig(fig, f"03_{STATION}_daily_overlay.png"); plt.show()
"""),
        seeing("The way the colours *fan out* shows the tide's phase marching "
               "around the clock over the month (the 50-min/day drift, "
               "accumulated). The envelope's width shows how much the tidal range "
               "varies between spring and neap."),
        md("""
## View 3 — hour-of-day × date heatmap (the clearest view)

Put **hour of day** on the vertical axis, **date** on the horizontal, and colour
each cell by the pressure anomaly. Spring–neap and the phase drift appear as
clean patterns.
"""),
        code("""
NDAYS = 60
s = ol.load_decimated(STATION, VAR, start, start + pd.Timedelta(days=NDAYS), rule="1h")
anom = s - s.rolling(24, center=True, min_periods=1).mean()   # remove slow daily drift

grid = anom.to_frame("v")
grid["date"] = grid.index.normalize()      # the calendar day
grid["hour"] = grid.index.hour             # 0..23
mat = grid.pivot_table(index="hour", columns="date", values="v")   # hour × date table

fig, ax = plt.subplots(figsize=(13, 4.5))
im = ax.pcolormesh(mat.columns, mat.index, mat.values, shading="auto", cmap="RdBu_r")
ax.set_ylabel("hour of day (UTC)"); ax.set_title(f"{STATION} {VAR} anomaly — hour vs date")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
fig.colorbar(im, ax=ax, label=f"anomaly [{ol.VARIABLES[VAR]['units']}]")
plt.tight_layout(); ol.savefig(fig, f"03_{STATION}_hour_date_heatmap.png"); plt.show()
"""),
        seeing("Red = above average, blue = below. The **diagonal stripes** are "
               "the tide's high/low times sliding ~50 min later each day. The "
               "**fading and strengthening of the colours** every ~2 weeks is the "
               "spring–neap cycle. This single picture encodes everything the "
               "first two views hinted at."),
        exercise(
            "Find a neap (weak) period in the heatmap, then plot that exact day with View 1's code.",
            "Switch `VAR='temperature'` in View 3. Is the tidal striping visible in temperature too?",
            "Increase `NDAYS` to 120 in the heatmap — count how many spring–neap cycles you see.",
        ),
        recap(
            "Three ways to view daily structure — a day grid, a 24-hour overlay, "
            "and an hour×date heatmap — and you can now spot the spring–neap "
            "cycle and the ~50-min/day lunar drift by eye.",
            nxt="`04_detide_harmonic_analysis.ipynb` — predict the tide mathematically and subtract it."),
    ]
    return nb


# ===========================================================================
# 04 — Removing tides: harmonic analysis (Thomson & Emery)
# ===========================================================================
def nb04():
    nb = new_notebook()
    nb.cells = [
        md(r"""
# 04 · Removing the tide — harmonic analysis

This is the payoff notebook. The tide is usually the *biggest* signal in the
pressure record, but often it's the part we want to **get rid of** — to see what
the ocean is doing underneath it (storms, currents, sea-level change). The
classic tool is **harmonic analysis**, exactly as described in the standard
textbook *Data Analysis Methods in Physical Oceanography* by **Richard E.
Thomson & William J. Emery** (Chapter 5).

We'll build it from scratch in NumPy so nothing is a black box, then optionally
cross-check against the `utide` package.
"""),
        objectives(
            "Understand *why* the tide is a sum of fixed-frequency 'constituents'",
            "Fit those constituents to data by least squares (the T&E method)",
            "Use the fit to PREDICT the tide and SUBTRACT it",
            "Read constituent amplitudes and the tidal 'form factor'",
            "Confirm with a spectrum that the tidal peaks are gone",
        ),
        questions(
            "Which constituent is largest at this site? What does the form factor say about the tide type?",
            "What fraction of the pressure variance is tidal?",
            "Is the out-of-sample score close to the in-sample score? Why does that matter?",
            "After de-tiding, what's left in the residual — and what physical process might cause it?",
            "When you lengthen the record, which constituents' amplitudes change most, and why?",
        ),
        md(r"""
## The big idea (no equations yet)

The tide is driven by the **gravity of the Moon and Sun** as the Earth rotates.
Because the orbits are clockwork-regular, the tide is the sum of a *fixed* set of
pure waves, each at a precisely known frequency. These are called **tidal
constituents**, each with a two-letter+number name:

| name | period | driven by |
|------|--------|-----------|
| **M2** | 12.42 h | Moon, twice daily (the big one) |
| **S2** | 12.00 h | Sun, twice daily |
| **N2** | 12.66 h | Moon's elliptical orbit |
| **K1** | 23.93 h | Moon+Sun, once daily |
| **O1** | 25.82 h | Moon, once daily |

The **size** (amplitude) and **timing** (phase) of each constituent depends on
your location — the shape of the coastline and seafloor. **Harmonic analysis**
is the procedure that *measures* those amplitudes and phases from your data.
Once you have them, you can compute the tide at *any* time — past or future.
That's literally how tide tables are made.
"""),
        keyterm("Constituent", "one pure cosine wave at a fixed astronomical "
                "frequency (e.g. M2 = 12.42 h). The tide is their sum."),
        keyterm("Amplitude & phase", "amplitude = how tall a constituent's wave "
                "is; phase = where in its cycle it is at a reference time. "
                "Harmonic analysis solves for both."),
        code(SETUP),
        md("""
## Step 1 · Load a clean ~60-day hourly pressure series

Harmonic analysis needs a continuous, evenly-spaced series. Hourly is plenty for
the tide (its fastest wiggle is ~12 h). We take 60 gap-free days, interpolate any
tiny holes, and use pressure as our sea-level stand-in.
"""),
        code("""
STATION = "AXBA1"
win = ol.DEMO[STATION]
t0 = pd.Timestamp(win["start"]) + pd.Timedelta(days=10)
t1 = t0 + pd.Timedelta(days=60)

s = ol.load_decimated(STATION, "pressure", t0, t1, rule="1h").interpolate(limit=3)
s = s.dropna()
print(f"{STATION}: {len(s)} hourly samples  {s.index[0]} → {s.index[-1]}")

fig, ax = plt.subplots(figsize=(12, 3.5))
ax.plot(s.index, s.values, lw=0.6)
ax.set_title(f"{STATION} pressure (hourly) — the input to our harmonic fit")
ax.set_ylabel("pressure [dbar]"); plt.tight_layout(); plt.show()
"""),
        seeing("60 days of tide. The obvious ~2-week swelling and shrinking of the "
               "envelope is the spring–neap cycle (which is really M2 and S2 "
               "beating against each other). Our job: find the constituents that "
               "add up to this curve."),
        md(r"""
## Step 2 · List the constituents and their frequencies

Each constituent has an astronomically-fixed **speed** in *degrees per hour*
(how fast its phase advances). Frequency in cycles/hour = speed / 360. These
numbers are universal constants — the same everywhere on Earth.
"""),
        code("""
# name : degrees per (solar) hour  — standard tidal speeds
CONSTITUENTS = {
    "Mm":  0.5443747,   # monthly   (Moon's orbit)
    "Mf":  1.0980331,   # fortnightly
    "Q1": 13.3986609, "O1": 13.9430356, "P1": 14.9589314, "K1": 15.0410686,   # diurnal (~daily)
    "N2": 28.4397295, "M2": 28.9841042, "S2": 30.0000000, "K2": 30.0821373,   # semidiurnal (~twice daily)
    "M4": 57.9682084, "MS4": 58.9841042,                                       # shallow-water 'overtides'
}
freqs = {k: v / 360.0 for k, v in CONSTITUENTS.items()}    # cycles per hour
pd.Series(CONSTITUENTS, name="deg/hr").to_frame().assign(
    period_h=lambda d: 360.0 / d["deg/hr"])                 # period = 360 / speed
"""),
        seeing("The 'period_h' column is each wave's repeat time in hours. Note "
               "the families: ~12 h (semidiurnal), ~24 h (diurnal), and the slow "
               "fortnightly/monthly ones. M4/MS4 are 'overtides' created when the "
               "tide is distorted in shallow water."),
        md(r"""
## Step 3 · The least-squares fit (the heart of the method)

We claim the data $y(t)$ is approximately

$$y(t) \approx \underbrace{Z_0}_{\text{mean}} + \underbrace{c\,t}_{\text{slow drift}}
   + \sum_k \big[a_k\cos(2\pi f_k t) + b_k\sin(2\pi f_k t)\big].$$

Why cos **and** sin for each constituent? Because together they can make a wave
of *any* amplitude **and** any phase — and crucially the unknowns
$a_k, b_k$ enter **linearly**, so we can solve for them with ordinary
**least squares** (find the numbers that minimise the squared misfit). We add a
constant ($Z_0$) and a straight-line trend ($c\,t$) to soak up the mean level and
slow instrument drift.

In code: build a matrix `X` whose columns are `[1, t, cos(2πf₁t), sin(2πf₁t),
cos(2πf₂t), …]`, then `np.linalg.lstsq` finds the best coefficients. From each
cos/sin pair we recover amplitude $A_k=\sqrt{a_k^2+b_k^2}$ and phase
$\phi_k=\operatorname{atan2}(b_k,a_k)$.
"""),
        keyterm("Least squares", "the workhorse fitting method: pick the "
                "coefficients that make the total squared difference between the "
                "model and the data as small as possible. One line: "
                "`np.linalg.lstsq`."),
        code("""
# x-axis for the fit = hours since the first sample (a plain number, not a date)
t_hours = ((s.index - s.index[0]) / pd.Timedelta(hours=1)).values.astype(float)
y = s.values.astype(float)

# Build the design matrix X, one column at a time.
cols  = [np.ones_like(t_hours), t_hours]        # column 0 = mean (Z0), column 1 = linear trend
names = ["mean", "trend"]
for name, f in freqs.items():
    w = 2 * np.pi * f                            # angular frequency
    cols  += [np.cos(w * t_hours), np.sin(w * t_hours)]
    names += [f"{name}_cos", f"{name}_sin"]
X = np.column_stack(cols)

# Solve  X @ beta ≈ y  in the least-squares sense.
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
coef = dict(zip(names, beta))

# Convert each cos/sin pair into amplitude & phase.
rows = []
for name, f in freqs.items():
    a, b = coef[f"{name}_cos"], coef[f"{name}_sin"]
    rows.append({"constituent": name, "period_h": 1 / f,
                 "amplitude": np.hypot(a, b),                     # sqrt(a^2 + b^2)
                 "phase_deg": np.degrees(np.arctan2(b, a)) % 360})
amps = pd.DataFrame(rows).set_index("constituent").sort_values("amplitude", ascending=False)
amps.round(2)
"""),
        seeing("The table is your tidal fingerprint for this site, sorted biggest "
               "first. For the US Pacific NW you should see **M2** on top, with "
               "**K1, S2, O1, N2** following — the classic ranking for this coast."),
        md("### Visualise the constituent amplitudes"),
        code("""
fig, ax = plt.subplots(figsize=(10, 4))
amps_sorted = amps.sort_values("amplitude")
ax.barh(amps_sorted.index, amps_sorted["amplitude"], color="C0")
ax.set_xlabel("amplitude [dbar ≈ m]"); ax.set_title(f"{STATION} tidal constituent amplitudes")
plt.tight_layout(); ol.savefig(fig, f"04_{STATION}_constituents.png"); plt.show()

# The 'form factor' classifies the tide's character in one number.
F = ((amps.loc['K1','amplitude'] + amps.loc['O1','amplitude']) /
     (amps.loc['M2','amplitude'] + amps.loc['S2','amplitude']))
kind = ("semidiurnal" if F < 0.25 else "mixed, mainly semidiurnal" if F < 1.5
        else "mixed, mainly diurnal" if F < 3 else "diurnal")
print(f"Form factor F = (K1+O1)/(M2+S2) = {F:.2f}  ->  {kind} tide")
"""),
        keyterm("Form factor F", "(K1+O1)/(M2+S2). A single number describing tide "
                "type: <0.25 semidiurnal (two equal tides/day), 0.25–1.5 mixed "
                "mainly semidiurnal, 1.5–3 mixed mainly diurnal, >3 diurnal "
                "(one tide/day)."),
        md(r"""
## Step 4 · Predict the tide, then subtract it

Now we *rebuild* the tide using only the constituent terms (keep the mean so the
curve sits at the right level, but **drop the linear-trend term** so the leftover
residual still contains the real slow sea-level changes we want to study).

**Residual = observed − predicted tide.** This is the de-tided signal — the
ocean's "weather".
"""),
        code("""
# Reconstruct the tide from the fitted coefficients.
tide_only = np.full_like(y, coef["mean"])                 # start at the mean level
for name, f in freqs.items():
    w = 2 * np.pi * f
    tide_only += coef[f"{name}_cos"]*np.cos(w*t_hours) + coef[f"{name}_sin"]*np.sin(w*t_hours)

tide  = pd.Series(tide_only, index=s.index)
resid = s - tide                                          # <-- the de-tided signal
var_explained = 1 - resid.var() / s.var()
print(f"Variance explained by the tidal fit: {100*var_explained:.1f}%")

fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
axes[0].plot(s.index, s.values, "C7", lw=0.6, label="observed")
axes[0].plot(tide.index, tide.values, "C1", lw=0.6, label="predicted tide")
axes[0].legend(loc="upper right"); axes[0].set_title(f"{STATION} · observed vs predicted tide")
axes[1].plot(resid.index, resid.values, "C2", lw=0.6)
axes[1].set_title("residual = observed − tide  (the non-tidal / 'subtidal' signal)")
axes[2].plot(resid.index, resid.rolling(30, center=True, min_periods=1).mean().values, "C3", lw=1.0)
axes[2].set_title("residual smoothed over 30 h  (storm-surge / weather band)")
for a in axes: a.set_ylabel("pressure [dbar]")
plt.tight_layout(); ol.savefig(fig, f"04_{STATION}_detide.png"); plt.show()
"""),
        seeing("**Top:** the orange predicted tide should sit almost exactly on "
               "the grey data — that's the 'variance explained' number (typically "
               ">99% for pressure here). **Middle:** the residual is tiny by "
               "comparison and looks irregular — that's the point, the clockwork "
               "tide is gone. **Bottom:** smoothing the residual reveals slow "
               "bumps that are real ocean/weather events, not tides."),
        md("### Zoom in on the first week to check the fit by eye"),
        code("""
sl = slice(s.index[0], s.index[0] + pd.Timedelta(days=7))
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(s.loc[sl].index, s.loc[sl].values, "C7", lw=1, label="observed")
ax.plot(tide.loc[sl].index, tide.loc[sl].values, "C1--", lw=1, label="predicted tide")
ax.legend(); ax.set_title(f"{STATION} · first 7 days: data vs prediction"); ax.set_ylabel("pressure [dbar]")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
plt.tight_layout(); ol.savefig(fig, f"04_{STATION}_detide_zoom.png"); plt.show()
"""),
        seeing("The dashed prediction should trace the data almost perfectly, "
               "capturing both the twice-daily humps and the unequal heights of "
               "successive highs (the 'mixed' character F told us about)."),
        md(r"""
## Step 4b · Is it overfitting? An out-of-sample check

A 99%+ "variance explained" can be a lie if we just fit noise. The honest test
of any predictive model is **out-of-sample skill**: fit on data it *hasn't* seen,
then predict. Here we fit the constituents on the **first half** of the record
and use them to predict the **second half**. If the tide is real (it is), the
two scores should be almost equal. A big drop would mean overfitting.
"""),
        code("""
n = len(s); half = n // 2
Xh = X[:half]                                   # design matrix, first half only
beta_half, *_ = np.linalg.lstsq(Xh, y[:half], rcond=None)

def predict_tide(beta_vec):
    out = np.full_like(t_hours, beta_vec[0])     # mean, no trend
    for j, f in enumerate(freqs.values()):
        w = 2 * np.pi * f
        out += beta_vec[2 + 2*j] * np.cos(w * t_hours) + beta_vec[3 + 2*j] * np.sin(w * t_hours)
    return out

pred = predict_tide(beta_half)
ve_in  = 1 - np.var(y[:half] - pred[:half]) / np.var(y[:half])
ve_out = 1 - np.var(y[half:] - pred[half:]) / np.var(y[half:])
print(f"Fit on first half, score on each half:")
print(f"   in-sample  (first half) : {100*ve_in:5.2f}%")
print(f"   OUT-OF-SAMPLE (2nd half): {100*ve_out:5.2f}%   <-- the number that matters")
print("Near-equal scores  ->  the tidal fit genuinely predicts unseen data (not overfitting).")
"""),
        seeing("The two percentages come out within a fraction of a percent of "
               "each other (~99.4% vs ~99.7%). That tiny gap is the proof: the "
               "constituents we solved for predict data they were never shown, so "
               "we're capturing real tidal physics, not fitting noise."),
        md(r"""
## Step 5 · Prove it with a spectrum

A **spectrum** (periodogram) shows how much of a signal's energy sits at each
frequency — sharp spikes mean strong periodic waves. If de-tiding worked, the
spikes at the **diurnal (~1 cycle/day)** and **semidiurnal (~2 cycles/day)**
bands should collapse in the residual.
"""),
        keyterm("Spectrum / periodogram", "a plot of signal energy vs frequency. "
                "A pure tide shows tall narrow spikes at its constituent "
                "frequencies; random 'weather' is broad and low."),
        code("""
from scipy.signal import welch
fs = 1.0  # sampling frequency in cycles per hour (data is hourly)
for label, ser in [("observed", s), ("residual", resid)]:
    f, P = welch(ser.values - ser.values.mean(), fs=fs, nperseg=min(1024, len(ser)))
    plt.semilogy(f * 24, P, lw=0.9, label=label)        # x converted to cycles/DAY
plt.axvline(1, ls=":", c="k", lw=0.8); plt.axvline(2, ls=":", c="k", lw=0.8)
plt.text(1, plt.ylim()[1], " diurnal", va="top", fontsize=8)
plt.text(2, plt.ylim()[1], " semidiurnal", va="top", fontsize=8)
plt.xlim(0, 4); plt.xlabel("frequency [cycles/day]"); plt.ylabel("energy (log scale)")
plt.title(f"{STATION} · spectrum before vs after de-tiding"); plt.legend()
plt.tight_layout(); ol.savefig(plt.gcf(), f"04_{STATION}_spectra.png"); plt.show()
"""),
        seeing("The 'observed' curve has towering spikes at 1 and 2 cycles/day. In "
               "the 'residual' curve those spikes drop by orders of magnitude "
               "(note the log y-axis) — direct proof the tide was removed and "
               "only the broadband non-tidal signal remains."),
        md("""
## Step 6 · (Optional) cross-check with the `utide` package

Everything above is hand-built so you can see the mechanism. In real work people
use **`utide`**, a packaged version of this same least-squares method that also
adds professional touches (18.6-year 'nodal' corrections, confidence intervals).
This cell runs it *if it's installed*; otherwise it tells you how to get it.
"""),
        code("""
try:
    import utide
    coef_u = utide.solve(s.index.to_pydatetime(), s.values,
                         lat=45.8, method="ols", conf_int="MC", verbose=False)
    rec = utide.reconstruct(s.index.to_pydatetime(), coef_u, verbose=False)
    resid_u = s.values - rec.h
    print("utide variance explained: %.1f%%" % (100*(1 - np.var(resid_u)/np.var(s.values))))
    top = pd.DataFrame({"name": coef_u["name"], "A": coef_u["A"]}).set_index("name")
    print(top.sort_values("A", ascending=False).head(8).round(1))
except ImportError:
    print("utide not installed — the NumPy fit above is fully self-contained.")
    print("To enable this cross-check, run:  pip install utide")
"""),
        exercise(
            "Re-run the whole notebook with `STATION='HYS14'` or `'HYSB1'`. Do the top constituents change?",
            "Make `t1 = t0 + pd.Timedelta(days=180)` (6 months). Does the fit improve? (Hint: longer records separate close constituents better.)",
            "De-tide TEMPERATURE instead of pressure: change 'pressure' to 'temperature' in Step 1. How much variance does the tide explain there?",
            "Remove M4/MS4 from CONSTITUENTS and re-run. Does variance-explained drop much? (They matter more in shallow water.)",
        ),
        md(r"""
---
## ✅ Recap & important caveats

**You did it:** you measured the tidal constituents at a real seafloor site by
least squares, used them to predict the tide, subtracted it, and proved (via the
spectrum) that the non-tidal residual is what's left. This *is* the Thomson &
Emery harmonic method.

A few honest caveats to remember:

* **Units.** Pressure is reported in **dbar** (oceanlib converts the raw counts
  at 1e-4 dbar/count). Since 1 dbar ≈ 1.02 m of seawater, the constituent
  amplitudes are effectively in **metres of sea level** — note M2 comes out
  ≈0.83 m, the textbook NE-Pacific value, a nice sanity check on the whole chain.
  The conversion factor isn't shipped in the files; it was pinned down from the
  three sites' known depths and that M2 value (see `oceanlib.COUNTS_PER_DBAR`).
* **Record length sets resolution.** To cleanly separate two nearby
  constituents you need a record at least as long as one full "beat" between
  them (the **Rayleigh criterion**): S2 vs K2 needs ~182 days, P1 vs K1 ~183
  days. With 60 days the *big* constituents (M2, K1, S2, O1) are rock-solid —
  they barely move when you refit on 60 vs 480 days — but the small close-pair
  ones (**K2, P1**) wobble ~10%. They're tiny, so this barely affects the
  *removal*; just don't quote their individual amplitudes precisely. Rerun on a
  longer window to sharpen them (AXBA1 has 491 contiguous days).
* **Long-period constituents on short records.** **Mm** has a ~27.6-day period,
  so a 60-day record contains only ~2 cycles of it — its amplitude is poorly
  constrained and it can soak up genuine *non-tidal* low-frequency energy
  (weather, eddies). If your goal is to *study* the subtidal residual, consider
  dropping `Mm` (and even `Mf`) from `CONSTITUENTS`, or use a much longer record.
* **What the phases mean here.** The `phase_deg` we report is measured **relative
  to the first sample of this record**, not the standard astronomical
  (Greenwich) reference used in published harmonic constants. They're correct for
  *predicting/removing* the tide in this series, but **don't compare them to
  tide-table values** — for that you'd need the astronomical argument corrections
  that `utide` applies.
* **Hourly averaging.** We fit hourly means, which gently smooth the fastest
  constituents (M4/MS4, ~6 h) by ~1–2%. Negligible here, and it doubles as
  anti-aliasing. Don't try to fit anything with a period under ~2 hours from
  hourly data (the Nyquist limit).
* **Nodal corrections.** The Moon's orbit slowly wobbles over 18.6 years,
  modulating constituent amplitudes. Our hand fit ignores this; `utide` includes
  it. For records of a year or less the effect is small.

**Where to go next:** apply this to temperature to study internal tides; compare
constituents between the three stations; or feed the residual into storm-surge
or current analysis.
"""),
    ]
    return nb


# ===========================================================================
# 05 — Current-meter data (velocity)
# ===========================================================================
def nb05():
    nb = new_notebook()
    nb.cells = [
        md("""
# 05 · Current-meter data — water velocity

This notebook uses the **other** dataset: the `currentmeter/` folder, which holds
a seafloor **current meter**. Unlike the pressure gauge (a single number), a
current meter measures the **velocity of the water** — a *vector* — broken into
three components:

| channel | component | meaning | units |
|---------|-----------|---------|-------|
| `LOE` | **east**  | + = flowing east  | m/s |
| `LON` | **north** | + = flowing north | m/s |
| `LOZ` | **up**    | + = flowing upward | m/s |
| `LKO` | temperature | — | °C |

From the east/north pair we get the two numbers people usually want: **speed**
(how fast) and **direction** (which way). This notebook builds the standard
current-meter views from those.
"""),
        objectives(
            "Load 3-component velocity into one tidy table with `ol.load_current`",
            "Convert east/north into speed & direction",
            "Read a stick (vector) plot and a progressive vector diagram",
            "Read a current rose (where the water goes, how fast)",
            "Relate the currents to the tide from notebook 04",
        ),
        questions(
            "Which compass direction does the current mostly flow along? Does it reverse back-and-forth or rotate?",
            "How fast is a typical current here? Is that big or small compared with surface ocean currents?",
            "Does the current speed pulse in step with the tide? When in the tidal cycle is it fastest?",
            "From the progressive vector diagram, is there a net drift, or mostly tidal sloshing?",
        ),
        md("""
> ⚠️ **Data note (read me).** This is a *partial download* — right now the
> current meter data is essentially all from one station (**HYSB1**); more
> stations will arrive later. Everything below **discovers the available stations
> automatically** (`ol.current_stations()`), so it will just work when they do.
> The loader also runs **quality control**: bottom currents here are well under
> 1 m/s, so any sample faster than `ol.CUR_QC_MAX` (3 m/s) is treated as a
> fill/spike value and masked out.
"""),
        code(SETUP),
        code("""
print("Current-meter stations available:", ol.current_stations())
STATION = ol.primary_current_station()     # the station with the most data (auto)
win = ol.current_window(STATION)            # a clean, gap-free window for it (auto)
print("Using station:", STATION, "| window:", win)
"""),
        md("""
## What the loaded data looks like

`ol.load_current` returns a tidy DataFrame: one row per time, columns for each
velocity component plus derived `speed` and `dir`. Let's load one day at full
1-second resolution.
"""),
        code("""
day = pd.Timestamp(win["start"]) + pd.Timedelta(days=10)
cur = ol.load_current(STATION, day, day)        # full-rate, one day
cur[["east", "north", "up", "speed", "dir"]].describe().round(3)
"""),
        seeing("`east`/`north`/`up` are velocities in m/s and can be **negative** "
               "(west/south/down). `speed` = √(east²+north²) is the horizontal "
               "current strength (always ≥ 0). `dir` is the compass heading the "
               "water flows *toward* (0°=N, 90°=E). Speeds here are small "
               "(centimetres/second) — typical for the deep seafloor."),
        md("## The three velocity components over one day"),
        code("""
fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
for ax, comp, c in zip(axes, ["east", "north", "up"], ["C0", "C1", "C2"]):
    ax.plot(cur.index, cur[comp], c, lw=0.6)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_ylabel(f"{comp} [m/s]")
axes[0].set_title(f"{STATION} · velocity components · {day.date()}")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_components_day.png"); plt.show()
"""),
        seeing("Each component swings above and below zero. If the swings have a "
               "~12-hour rhythm, that's the **tidal current** — the same tide from "
               "notebook 04, but now we see it pushing water back and forth, not "
               "just up and down."),
        md("## Speed and direction"),
        code("""
fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
axes[0].plot(cur.index, cur["speed"], "C3", lw=0.6); axes[0].set_ylabel("speed [m/s]")
axes[1].plot(cur.index, cur["dir"], ".", ms=1, color="C4"); axes[1].set_ylabel("direction [° toward]")
axes[1].set_ylim(0, 360); axes[1].set_yticks([0, 90, 180, 270, 360])
axes[1].set_yticklabels(["N", "E", "S", "W", "N"])
axes[0].set_title(f"{STATION} · current speed & direction · {day.date()}")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_speed_dir_day.png"); plt.show()
"""),
        seeing("When the tide reverses, speed dips toward zero (slack water) and "
               "the direction flips by ~180° — the classic back-and-forth of a "
               "tidal current. Direction is plotted as dots because it's "
               "meaningless to draw a line across the 360°→0° wrap."),
        md("""
## Stick (vector) plot

A stick plot draws the current as little arrows along the time axis — the
clearest single picture of a current record. Each arrow points the way the water
is flowing and its length is the speed. We thin to one arrow per ~30 min so they
don't overlap.
"""),
        code("""
s = cur.resample("30min").mean().dropna(subset=["east", "north"])
fig, ax = plt.subplots(figsize=(13, 3.5))
t = mdates.date2num(s.index.to_pydatetime())
ax.quiver(t, np.zeros(len(s)), s["east"], s["north"],
          angles="uv", scale=3, width=0.0015, color="C0")
ax.axhline(0, color="k", lw=0.5)
ax.set_yticks([]); ax.set_ylabel("current vector")
ax.set_title(f"{STATION} · stick plot (arrow = flow direction & speed) · {day.date()}")
ax.xaxis_date(); ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_stickplot.png"); plt.show()
"""),
        seeing("Arrows pointing up = water heading north, right = east, etc. Watch "
               "them swing back and forth (or rotate) over the tidal cycle. A "
               "steady lean in one direction across the whole day is the *mean* "
               "(non-tidal) current."),
        md("""
## Progressive vector diagram — *where would a water parcel go?*

If you follow the current and add up all its little steps (velocity × time), you
trace the path a drifting parcel of water *would* take. It's not a real
trajectory (the meter sits still), but it's a great way to see net transport.
We use the longer window here, decimated to 10-minute steps.
"""),
        code("""
trk = ol.load_current(STATION, win["start"], win["end"], rule="10min").dropna(subset=["east", "north"])
dt = 600.0  # seconds per 10-min step
# integrate velocity -> displacement, convert m -> km
x = (trk["east"] * dt).cumsum() / 1000.0
y = (trk["north"] * dt).cumsum() / 1000.0

fig, ax = plt.subplots(figsize=(7, 7))
sc = ax.scatter(x, y, c=mdates.date2num(trk.index.to_pydatetime()), s=2, cmap="viridis")
ax.plot(x.iloc[0], y.iloc[0], "go", label="start"); ax.plot(x.iloc[-1], y.iloc[-1], "rs", label="end")
ax.set_aspect("equal"); ax.set_xlabel("east displacement [km]"); ax.set_ylabel("north displacement [km]")
ax.legend(); ax.set_title(f"{STATION} · progressive vector diagram · {win['start']}→{win['end']}")
cb = fig.colorbar(sc, ax=ax); cb.ax.yaxis.set_major_formatter(mdates.DateFormatter("%b"))
plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_progressive_vector.png"); plt.show()
"""),
        seeing("Tight loops/zig-zags are the tide sloshing back and forth (no net "
               "travel). A steady drift of the whole curve in one direction is the "
               "**mean current** carrying water that way over weeks. The colour "
               "shows time, so you can see how the net direction evolves."),
        md("""
## Current rose — the direction/speed climate

A current rose is a polar histogram: each wedge points in a compass direction,
its length is how *often* the current flowed that way, and the colours split that
by speed. It summarises months of data in one picture.
"""),
        code("""
rose = ol.load_current(STATION, win["start"], win["end"], rule="10min").dropna(subset=["speed", "dir"])
nbins = 16
ang = np.deg2rad(np.arange(0, 360, 360 / nbins))
width = 2 * np.pi / nbins
spd_bins = [0, 0.05, 0.1, 0.2, 0.5, np.inf]
colors = plt.cm.viridis(np.linspace(0, 1, len(spd_bins) - 1))

fig = plt.figure(figsize=(7, 7)); ax = fig.add_subplot(111, projection="polar")
ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)   # compass: N up, clockwise
# which direction-wedge each sample falls in (centred on each compass point)
dir_bin = ((((rose["dir"] + 360 / nbins / 2) % 360) // (360 / nbins)).astype(int)) % nbins
bottom = np.zeros(nbins)
for k in range(len(spd_bins) - 1):
    lo, hi = spd_bins[k], spd_bins[k + 1]
    sel = (rose["speed"] >= lo) & (rose["speed"] < hi)
    counts = np.bincount(dir_bin[sel], minlength=nbins)
    frac = 100 * counts / len(rose)                       # % of all samples
    lbl = f"{lo}–{hi if np.isfinite(hi) else '∞'} m/s"
    ax.bar(ang, frac, width=width, bottom=bottom, color=colors[k],
           edgecolor="w", linewidth=0.3, label=lbl)
    bottom += frac
ax.set_title(f"{STATION} · current rose (flow toward) · {win['start']}→{win['end']}")
ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05), fontsize=8, title="speed")
plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_current_rose.png"); plt.show()
"""),
        seeing("Long wedges show the directions the current most often flows "
               "toward; if two opposite wedges dominate, the flow is a "
               "back-and-forth tidal jet aligned with that axis. The colour mix "
               "tells you whether the fast events come from a particular direction."),
        md("""
## Do the currents follow the tide?

Notebook 04 found the tide in **pressure**. Here we overlay current **speed**
against the **pressure** record over the same window — if the current is tidal,
its speed should pulse in step with the rise and fall of the tide.
"""),
        code("""
a, b = win["start"], win["end"]
spd = ol.load_current(STATION, a, b, rule="1h")["speed"]
press = ol.load_decimated(STATION, "pressure", a, b, rule="1h")
both = pd.concat({"speed": spd, "pressure": press}, axis=1).dropna()

if len(both) > 100:
    zoom = both.loc[both.index[0]:both.index[0] + pd.Timedelta(days=7)]
    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(zoom.index, zoom["pressure"], "C0", lw=0.8)
    ax1.set_ylabel("pressure [dbar]", color="C0"); ax1.tick_params(axis="y", colors="C0")
    ax2 = ax1.twinx(); ax2.plot(zoom.index, zoom["speed"], "C3", lw=0.8)
    ax2.set_ylabel("current speed [m/s]", color="C3"); ax2.tick_params(axis="y", colors="C3"); ax2.grid(False)
    ax1.set_title(f"{STATION} · tide (pressure) vs current speed · first 7 days")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.tight_layout(); ol.savefig(fig, f"05_{STATION}_current_vs_tide.png"); plt.show()
    print(f"{len(both)} overlapping hours of current + pressure.")
else:
    print("Not enough overlapping current+pressure data in this window "
          f"({len(both)} hrs) — likely a different station/period once more data lands.")
"""),
        seeing("Tidal currents typically run *fastest midway between* high and low "
               "tide (when the water is moving most) and go slack at the turning "
               "points — so current-speed peaks often sit between the pressure "
               "peaks and troughs. A formal version of this is harmonic analysis "
               "of the east/north components (tidal-current ellipses) — the same "
               "Thomson & Emery machinery from notebook 04, applied to velocity."),
        exercise(
            "Re-run with a different station once more data arrives: set `STATION = 'HYS14'`.",
            "Change the stick-plot `day` to a spring vs a neap day — are the arrows longer at spring?",
            "In the progressive vector diagram, switch `rule` to '1h' — does the net path change shape?",
            "Compute the mean current vector for the whole window: `cur[['east','north']].mean()` — which way does the water go on average?",
        ),
        recap(
            "You loaded 3-component current-meter velocity (with automatic QC and "
            "station discovery), turned it into speed/direction, and read it as "
            "components, a stick plot, a progressive vector diagram, and a current "
            "rose — then tied the currents back to the tide. The code scales to "
            "new stations automatically as your downloads complete.",
            nxt="add more stations to `currentmeter/`, then just re-run — or extend this into tidal-current-ellipse harmonic analysis."),
    ]
    return nb


# ===========================================================================
# 06 — Relating the tide (pressure) and the currents
# ===========================================================================
def nb06():
    nb = new_notebook()
    nb.cells = [
        md(r"""
# 06 · Are the tide and the currents related?

We have two co-located instruments at the same site: a **pressure gauge** (the
tide / sea level, notebooks 00–04) and a **current meter** (water velocity,
notebook 05). The same Moon-and-Sun tide drives *both*, so they ought to be
related — but *how* exactly? This notebook runs several complementary tests on
the **overlapping period** where both recorded.

We'll move from "do they look related?" to "they are coherent at the tidal
frequencies, and the current leads the tide by ~X hours" — a quantitative answer.
"""),
        objectives(
            "Combine pressure and current onto one aligned hourly time base",
            "Reduce the vector current to its main axis (the tidal-current direction)",
            "Test relatedness with: overlay, lagged cross-correlation, coherence spectrum",
            "Measure the phase lag between tide and current per constituent (harmonic)",
            "Interpret the lag physically (progressive vs standing tidal wave)",
        ),
        questions(
            "At which frequencies are the tide and current most coherent? What does that tell you about what drives the currents?",
            "Does the current lead or lag the tide, and by roughly how many hours?",
            "Is that lead/lag consistent across the major constituents (M2, K1, O1)? Why does consistency matter?",
            "Do the cross-correlation lag and the harmonic M2 lag agree?",
            "Based on the phase lag, is this closer to a progressive or a standing tidal wave?",
            "Overall: are the tide and the currents related? What's your evidence?",
        ),
        md(r"""
## The physics, briefly

Think of the tide as a wave. There are two textbook end-members:

* **Progressive wave** (like a wave rolling across open water): the current is
  **strongest at high and low tide** and slack in between — current and elevation
  are *in phase* (0° apart).
* **Standing wave** (sloshing in a basin): the current is **strongest at
  mid-tide** and slack at the extremes — current and elevation are *90° apart*
  (in "quadrature").

Real coasts are a mix. So the **phase lag** we measure between pressure and
current is physically meaningful — it tells us which behaviour dominates here.
"""),
        keyterm("In phase / quadrature", "two oscillations are 'in phase' when "
                "their peaks line up (0°), 'in quadrature' when one peaks while "
                "the other is at zero (90°). Tidal elevation vs current sits "
                "somewhere between, depending on the wave type."),
        keyterm("Coherence", "a frequency-by-frequency correlation (0–1). High "
                "coherence at a frequency means the two signals move together "
                "there — even if elsewhere they don't. The tidal test: is "
                "coherence high at the diurnal & semidiurnal bands?"),
        code(SETUP),
        code("""
STATION = ol.primary_current_station()       # station with both current + pressure
win = ol.current_window(STATION)
a, b = win["start"], win["end"]
print(f"Station {STATION}, window {a} → {b}")

cur = ol.load_current(STATION, a, b, rule="1h")              # current (m/s), hourly, QC'd
press = ol.load_decimated(STATION, "pressure", a, b, rule="1h")  # pressure (dbar), hourly

df = pd.concat({"press": press, "east": cur["east"], "north": cur["north"]}, axis=1).dropna()
print(f"{len(df)} hours where BOTH instruments have good data "
      f"({df.index[0].date()} → {df.index[-1].date()})")
"""),
        md("""
## Step 1 · Reduce the current to one number: the tidal-current axis

The current is a 2-D vector, but tidal currents mostly oscillate **back and forth
along one axis**. We find that axis with a quick principal-component analysis
(`ol.principal_axis`) and project the current onto it — giving a single scalar
"along-axis current" we can compare directly with the tide.
"""),
        code("""
v, orient, u_major = ol.principal_axis(df["east"], df["north"])
print(f"Tidal-current axis orientation: {orient:.0f}° from North "
      f"(unit vector east={v[0]:.2f}, north={v[1]:.2f})")

# show the velocity scatter and the fitted axis
fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.scatter(df["east"] - df["east"].mean(), df["north"] - df["north"].mean(), s=2, alpha=0.2)
lim = np.nanpercentile(np.abs(np.r_[df["east"]-df["east"].mean(), df["north"]-df["north"].mean()]), 99)
ax.plot([-v[0]*lim, v[0]*lim], [-v[1]*lim, v[1]*lim], "r-", lw=2, label="principal axis")
ax.set_aspect("equal"); ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
ax.set_xlabel("east velocity anomaly [m/s]"); ax.set_ylabel("north velocity anomaly [m/s]")
ax.legend(); ax.set_title(f"{STATION} · current scatter & principal axis ({orient:.0f}°)")
plt.tight_layout(); ol.savefig(fig, f"06_{STATION}_principal_axis.png"); plt.show()
"""),
        seeing("If the cloud is a tilted cigar, the current is strongly polarised "
               "along the red axis — a back-and-forth tidal jet. A round blob "
               "would mean the current rotates rather than reverses. The axis "
               "orientation tells you the compass line the tidal current runs along."),
        md("""
## Step 2 · Eyeball test — overlay the tidal parts

Both signals carry slow non-tidal drift that would obscure the comparison, so we
overlay the **tidal reconstructions** (from `ol.harmonic_fit`) of pressure and of
the along-axis current, each normalised to its own size, for one week.
"""),
        code("""
press_tide = ol.harmonic_fit(df["press"])["tide"]
curr_tide  = ol.harmonic_fit(u_major, t0=df.index[0])["tide"]
norm = lambda s: (s - s.mean()) / s.std()

wk = slice(df.index[0], df.index[0] + pd.Timedelta(days=7))
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(press_tide.loc[wk].index, norm(press_tide).loc[wk], "C0", lw=1.2, label="tide (pressure)")
ax.plot(curr_tide.loc[wk].index, norm(curr_tide).loc[wk], "C3", lw=1.2, label="along-axis current")
ax.axhline(0, color="k", lw=0.5); ax.legend(); ax.set_ylabel("normalised (σ units)")
ax.set_title(f"{STATION} · tidal pressure vs tidal current (first 7 days)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
plt.tight_layout(); ol.savefig(fig, f"06_{STATION}_overlay.png"); plt.show()
"""),
        seeing("Same rhythm, slightly offset: the two curves rise and fall "
               "together but their peaks don't land at exactly the same moment. "
               "That horizontal offset is the **phase lag** we quantify next. If "
               "the red current peaks consistently *before* the blue tide, the "
               "current leads."),
        md(r"""
## Step 3 · Lagged cross-correlation — how big is the time shift?

Slide the current against the tide and see which time shift makes them line up
best. The lag of the highest correlation is the dominant time offset between
them (dominated by the biggest constituent, M2).
"""),
        code("""
from scipy.signal import correlate, correlation_lags
x = norm(press_tide); y = norm(curr_tide.reindex(x.index))
m = x.notna() & y.notna(); x, y = x[m].values, y[m].values

corr = correlate(y, x, mode="full") / len(x)
lags = correlation_lags(len(y), len(x), mode="full")     # in hours (hourly data)
keep = np.abs(lags) <= 18                                 # look within ±18 h
k = np.argmax(corr[keep]); best_lag = lags[keep][k]

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(lags[keep], corr[keep], "C2")
ax.axvline(best_lag, color="r", ls="--", label=f"peak at {best_lag:+d} h")
ax.axvline(0, color="k", lw=0.5)
ax.set_xlabel("lag [hours]  (negative = current LEADS tide)"); ax.set_ylabel("correlation")
ax.legend(); ax.set_title(f"{STATION} · cross-correlation: current vs tide")
plt.tight_layout(); ol.savefig(fig, f"06_{STATION}_crosscorr.png"); plt.show()
print(f"Best alignment at {best_lag:+d} h, correlation {corr[keep][k]:.2f}  "
      f"({'current leads the tide' if best_lag < 0 else 'current lags the tide'}).")
"""),
        seeing("A tall, narrow peak near zero lag means a tight, fixed-phase "
               "relationship — strong evidence the two are the same forcing. The "
               "sign of the peak lag says whether the current runs ahead of or "
               "behind the tide."),
        md(r"""
## Step 4 · Coherence spectrum — *at which frequencies* are they related?

Cross-correlation gives one overall lag; coherence is sharper — it asks, for each
frequency separately, "do these two move together here?" For a tidally-driven
pair we expect coherence to **spike at the diurnal (1/day) and semidiurnal
(2/day) bands** and be low elsewhere.
"""),
        code("""
from scipy.signal import coherence, csd
fs = 1.0  # cycles/hour
yc = u_major.reindex(df.index).interpolate(limit=3)
xc = df["press"]
f, Cxy = coherence(xc.values, yc.values, fs=fs, nperseg=512)
_, Pxy = csd(yc.values, xc.values, fs=fs, nperseg=512)     # csd(current,press): phase = φ_curr−φ_press
cpd = f * 24                                                # x-axis in cycles/day

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
ax1.plot(cpd, Cxy, "C0"); ax1.set_ylabel("coherence²"); ax1.set_ylim(0, 1)
ax2.plot(cpd, np.degrees(np.angle(Pxy)), ".", ms=3, color="C3")
ax2.set_ylabel("phase [°]\\n(curr − press)"); ax2.set_ylim(-180, 180); ax2.set_yticks([-180,-90,0,90,180])
for ax in (ax1, ax2):
    for band in (1, 2): ax.axvline(band, color="k", ls=":", lw=0.8)
ax1.set_title(f"{STATION} · coherence & phase: current vs tide")
ax2.set_xlabel("frequency [cycles/day]"); ax2.set_xlim(0, 4)
plt.tight_layout(); ol.savefig(fig, f"06_{STATION}_coherence.png"); plt.show()

for band, fc in [("diurnal", 1/24), ("semidiurnal", 2/24)]:
    i = np.argmin(np.abs(f - fc))
    print(f"{band:12s} ({fc*24:.0f} cyc/day): coherence²={Cxy[i]:.2f}, phase={np.degrees(np.angle(Pxy))[i]:+.0f}°")
"""),
        seeing("Coherence should jump close to 1 right at the dotted lines (1 and "
               "2 cycles/day) and sag between them — proof the relationship lives "
               "specifically in the tidal bands. The phase panel, read *at those "
               "spikes only* (phase is meaningless where coherence is low), gives "
               "the lead/lag angle between current and tide at each band."),
        md(r"""
## Step 5 · Per-constituent phase lag (the precise answer)

Finally, fit the same tidal constituents to **both** signals with a shared time
origin (so phases are comparable) and tabulate, for each constituent:

* the **amplitude ratio** (current per unit tide — an "admittance"),
* the **phase lag** in degrees and in **hours**.
"""),
        code("""
con = ["Q1", "O1", "K1", "N2", "M2", "S2"]
fp = ol.harmonic_fit(df["press"], con)
fc = ol.harmonic_fit(u_major, con, t0=df.index[0])

rows = []
for k in con:
    pa, ca = fp["amps"].loc[k], fc["amps"].loc[k]
    dphi = (ca["phase_deg"] - pa["phase_deg"]) % 360
    dphi = dphi - 360 if dphi > 180 else dphi          # wrap to (-180, 180]
    rows.append({"constituent": k, "period_h": round(pa["period_h"], 2),
                 "tide_amp_dbar": round(pa["amplitude"], 4),
                 "curr_amp_ms": round(ca["amplitude"], 4),
                 "phase_lag_deg": round(dphi, 0),
                 "lag_hours": round(dphi / 360 * pa["period_h"], 2)})
tbl = pd.DataFrame(rows).set_index("constituent")
print("(phase_lag / lag_hours: negative = current LEADS the tide)")
tbl
"""),
        code("""
# Visualise the lead/lag of the major constituents
fig, ax = plt.subplots(figsize=(9, 4))
big = tbl.sort_values("tide_amp_dbar", ascending=False)
ax.bar(big.index, big["lag_hours"], color=np.where(big["lag_hours"] < 0, "C3", "C0"))
ax.axhline(0, color="k", lw=0.8)
ax.set_ylabel("current lead(−)/lag(+) vs tide [h]")
ax.set_title(f"{STATION} · per-constituent timing of current relative to tide")
plt.tight_layout(); ol.savefig(fig, f"06_{STATION}_phase_lag.png"); plt.show()
"""),
        seeing("The dominant constituents (M2, K1) should show a consistent, "
               "modest lead/lag of a couple of hours — not random values. "
               "Consistency across constituents is itself evidence the "
               "relationship is real tidal physics. A lag near 0 h would indicate "
               "a progressive-wave regime; near ±3 h (≈90° at M2) a standing-wave "
               "regime; in between, mixed."),
        exercise(
            "Re-run for another station once its current data lands (`STATION = 'HYS14'`).",
            "Compare the M2 lag from cross-correlation (Step 3) with the M2 lag in the table (Step 5) — do they agree?",
            "Project the current onto the MINOR axis instead (use the other eigenvector) — is it coherent with the tide too?",
            "Repeat the coherence test with TEMPERATURE vs tide instead of current — is temperature tidally coherent here?",
        ),
        recap(
            "You combined the two instruments, reduced the current to its tidal "
            "axis, and showed they're related four ways: a phased overlay, a "
            "sharp cross-correlation peak, high coherence confined to the tidal "
            "bands, and consistent per-constituent phase lags. Together these say "
            "the currents and the tide are the same forcing — and quantify how the "
            "current leads/lags the rise and fall of sea level.",
            nxt="extend to tidal-current ellipses (fit M2 to east & north separately) or compare lags across stations as more data arrives."),
    ]
    return nb


def main():
    import sys
    builders = {
        "00_dataset_overview.ipynb": nb00,
        "01_signals_separately.ipynb": nb01,
        "02_signals_together.ipynb": nb02,
        "03_daily_plots.ipynb": nb03,
        "04_detide_harmonic_analysis.ipynb": nb04,
        "05_current_meter.ipynb": nb05,
        "06_tide_current_relationship.ipynb": nb06,
    }
    # Build only the notebooks named on the command line; default = all.
    # (Lets us regenerate one notebook without wiping others' executed outputs.)
    targets = [a for a in sys.argv[1:]] or list(builders)
    for fn in targets:
        nb = builders[fn]()
        nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
        with open(fn, "w") as f:
            nbf.write(nb, f)
        print("wrote", fn)


if __name__ == "__main__":
    main()
