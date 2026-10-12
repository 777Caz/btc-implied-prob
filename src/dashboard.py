"""
Research dashboard: one static HTML page (Plotly from a CDN, data and figures embedded), reports/dashboard.html.
Tabs: Findings (report figures), Live (1, 2 and 4 below), Kalshi (3 + analysis figures), 1-day forecasts,
30-day options (phases 2-3), Data. Every PNG is embedded as base64, so the file works on its own.

  1. Current option-implied densities: SVI fitted to the mark IVs of every expiry in the latest
     Deribit snapshot, Breeden-Litzenberger densities, as a heatmap (expiry x price).
  2. Today's Kalshi vs options: q and the Kalshi bid/ask for every strike of the latest 08:00 UTC
     paper-trading run, and the gap mid - q.
  3. Calibration: Kalshi reliability 1h before (pre-2026 vs 2026), q vs Kalshi mid on the same
     contracts, and the monthly favourite-longshot slope.
  4. Paper-trading log: signals, fills, P&L (no orders are ever sent).
Run:  python -m src.dashboard   (rebuild after the 08:07 paper-trading run for today's panels)
PDF (every tab in order, A4):  open dashboard.html#print and print, or headless Edge:
  msedge --headless=new --no-pdf-header-footer --virtual-time-budget=30000 --user-data-dir=<empty temp dir>
         --print-to-pdf=reports/dashboard.pdf file:///<project>/reports/dashboard.html#print
  (the separate profile stops an already-running Edge from taking the job and writing nothing)
"""
import base64
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


