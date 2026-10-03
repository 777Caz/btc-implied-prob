"""
Research dashboard: one static HTML page (Plotly from a CDN, data embedded), reports/dashboard.html.

  1. Current option-implied densities: SVI fitted to the mark IVs of every expiry in the latest
     Deribit snapshot, Breeden-Litzenberger densities, as a heatmap (expiry x price).
  2. Today's Kalshi vs options: q and the Kalshi bid/ask for every strike of the latest 08:00 UTC
     paper-trading run, and the gap mid - q.
  3. Calibration: Kalshi reliability 1h before (pre-2026 vs 2026), q vs Kalshi mid on the same
     contracts, and the monthly favourite-longshot slope.
  4. Paper-trading log: signals, fills, P&L (no orders are ever sent).
Run:  python -m src.dashboard   (rebuild after the 08:07 paper-trading run for today's panels)
"""
import glob
import html
import json
import logging

import numpy as np
import pandas as pd

import config
from src.models import smile as sm

log = logging.getLogger(__name__)
R = config.ROOT / "reports"
OUT = R / "dashboard.html"
PAPER = config.DATA_PROCESSED / "paper_trades"
BLUE, ORANGE, AQUA, INK2, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#52514e", "#e6e5e1"


def latest_densities():
    files = sorted(glob.glob(str(config.SNAPSHOTS_DIR / "*" / "deribit_*.parquet")))
    chain = pd.read_parquet(files[-1])
    t0 = chain["snapshot_time"].iloc[0]
    spot = float(chain["index_price"].iloc[0])
    grid = np.linspace(spot * 0.6, spot * 1.5, 241)
    cols, labels = [], []
    for exp, g in chain[(chain["expiry"] > t0) & (chain["expiry"] <= t0 + pd.Timedelta(days=95))].groupby("expiry"):
        T = (exp - t0).total_seconds() / (365 * 86400)
        F = float(g["forward_price"].iloc[0])
        g = g[(g["mark_iv"] > 0) & ((g["option_type"] == "call") & (g["strike"] >= F) | (g["option_type"] == "put") & (g["strike"] < F))]
        if len(g) < 6:
            continue
        k = np.log(g["strike"] / F).to_numpy()
        p, _ = sm.fit_svi(k, (g["mark_iv"].to_numpy() / 100) ** 2 * T)
        if p is None:
            continue
        dist = sm.distribution_from_w(p.w, F, T, n=4001, width=10.0)
        dens = np.clip(np.interp(grid, dist.K, dist.density, left=0, right=0), 0, None)
        cols.append(dens / dens.max() if dens.max() > 0 else dens)
        labels.append(f"{exp:%d %b}")
    return {"z": np.array(cols).T.round(4).tolist(), "x": labels, "y": grid.round(0).tolist(), "spot": spot,
            "time": f"{t0:%Y-%m-%d %H:%M} UTC"}


def today_gap():
    f = PAPER / "kalshi_strikes_0800.parquet"
    if not f.exists():
        return None
    s = pd.read_parquet(f)
    d = s[s["date"] == s["date"].max()].sort_values("strike")
    mid = (d["yes_bid"] + d["yes_ask"]) / 2
    return {"date": d["date"].iloc[0], "settle": f"{d['resolution_time'].iloc[0]:%Y-%m-%d %H:%M} UTC",
            "strike": d["strike"].round(2).tolist(), "q": d["q"].round(4).tolist(),
            "bid": d["yes_bid"].round(3).where(d["yes_bid"].notna(), None).tolist(),
            "ask": d["yes_ask"].round(3).where(d["yes_ask"].notna(), None).tolist(),
            "mid": mid.round(4).where(mid.notna(), None).tolist(),
            "gap": ((mid - d["q"]) * 100).round(2).where(mid.notna(), None).tolist(),
            "forward": float(d["forward"].iloc[0])}


