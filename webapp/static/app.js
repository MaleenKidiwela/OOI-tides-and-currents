"use strict";

// ---- element handles -------------------------------------------------------
const el = (id) => document.getElementById(id);
const stationSel = el("station");
const channelSel = el("channel");
const startInp = el("start");
const endInp = el("end");
const tTemp = el("t-temp");
const tDetide = el("t-detide");
const tCurrent = el("t-current");
const loadBtn = el("load");
const statusEl = el("status");
const infoEl = el("info");
const tideEl = el("tide");

let META = null; // /api/meta payload, keyed by station code

// ---- helpers ---------------------------------------------------------------
function setStatus(msg, isErr = false) {
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("err", !!isErr);
}

// datetime-local wants "YYYY-MM-DDTHH:MM:SS" in local wall-clock; we treat the
// values as UTC and hand them to the API verbatim (the API parses them as UTC).
function toInputValue(dateStr, addDays = 0) {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + addDays);
  return d.toISOString().slice(0, 19); // drop trailing Z + ms
}

async function getJSON(url) {
  const r = await fetch(url);
  const text = await r.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    // Not JSON — usually an HTML error page (e.g. something else answering the
    // port). Surface a readable message instead of a raw JSON-parse error.
    const path = url.split("?")[0];
    throw new Error(`Server returned non-JSON (HTTP ${r.status}) from ${path}. ` +
      `Is the Flask app the thing answering this port? First bytes: ${text.slice(0, 80)}`);
  }
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}

function station() { return META[stationSel.value]; }

// ---- bootstrap: load station metadata --------------------------------------
async function init() {
  setStatus("Loading station list…");
  const meta = await getJSON("/api/meta");
  META = {};
  for (const s of meta.stations) META[s.code] = s;

  stationSel.innerHTML = meta.stations
    .map((s) => `<option value="${s.code}">${s.code} — ${s.name}</option>`)
    .join("");
  stationSel.addEventListener("change", onStationChange);
  loadBtn.addEventListener("click", () => run().catch((e) => setStatus(e.message, true)));
  onStationChange();
  setStatus("Ready. Choose a window and click “Load & plot”.");
}

function onStationChange() {
  const s = station();
  channelSel.innerHTML = (s.pressure_channels || [])
    .map((c) => `<option value="${c}">${c}</option>`).join("");
  // Default to a 30-day view inside the station's known-good demo window.
  if (s.demo) {
    startInp.value = toInputValue(s.demo.start, 0);
    endInp.value = toInputValue(s.demo.start, 30);
  }
  tCurrent.disabled = !s.has_current;
  if (!s.has_current) tCurrent.checked = false;
  renderInfo();
}

function renderInfo() {
  const s = station();
  const cov = s.coverage ? `${s.coverage.start} → ${s.coverage.end}` : "—";
  const curr = s.has_current ? "yes" : "no";
  infoEl.innerHTML = [
    `<span><b>${s.name}</b> (${s.code})</span>`,
    `<span>lat <b>${s.lat}</b>°, lon <b>${s.lon}</b>°</span>`,
    `<span>depth <b>${s.depth_m}</b> m</span>`,
    `<span>coverage <b>${cov}</b></span>`,
    `<span>current meter: <b>${curr}</b></span>`,
  ].join("");
}