# ── Figure gallery: every chart the project produced, embedded so the page is one file ───────
FIGURES = {   # tab: [(path under reports/, title, caption, wide)]
    "findings": [
        ("figures/report/fig1_option_to_probability.png", "From option trades to a 1-day probability",
         "One day: Deribit trades and the fitted SVI smile at 08:00 UTC, then q = P(S > K) at 17:00 NY next to Kalshi's mids.", True),
        ("figures/report/fig4_kalshi_vs_options.png", "Kalshi is flatter than the options",
         "Kalshi mid minus option q by price bucket, and reliability of both on the same 8,574 contracts: q is calibrated, the mid too flat.", True),
        ("figures/report/fig3_kalshi_calibration.png", "Kalshi calibration and the price-floor check",
         "Reliability 1h before settlement, and the favourite-longshot slope b with mids trimmed or selected by distance from the money.", True),
        ("figures/report/fig5_encompassing_staleness.png", "Which price carries the information?",
         "Encompassing weights of the Kalshi mid and option q, with the usual 8-hour smile and with smiles from only the last 2 hours or 1 hour.", True),
        ("figures/report/fig6_trade_tests.png", "Can the gap be traded?",
         "Taker and maker P&L with 95% CIs. The maker edge disappears once fills are simulated from Kalshi's trade history.", True),
        ("figures/report/fig7_markouts.png", "What resting orders earn",
         "Markouts after a fill (maker's view) and P&L to settlement by purchase price: favourites win, longshots lose.", True),
        ("figures/report/fig8_bias_over_time.png", "Bias over time and market structure",
         "Monthly slope b, quoted spread, taker longshot buying and volume, with the 2026 holdout and the Wintermute date.", True),
        ("figures/report/fig2_short_horizon_validation.png", "The 1-day option forecasts are calibrated",
         "PIT histograms on 1,952 days: flat = calibrated; the small central hump = slightly too wide (a small variance premium).", True),
    ],
    "kalshi": [
        ("pm/kalshi_calibration/reliability.png", "Reliability by quote time and period",
         "Share settling YES against the Kalshi mid, 24h / 8h / 1h before and at 08:00 UTC, pre-2026 vs 2026.", True),
        ("pm/kalshi_vs_options/kalshi_vs_options.png", "Kalshi mid vs option q, every contract",
         "Scatter of mid against q at 08:00 UTC and the mean gap by bucket with day-clustered CIs.", True),
        ("pm/kalshi_gap_trade/cumulative_pnl.png", "Gap rule: cumulative P&L",
         "Taker and (optimistic, fill-assumed) maker P&L at T = 2, 3, 5c, 100 contracts per trade; dashed line = 2026 holdout.", True),
        ("pm/kalshi_bias_time/bias_vs_activity.png", "Bias vs activity, spreads and taker flow (full detail)",
         "Monthly slopes at three quote times, the gap vs options, spreads, taker flow by side, volume and open interest.", True),
    ],
    "oneday": [
        ("intraday/intraday_profile.png", "Intraday variance profile",
         "Share of a day's variance per minute from squared 1-minute Binance returns, weekday vs weekend: the basis of variance time.", True),
        ("intraday/intraday_by_year.png", "The profile by year",
         "The intraday shape is stable across years; the weekend level falls from about 0.73 of a weekday in 2021.", True),
        ("short_horizon/event_excess.png", "Macro-event days",
         "Excess variance around CPI, NFP and FOMC releases, from earlier events only: most of it arrives within minutes.", False),
        ("short_horizon/pit_histograms.png", "Validation of every variant",
         "PIT histograms for clock vs variance time, with and without events, alpha 0.5 vs fitted.", False),
    ],
    "thirty": [
        ("phase2/vol_levels.png", "DVOL vs realised volatility",
         "DVOL averaged about 60% against 51% realised over the next 30 days: a variance risk premium.", True),
        ("phase3/density_heatmap.png", "Risk-neutral density by days ahead",
         "From the live snapshot of 30 Sep 2026: smile densities per expiry, interpolated in total variance, with the 5th, 50th and 95th percentiles.", True),
        ("phase3/smile_fits.png", "SVI smile fits per expiry", "Implied vols of out-of-the-money options in the 30 Sep 2026 snapshot with the fitted SVI curve and fit error per expiry.", False),
        ("phase3/expiry_densities.png", "Densities by expiry", "Breeden-Litzenberger densities per expiry (30 Sep 2026) against a DVOL lognormal: the smile puts more mass in the centre and the tails.", False),
        ("phase3/smile_vs_dvol_cone.png", "Smile vs DVOL 30-day cone", "Percentile bands from the full smile against a DVOL lognormal, from 30 Sep 2026: close at the 5th/95th, the smile is narrower in the middle.", False),
        ("phase2/forward_cone.png", "Forward cone", "DVOL-based 30-day percentile cone from today.", False),
        ("phase2/historical_cones.png", "Historical 30-day cones", "Non-overlapping 30-day cones since 2021 with the realised path: DVOL 8 of 67 outside 5-95% (expected 6.7), trailing realised vol 13 of 67.", True),
        ("phase3/pit_histograms.png", "Calibration of the 30-day forecasts (smile)", "PIT histograms: the smile's are flat (variance ratio 1.02).", False),
        ("phase2/pit_histograms.png", "Calibration of the 30-day forecasts (DVOL, realised vol)", "DVOL is too wide in the middle; realised vol too narrow.", False),
        ("phase3/reliability.png", "Reliability of strike probabilities (smile)", "Predicted vs observed frequency of BTC ending above each strike.", False),
        ("phase2/reliability.png", "Reliability of strike probabilities (DVOL)", "The same for the DVOL lognormal and realised-vol models.", False),
        ("phase3/tail_breaches.png", "Tail misses by model",
         "Share of 30-day windows finishing below the 5th / above the 95th percentile, by model, with Newey-West 95% CIs: every model misses a little on the upside, none significantly.", True),
    ],
    "data": [
        ("figures/00_data_coverage.png", "Data coverage", "Every dataset's time span and gaps.", True),
        ("figures/02_btc_price.png", "BTC price", "Bitcoin price history used throughout.", False),
        ("figures/03_btc_vs_dvol.png", "BTC vs DVOL", "Price against Deribit's 30-day implied volatility index.", False),
        ("figures/04_option_trades.png", "Option trades", "Deribit option trades per month, 2021-2026.", False),
        ("figures/05_live_snapshot.png", "A live snapshot", "One synchronised snapshot of the Deribit chain and the prediction markets.", False),
    ],
}


def gallery(tab: str) -> str:
    out = []
    for path, title, caption, wide in FIGURES[tab]:
        f = R / path
        if not f.exists():
            log.warning("dashboard: missing %s", f)
            continue
        src = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
        out.append(f'<figure class="{"wide" if wide else ""}"><img loading="lazy" src="{src}" alt="{html.escape(title)}">'
                   f'<figcaption><b>{html.escape(title)}{"" if title.endswith("?") else "."}</b> {html.escape(caption)} <span class="src">({html.escape(path)})</span></figcaption></figure>')
    return f'<div class="gallery">{"".join(out)}</div>'


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
.tabs { display:flex; flex-wrap:wrap; gap:6px; margin:16px 0 8px; border-bottom:1px solid var(--rule); }
.tabs button { font:inherit; font-size:14px; padding:8px 14px; border:1px solid transparent; border-bottom:none; background:none;
  color:var(--ink2); cursor:pointer; border-radius:8px 8px 0 0; }