def calibration():
    rel = pd.read_csv(R / "pm" / "kalshi_calibration" / "reliability.csv")
    rel = rel[(rel["event_hour"] == "17:00 NY") & (rel["lead"] == "1h")]
    q = pd.read_parquet(R / "pm" / "kalshi_vs_options" / "quotes_with_q.parquet")
    q = q[q["usable"] & q["q"].notna()].assign(mid=lambda x: (x["bid"] + x["ask"]) / 2)
    bins = np.array([0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1])
    same = {}
    for col in ("q", "mid"):
        g = q.groupby(pd.cut(q[col], bins, include_lowest=True), observed=True).agg(x=(col, "mean"), y=("outcome", "mean"))
        same[col] = {"x": g["x"].round(4).tolist(), "y": g["y"].round(4).tolist()}
    b = pd.read_csv(R / "pm" / "kalshi_bias_time" / "bias_monthly.csv")
    b = b[b["measure"] == "b, 8h"]
    return {"rel": {p: {"x": g["mean_mid"].round(4).tolist(), "y": g["observed"].round(4).tolist(),
                        "lo": (g["observed"] - g["ci_lo"]).round(4).tolist(), "hi": (g["ci_hi"] - g["observed"]).round(4).tolist()}
                    for p, g in rel.groupby("period")},
            "same": same, "b": {"month": b["month"].tolist(), "value": b["value"].round(3).tolist(),
                                "ci": (1.96 * b["se"]).round(3).tolist()}}


def paper_log():
    f = PAPER / "kalshi_gap_log.parquet"
    if not f.exists():
        return None, ""
    d = pd.read_parquet(f).sort_values(["date", "T_c", "style", "strike"])
    settled = d[d["outcome"].notna()]
    summ = (settled.groupby(["T_c", "style"]).agg(signals=("ticker", "size"), fill_rate=("filled_through", "mean"),
                                                  pnl_through_c=("pnl_c_through", "mean"), pnl_if_filled_c=("pnl_c_if_filled", "mean"))
            .reset_index() if len(settled) else pd.DataFrame())
    cum = {}
    for (T, style), g in settled.groupby(["T_c", "style"]):
        day = g.groupby("date")["pnl_c_through"].sum().sort_index()
        cum[f"{style}, T = {T:.0f}c"] = {"x": day.index.tolist(), "y": day.cumsum().round(2).tolist()}
    cols = ["date", "T_c", "style", "side", "strike", "q", "yes_bid", "yes_ask", "price", "edge_c", "best_size",
            "outcome", "filled_through", "pnl_c_through"]
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(fmt(r[c]))}</td>" for c in cols) + "</tr>" for _, r in d[cols].tail(60).iterrows())
    table = f"<table><thead><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>{rows}</tbody></table>"
    summary = summ.round(3).to_html(index=False, border=0) if len(summ) else "<p>No settled signals yet.</p>"
    return cum, f"<h3>Settled signals by rule</h3>{summary}<h3>Latest signals</h3>{table}"