// ---- the main action -------------------------------------------------------
async function run() {
  const sta = stationSel.value;
  const start = startInp.value;
  const end = endInp.value;
  const channel = channelSel.value;
  if (!start || !end) { setStatus("Pick a start and end.", true); return; }

  loadBtn.disabled = true;
  tideEl.innerHTML = "";
  setStatus("Loading data…");
  const q = `station=${sta}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;

  try {
    // Always fetch pressure; add temperature only if ticked.
    const vars = tTemp.checked ? "pressure,temperature" : "pressure";
    const jobs = { series: getJSON(`/api/series?${q}&vars=${vars}&channel=${channel}`) };
    if (tDetide.checked) jobs.detide = getJSON(`/api/detide?${q}&channel=${channel}`);
    if (tCurrent.checked) jobs.current = getJSON(`/api/current?${q}`);

    const keys = Object.keys(jobs);
    const results = await Promise.all(keys.map((k) => jobs[k]));
    const data = {};
    keys.forEach((k, i) => (data[k] = results[i]));

    draw(sta, data);
    setStatus(`Loaded ${sta}  ·  ${start} → ${end}  (rule: ${data.series.rule}).`);
  } finally {
    loadBtn.disabled = false;
  }
}

// ---- plotting --------------------------------------------------------------
const COL = { pressure: "#4aa3df", tide: "#f0a03c", resid: "#7ee0a4",
              temp: "#e06c9f", speed: "#ffd166", east: "#7bb0ff", north: "#c9a0ff" };

function line(xy, name, color, opts = {}) {
  return Object.assign({
    x: xy.t, y: xy.v, type: "scattergl", mode: "lines", name,
    line: { color, width: opts.width || 1.2, dash: opts.dash || "solid" },
    connectgaps: false,
  }, opts.extra || {});
}

function draw(sta, data) {
  // Build the panel list top→bottom based on what was requested.
  const panels = [];

  const pressureTraces = [line(data.series.pressure, "pressure", COL.pressure)];
  if (data.detide) {
    pressureTraces.push(line(data.detide.tide, "predicted tide", COL.tide, { dash: "dot" }));
  }
  panels.push({ title: "Seafloor pressure [dbar]", traces: pressureTraces });

  if (data.detide) {
    panels.push({ title: "Residual (non-tidal) [dbar]",
                  traces: [line(data.detide.residual, "residual", COL.resid)] });
  }
  if (data.series.temperature) {
    panels.push({ title: "Temperature [°C]",
                  traces: [line(data.series.temperature, "temperature", COL.temp)] });
  }
  if (data.current) {
    if (data.current.available) {
      const c = data.current;
      panels.push({ title: "Current [m/s]", traces: [
        line({ t: c.t, v: c.speed }, "speed", COL.speed, { width: 1.6 }),
        line({ t: c.t, v: c.east }, "east", COL.east, { width: 0.9 }),
        line({ t: c.t, v: c.north }, "north", COL.north, { width: 0.9 }),
      ] });
    } else {
      setStatus(data.current.message || "No current-meter data for this window.");
    }
  }

  // Stack panels as separate y-axes sharing one x-axis.
  const n = panels.length;
  const gap = 0.06;
  const h = (1 - gap * (n - 1)) / n;
  const layout = {
    height: 230 * n + 40,
    margin: { l: 64, r: 20, t: 26, b: 40 },
    paper_bgcolor: "#0f1720", plot_bgcolor: "#0f1720",
    font: { color: "#c7d3de", size: 12 },
    showlegend: true,
    legend: { orientation: "h", y: 1.03, x: 0 },
    annotations: [],
    xaxis: { anchor: `y${n}`, gridcolor: "#22303c", showticklabels: true },
  };
  const traces = [];
  panels.forEach((p, k) => {
    const ykey = k === 0 ? "y" : `y${k + 1}`;
    const axkey = k === 0 ? "yaxis" : `yaxis${k + 1}`;
    const top = 1 - k * (h + gap);
    const bottom = top - h;
    layout[axkey] = { domain: [Math.max(bottom, 0), top], anchor: "x",
                      gridcolor: "#22303c", zeroline: false };
    p.traces.forEach((tr) => { tr.yaxis = ykey; tr.xaxis = "x"; traces.push(tr); });
    layout.annotations.push({
      text: p.title, showarrow: false, xref: "paper", yref: "paper",
      x: 0, xanchor: "left", y: top, yanchor: "bottom",
      font: { size: 12, color: "#9fb0c0" },
    });
  });

  Plotly.react("plot", traces, layout, { responsive: true, displaylogo: false });

  renderTide(sta, data.detide);
}

function renderTide(sta, dt) {
  if (!dt) { tideEl.innerHTML = ""; return; }
  const F = dt.form_factor;
  const ve = (100 * dt.variance_explained).toFixed(2);
  const fmt = (x, n) => (Number.isFinite(x) ? x.toFixed(n) : "—");
  const rows = dt.constituents.map((c) =>
    `<tr><td>${c.name}</td><td>${fmt(c.amp, 4)}</td>` +
    `<td>${fmt(c.phase_deg, 1)}</td><td>${fmt(c.period_h, 2)}</td></tr>`).join("");
  tideEl.innerHTML = `
    <h3>Tidal model — ${sta}</h3>
    <p class="summary">
      Method: <b>${dt.method === "utide" ? "utide (latitude-aware)" : "built-in least-squares"}</b> ·
      form factor F = (K1+O1)/(M2+S2) = <b>${Number.isFinite(F) ? F.toFixed(3) : "—"}</b>
      → <b>${dt.kind}</b> tide · variance explained <b>${ve}%</b>.
    </p>
    <table>
      <thead><tr><th>constituent</th><th>amplitude [dbar]</th><th>phase [°]</th><th>period [h]</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

init().catch((e) => setStatus(e.message, true));