.tabs button[aria-selected="true"] { color:var(--ink); background:var(--card); border-color:var(--rule); font-weight:600; margin-bottom:-1px; }
.tab { display:none; } .tab.on { display:block; }
ol.answer { margin:12px 0 4px; padding-left:22px; } ol.answer li { margin:4px 0; }
.gallery { display:grid; grid-template-columns:repeat(auto-fit, minmax(460px, 1fr)); gap:16px; margin-top:16px; }
@media (max-width:520px) { .gallery { grid-template-columns:1fr; } }
figure { margin:0; background:var(--card); border:1px solid var(--rule); border-radius:10px; padding:12px; min-width:0; }
figure.wide { grid-column:1 / -1; }
figure img { width:100%; height:auto; display:block; border-radius:4px; cursor:zoom-in; background:#fcfcfb; }
figcaption { font-size:13px; color:var(--ink2); margin-top:8px; } figcaption b { color:var(--ink); }

.tabtitle { display:none; }
body.printall .tab { display:block; } body.printall .tabs { display:none; } body.printall .tabtitle { display:block; }
@media print {
  @page { size: A4; margin: 12mm; }
  body { background:#fff; font-size:12px; } main { max-width:none; padding:0; }
  .tab { display:block !important; } .tabs, #lightbox { display:none !important; } .tabtitle { display:block; }
  .tab + .tab { break-before: page; }
  figure, .card, .tile, ol.answer { break-inside: avoid; }
  .gallery { grid-template-columns: 1fr; } .grid { grid-template-columns: 1fr 1fr; }
  figure img { cursor:default; width:auto; max-width:100%; max-height:235mm; margin:0 auto; } .tablewrap { overflow:visible; }
}
#lightbox { position:fixed; inset:0; background:rgba(0,0,0,.85); display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:16px; z-index:10; cursor:zoom-out; } #lightbox[hidden] { display:none; }
#lightbox img { max-width:100%; max-height:88vh; background:#fcfcfb; border-radius:4px; } #lightbox p { color:#fff; font-size:14px; max-width:900px; }
</style></head><body><main>
<h1>BTC options vs Kalshi</h1>
<p class="sub">Generated __GENERATED__. Are prediction markets efficient once you account for the risk premium in options?
Option-implied probabilities (Deribit) vs Kalshi's 17:00 New York daily Bitcoin markets. Research only; the paper-trading log never sends orders.</p>
<nav class="tabs" role="tablist">
 <button data-tab="findings">Findings</button><button data-tab="live">Live</button><button data-tab="kalshi">Kalshi</button>
 <button data-tab="oneday">1-day forecasts</button><button data-tab="thirty">30-day options</button><button data-tab="data">Data</button>
</nav>

<section id="tab-findings" class="tab">
<h2 class="tabtitle">Findings</h2>
<div class="tile">
 <div><b>0.99 &plusmn; 0.04</b><span>logit slope of option q (calibrated = 1)</span></div>
 <div><b>1.14 &plusmn; 0.04</b><span>logit slope of the Kalshi mid, 08:00 UTC</span></div>
 <div><b>0.0962 / 0.0962</b><span>Brier: Kalshi mid / option q (518 days)</span></div>
 <div><b>&asymp; 0&cent;</b><span>maker edge per signal with simulated fills, 2026</span></div>
</div>
<ol class="answer">
 <li><b>The options get it right.</b> The 1-day option probability q is calibrated on Kalshi's strikes.</li>
 <li><b>Kalshi has a favourite-longshot bias in 2026</b> (slope 1.18&ndash;1.36). It survives the 1&cent; price-floor check; before 2026 it was mostly that floor.</li>
 <li><b>Kalshi is flatter than the options by 2&ndash;4&cent;, but just as informative</b>: equal Brier scores, similar information with fresh option data.</li>
 <li><b>The gap can't be traded.</b> Takers lose to fees and the spread; maker profits vanish once fills are simulated.</li>
 <li><b>Kalshi is efficient up to its costs.</b> The bias coincides with more takers buying longshots in 2026 (suggestive, not significant).</li>
</ol>
__GALLERY_findings__
</section>

<section id="tab-live" class="tab">
<h2 class="tabtitle">Live: options and Kalshi today, paper trading</h2>
<h2>Current option-implied distributions</h2>
<p class="note" id="dens-note"></p>
<div class="card"><div id="dens" class="plot" style="height:420px"></div></div>
<h2>Today: Kalshi vs options at 08:00 UTC</h2>
<p class="note" id="gap-note"></p>
<div class="grid">
 <div class="card"><div id="gapq" class="plot"></div></div>
 <div class="card"><div id="gapbar" class="plot"></div></div>
</div>
<h2>Paper-trading log</h2>
<p class="note">Gap rule at 08:00 UTC for T = 2, 3, 5&cent;, taker and maker. Maker fills from Kalshi's public trade history
("through" = a later trade went beyond our price). P&amp;L in cents per contract after fees.</p>
<div class="card"><div id="cum" class="plot" style="height:300px"></div></div>
<div class="card tablewrap" style="margin-top:16px">__PAPER_TABLE__</div>
</section>

<section id="tab-kalshi" class="tab">
<h2 class="tabtitle">Kalshi analysis</h2>
<h2>Calibration (interactive)</h2>
<div class="grid">
 <div class="card"><div id="rel" class="plot"></div></div>
 <div class="card"><div id="same" class="plot"></div></div>
</div>
<div class="card" style="margin-top:16px"><div id="bt" class="plot" style="height:320px"></div></div>
__GALLERY_kalshi__
</section>

<section id="tab-oneday" class="tab">
<h2 class="tabtitle">1-day option forecasts</h2>
<p class="note">Scaling the 08:00 UTC front-expiry smile to noon and 17:00 New York with variance time and macro-event days; validated on 1,869 days.</p>
__GALLERY_oneday__
</section>
<section id="tab-thirty" class="tab">
<h2 class="tabtitle">30-day option forecasts (phases 2-3)</h2>
<p class="note">Phases 2&ndash;3: 30-day forecasts from DVOL and from the full option smile, scored against the Deribit delivery price.</p>
__GALLERY_thirty__
</section>
<section id="tab-data" class="tab">
<h2 class="tabtitle">Data</h2>
<p class="note">What was collected, and how complete it is.</p>
__GALLERY_data__
</section>
</main>
<div id="lightbox" hidden><img alt=""><p></p></div>
<script>
const D = __DATA__;
const printAll = location.hash === '#print';
if (printAll) document.body.classList.add('printall');
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
// tabs (remembered in the URL hash) and the image lightbox
const tabs = [...document.querySelectorAll('.tabs button')];
function show(name) {
  if (!document.getElementById('tab-' + name)) name = 'findings';
  tabs.forEach(b => b.setAttribute('aria-selected', b.dataset.tab === name));
  document.querySelectorAll('.tab').forEach(s => s.classList.toggle('on', s.id === 'tab-' + name));
  document.querySelectorAll('#tab-' + name + ' .plot').forEach(p => { try { Plotly.Plots.resize(p); } catch (e) {} });
  history.replaceState(null, '', '#' + name);
}
tabs.forEach(b => b.addEventListener('click', () => show(b.dataset.tab)));
if (!printAll) show(location.hash.slice(1) || 'findings');
const resizeAll = () => document.querySelectorAll('.plot').forEach(p => { try { Plotly.Plots.resize(p); } catch (e) {} });
window.addEventListener('beforeprint', () => { document.body.classList.add('printall'); resizeAll(); });
window.addEventListener('afterprint', () => { if (!printAll) { document.body.classList.remove('printall'); resizeAll(); } });
const lb = document.getElementById('lightbox');
document.querySelectorAll('figure img').forEach(img => img.addEventListener('click', () => {
  lb.querySelector('img').src = img.src; lb.querySelector('p').innerHTML = img.closest('figure').querySelector('figcaption').innerHTML; lb.hidden = false; }));
lb.addEventListener('click', () => { lb.hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') lb.hidden = true; });
</script></body></html>
"""


def main():
    config.setup_logging()
    cum, table = paper_log()
    data = {"dens": latest_densities(), "gap": today_gap(), "cal": calibration(), "cum": cum}
    page = (PAGE.replace("__DATA__", json.dumps(data, default=lambda o: None).replace("NaN", "null"))
            .replace("__PAPER_TABLE__", table or "<p>No paper-trading log yet.</p>")
            .replace("__GENERATED__", f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC"))
    for tab in FIGURES:
        page = page.replace(f"__GALLERY_{tab}__", gallery(tab))
    OUT.write_text(page, encoding="utf-8")
    log.info("dashboard -> %s (%.0f KB)", OUT, len(page) / 1024)


if __name__ == "__main__":
    main()