def fmt(v):
    if isinstance(v, float):
        return "" if np.isnan(v) else (f"{v:,.2f}" if abs(v) >= 100 else f"{v:.3f}")
    return str(v)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BTC Options vs Kalshi</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root { --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#8a8984; --rule:#e6e5e1; --card:#ffffff; }
@media (prefers-color-scheme: dark) { :root { --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#9a998f; --rule:#383835; --card:#222220; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink); font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:18px; margin:32px 0 6px; } h3 { font-size:15px; margin:18px 0 6px; }
p.sub, .note { color:var(--ink2); margin:0 0 12px; } .note { font-size:13px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(340px, 1fr)); gap:16px; }
.card { background:var(--card); border:1px solid var(--rule); border-radius:10px; padding:12px; min-width:0; }
.plot { width:100%; height:360px; }
.tile { display:flex; gap:24px; flex-wrap:wrap; margin:8px 0 4px; }
.tile div { min-width:150px; } .tile b { display:block; font-size:22px; } .tile span { color:var(--ink2); font-size:13px; }
.tablewrap { overflow-x:auto; }
table { border-collapse:collapse; font-size:12.5px; width:100%; }
th, td { padding:4px 8px; border-bottom:1px solid var(--rule); text-align:right; white-space:nowrap; }
th { color:var(--ink2); font-weight:600; position:sticky; top:0; background:var(--card); }
</style></head><body><main>
<h1>BTC options vs Kalshi</h1>
<p class="sub">Generated __GENERATED__. Option-implied probabilities (Deribit) vs Kalshi's 17:00 New York daily Bitcoin markets.
Research only; the paper-trading log never sends orders.</p>
<div class="tile">
 <div><b>0.99 &plusmn; 0.04</b><span>logit slope of option q (calibrated = 1)</span></div>
 <div><b>1.14 &plusmn; 0.04</b><span>logit slope of the Kalshi mid, 08:00 UTC</span></div>
 <div><b>0.0962 / 0.0962</b><span>Brier: Kalshi mid / option q (518 days)</span></div>
 <div><b>&asymp; 0&cent;</b><span>maker edge per signal with simulated fills, 2026</span></div>
</div>

<h2>1. Current option-implied distributions</h2>
<p class="note" id="dens-note"></p>
<div class="card"><div id="dens" class="plot" style="height:420px"></div></div>

<h2>2. Today: Kalshi vs options at 08:00 UTC</h2>
<p class="note" id="gap-note"></p>
<div class="grid">
 <div class="card"><div id="gapq" class="plot"></div></div>
 <div class="card"><div id="gapbar" class="plot"></div></div>
</div>

<h2>3. Calibration</h2>
<div class="grid">
 <div class="card"><div id="rel" class="plot"></div></div>
 <div class="card"><div id="same" class="plot"></div></div>
</div>
<div class="card" style="margin-top:16px"><div id="bt" class="plot" style="height:320px"></div></div>

<h2>4. Paper-trading log</h2>
<p class="note">Gap rule at 08:00 UTC for T = 2, 3, 5&cent;, taker and maker. Maker fills from Kalshi's public trade history
("through" = a later trade went beyond our price). P&amp;L in cents per contract after fees.</p>
<div class="card"><div id="cum" class="plot" style="height:300px"></div></div>
<div class="card tablewrap" style="margin-top:16px">__PAPER_TABLE__</div>
</main>
<script>
const D = __DATA__;
const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
const ink2 = dark ? '#c3c2b7' : '#52514e', rule = dark ? '#383835' : '#e6e5e1';
const BLUE = dark ? '#3987e5' : '#2a78d6', ORANGE = dark ? '#d95926' : '#eb6834', AQUA = dark ? '#199e70' : '#1baf7a';
const base = (title, xt, yt) => ({ title:{text:title, x:0, font:{size:14}}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{color:ink2, size:12}, margin:{l:56, r:16, t:40, b:48}, xaxis:{title:{text:xt}, gridcolor:rule, zeroline:false},
  yaxis:{title:{text:yt}, gridcolor:rule, zeroline:false}, legend:{orientation:'h', y:-0.22}, hovermode:'closest' });
const cfg = { displaylogo:false, responsive:true };

// 1. densities
document.getElementById('dens-note').textContent = `Deribit snapshot ${D.dens.time}; index ${D.dens.spot.toLocaleString(undefined,{maximumFractionDigits:0})}. ` +
  'SVI fitted to mark IVs per expiry, density scaled to its own maximum.';
Plotly.newPlot('dens', [{ type:'heatmap', x:D.dens.x, y:D.dens.y, z:D.dens.z, colorscale:[[0,dark?'#1a1a19':'#fcfcfb'],[0.25,'#b7d3f6'],[0.6,'#3987e5'],[1,'#0d366b']],
  colorbar:{title:{text:'relative<br>density'}}, hovertemplate:'expiry %{x}<br>BTC %{y:,.0f}<br>density %{z:.2f}<extra></extra>' },
  { x:D.dens.x, y:D.dens.x.map(() => D.dens.spot), mode:'lines', line:{color:ORANGE, width:1.5, dash:'dot'}, name:'index now', hoverinfo:'skip' }],
  Object.assign(base('Option-implied density by expiry', 'expiry', 'BTC price, $'), {showlegend:false}), cfg);

// 2. today's gap
if (D.gap) {
  const g = D.gap;
  document.getElementById('gap-note').textContent = `Kalshi 08:00 UTC snapshot on ${g.date}; settles ${g.settle}; option forward ${g.forward.toLocaleString(undefined,{maximumFractionDigits:0})}.`;
  const quoted = g.strike.filter((k,i) => g.mid[i] !== null);
  const pad = (Math.max(...quoted) - Math.min(...quoted)) * 0.15 + 250;
  const xr = [Math.min(...quoted) - pad, Math.max(...quoted) + pad];
  const lo = g.mid.map((m,i) => (m===null||g.bid[i]===null)?null:m-g.bid[i]), hi = g.mid.map((m,i) => (m===null||g.ask[i]===null)?null:g.ask[i]-m);
  Plotly.newPlot('gapq', [
    { x:g.strike, y:g.q, mode:'lines', name:'option q = P(S > K)', line:{color:BLUE, width:2}, hovertemplate:'K %{x:,.0f}<br>q %{y:.3f}<extra></extra>' },
    { x:g.strike, y:g.mid, mode:'markers', name:'Kalshi mid (bar = bid to ask)', marker:{color:ORANGE, size:7},
      error_y:{type:'data', symmetric:false, array:hi, arrayminus:lo, color:ORANGE, thickness:1.2, width:0}, hovertemplate:'K %{x:,.0f}<br>mid %{y:.3f}<extra></extra>' }],
    Object.assign(base('P(BTC above K at settlement)', 'strike K, $', 'probability'), {xaxis:{title:{text:'strike K, $'}, gridcolor:rule, range:xr}}), cfg);
  Plotly.newPlot('gapbar', [{ type:'bar', x:g.strike, y:g.gap, marker:{color:g.gap.map(v => v===null?rule:(v>0?ORANGE:BLUE))},
    hovertemplate:'K %{x:,.0f}<br>mid - q %{y:.2f}c<extra></extra>' }],
    Object.assign(base('Kalshi mid - option q', 'strike K, $', 'cents'), {showlegend:false, xaxis:{title:{text:'strike K, $'}, gridcolor:rule, range:xr}}), cfg);
} else { document.getElementById('gap-note').textContent = 'No paper-trading run yet (python -m src.paper_trade).'; }

// 3. calibration
const relTraces = Object.entries(D.cal.rel).map(([p, r]) => ({ x:r.x, y:r.y, mode:'lines+markers', name:p,
  line:{color:p==='2026'?ORANGE:BLUE, width:2}, marker:{size:7}, error_y:{type:'data', symmetric:false, array:r.hi, arrayminus:r.lo, thickness:1, width:3},
  hovertemplate:'mid %{x:.2f}<br>settled YES %{y:.2f}<extra>'+p+'</extra>' }));
relTraces.push({ x:[0,1], y:[0,1], mode:'lines', line:{color:ink2, width:1}, showlegend:false, hoverinfo:'skip' });
Plotly.newPlot('rel', relTraces, base('Kalshi reliability, 1h before (17:00 NY)', 'Kalshi mid', 'share settled YES'), cfg);
Plotly.newPlot('same', [
  { x:D.cal.same.q.x, y:D.cal.same.q.y, mode:'lines+markers', name:'option q', line:{color:BLUE, width:2}, marker:{size:7} },
  { x:D.cal.same.mid.x, y:D.cal.same.mid.y, mode:'lines+markers', name:'Kalshi mid', line:{color:ORANGE, width:2}, marker:{size:7} },
  { x:[0,1], y:[0,1], mode:'lines', line:{color:ink2, width:1}, showlegend:false, hoverinfo:'skip' }],
  base('Same contracts at 08:00 UTC: q vs Kalshi', 'forecast probability', 'share settled YES'), cfg);
Plotly.newPlot('bt', [{ x:D.cal.b.month, y:D.cal.b.value, mode:'lines+markers', name:'slope b, 8h before',
  line:{color:BLUE, width:2}, marker:{size:6}, error_y:{type:'data', array:D.cal.b.ci, thickness:1, width:3},
  hovertemplate:'%{x}<br>b %{y:.2f}<extra></extra>' },
  { x:[D.cal.b.month[0], D.cal.b.month[D.cal.b.month.length-1]], y:[1,1], mode:'lines', line:{color:ink2, width:1}, showlegend:false, hoverinfo:'skip' }],
  Object.assign(base('Monthly favourite-longshot slope (1 = calibrated, 95% CI)', 'month', 'logit slope b'), {showlegend:false}), cfg);

// 4. paper trading
const cumTraces = Object.entries(D.cum || {}).map(([k, c], i) => ({ x:c.x, y:c.y, mode:'lines+markers', name:k,
  line:{width:2, color:[BLUE, ORANGE, AQUA, '#eda100', '#e87ba4', '#4a3aa7'][i % 6]} }));
Plotly.newPlot('cum', cumTraces.length ? cumTraces : [{x:[], y:[]}],
  Object.assign(base('Cumulative paper P&L, cents per contract summed over signals (fills "through")', 'settlement date', 'cents'),
    {xaxis:{type:'category', title:{text:'settlement date'}, gridcolor:rule}}), cfg);
</script></body></html>
"""


def main():
    config.setup_logging()
    cum, table = paper_log()
    data = {"dens": latest_densities(), "gap": today_gap(), "cal": calibration(), "cum": cum}
    page = (PAGE.replace("__DATA__", json.dumps(data, default=lambda o: None).replace("NaN", "null"))
            .replace("__PAPER_TABLE__", table or "<p>No paper-trading log yet.</p>")
            .replace("__GENERATED__", f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC"))
    OUT.write_text(page, encoding="utf-8")
    log.info("dashboard -> %s (%.0f KB)", OUT, len(page) / 1024)


if __name__ == "__main__":
    main()
