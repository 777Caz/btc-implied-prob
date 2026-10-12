# Operations: data collection, layout and setup

Everything here is about running and maintaining the pipeline; the research is in [reports/REPORT.md](../reports/REPORT.md).

## Data sources (all free, public, no API key)

| Source | What we take | Docs |
|---|---|---|
| Deribit | BTC index price, DVOL, historical option trades, live options chain | https://docs.deribit.com |
| Polymarket | BTC price markets: questions, thresholds, prices | https://docs.polymarket.com |
| Kalshi | BTC price markets: thresholds, prices | https://docs.kalshi.com |

## Folder layout

```
btc-implied-prob/
├── config.py            # dates, currency, paths, API URLs, logging setup: edit settings here
├── requirements.txt
├── src/
│   ├── api.py             # shared HTTP GET with retries/pacing + Deribit JSON-RPC wrapper
│   ├── storage.py         # save/load parquet helpers
│   ├── deribit_prices.py  # step 2: BTC index price history (daily, hourly, 08:00 UTC)
│   ├── deribit_dvol.py    # step 3: DVOL implied-vol index history
│   ├── deribit_options.py # step 4: historical option trades
│   ├── snapshot.py        # step 5: live snapshot of Deribit chain + Polymarket/Kalshi
│   ├── resolutions.py     # daily: settlements, market outcomes, Binance 12:00 ET price
│   ├── checks.py          # step 6: data-quality checks used by the notebook
│   ├── visuals.py         # progress charts → reports/figures/ (python -m src.visuals)
│   ├── models/            # smile.py (SVI, Breeden-Litzenberger), dvol_lognormal.py, realized_vol.py
│   ├── forwards.py, clean_trades.py, phase2.py, phase3*.py   # 30-day forecasts (phases 2-3)
│   ├── binance_bulk.py, intraday_vol.py, short_horizon.py    # 1-day forecasts at 12:00/17:00 NY
│   ├── pm_backfill.py, pm_kalshi_*.py                        # prediction-market history and tests
│   ├── paper_trade.py     # daily Kalshi gap-rule paper-trading log (no orders)
│   ├── report_figures.py  # the figures of reports/REPORT.md
│   ├── report_pdf.py      # reports/REPORT.md -> reports/REPORT.pdf
│   └── dashboard.py       # reports/dashboard.html (static Plotly page)
├── docs/                # this file, and the plan for the pricing-kernel step
├── deploy/              # register_tasks.ps1 + run_task.py (Windows), crontab.txt (Mac/Linux)
├── reference/us_macro_events.csv   # CPI / NFP / FOMC release times (bls.gov, federalreserve.gov)
├── data/
│   ├── raw/             # data exactly as fetched (parquet)
│   │   ├── option_trades/  # Deribit option trades, one file per month (YYYY-MM.parquet)
│   │   ├── snapshots/   # one folder per day, two zstd parquet files per snapshot run
│   │   └── resolutions/ # settlement prices + outcomes for everything the snapshots quoted
│   └── processed/       # cleaned / merged data built from raw/
├── notebooks/
│   └── 01_data_checks.ipynb  # step 6: coverage, timezones, duplicates, bad values, BTC vs DVOL
├── reports/             # REPORT.md/.pdf, dashboard, and one results folder per analysis (RESULTS.md + CSVs)
│   └── figures/         # data charts; figures/report/ holds the figures of REPORT.md
└── logs/pipeline.log    # log output from every script
```

## Conventions

- **Timestamps are always UTC**, stored as timezone-aware pandas datetimes (dtype `datetime64[..., UTC]`).
- **Storage is parquet**. It keeps dtypes and is small and fast. Read it with `pd.read_parquet`.
- **raw/ is never edited by hand.** Anything derived goes in processed/ so it can be rebuilt.
- Deribit options expire at **08:00 UTC**, so that is the reference time for "outcome" prices.

## Live snapshots

`python -m src.snapshot` saves the full Deribit BTC options chain plus Polymarket and Kalshi
BTC price markets, all taken within ~2 seconds, to `data/raw/snapshots/YYYY-MM-DD/`.
Free historical data can't give synchronised quotes across these venues, so they have to be
recorded going forward. Each snapshot is ~100 KB (~15 MB/day at one every 10 minutes).

`python -m src.resolutions` (daily) records what actually happened for everything the snapshots
quoted, in `data/raw/resolutions/`:

| File | Key | Joins to snapshot rows on |
|---|---|---|
| `deribit_delivery.parquet` | `expiry` (08:00 UTC) | Deribit snapshot `expiry` |
| `predmarkets.parquet` | (`venue`, `market_id`) | prediction-market snapshot (`venue`, `market_id`) |
| `binance_btcusdt_1m.parquet` | `candle_open` (UTC) | Polymarket snapshot `resolution_time` |

`market_id` is Polymarket's Gamma market id or Kalshi's ticker: both are permanent ids, unlike
question text. `outcome` is 1 if YES won, 0 if NO won, NaN if not final yet. The job only
fetches what is missing or not yet final, so running it late or twice is harmless.

### Scheduling on Windows (Task Scheduler)

`deploy/register_tasks.ps1` registers three tasks under `\btc-implied-prob\`, run as you whether
or not you are logged on (S4U, no stored password), with times pinned to UTC:

| Task | When | Runs |
|---|---|---|
| `snapshot` | every 10 minutes | `python -m src.snapshot` |
| `resolutions` | daily 00:30 UTC | `python -m src.resolutions` (also settles the paper-trading log) |
| `paper_trade` | daily 08:07 UTC | `python -m src.paper_trade` (Kalshi gap-rule signals, no orders) |

Register (or re-register) from the project root in an **admin** PowerShell:
`powershell -ExecutionPolicy Bypass -File deploy\register_tasks.ps1`. Each task runs through
`deploy/run_task.py` (pythonw, output to `logs/task_<module>.log`). Set the PC's sleep to "Never"
on mains power, or snapshots will have gaps; `src.checks.snapshot_gaps()` and the daily
resolutions log report any gap of 30 minutes or more.

### Scheduling on a Mac (cron)

The cron jobs are in [deploy/crontab.txt](../deploy/crontab.txt) (install with `crontab deploy/crontab.txt`,
check with `crontab -l`, remove with `crontab -r`). Edit the path inside first if the project lives
elsewhere. Times are local time. cron doesn't run while the Mac sleeps, so expect gaps. Output goes
to `logs/cron_*.log`.

Run only **one** collector at a time (Mac, PC or VPS). Two would write two separate sets of
snapshots that you'd have to merge.

### Moving to a small Linux VPS

Any always-on box works (e.g. a $4–6/month 1 vCPU / 1 GB VPS; Ubuntu 24.04 assumed). Data
grows ~15 MB/day, so the smallest disk is plenty for years.

1. **Set up the server** (as your user, not root):
   ```bash
   sudo apt update && sudo apt install -y python3-venv git rsync
   sudo timedatectl set-timezone UTC          # keep the server in UTC; avoids DST surprises
   git clone <your repo url> ~/btc-implied-prob   # or: rsync the project up from the Mac (step 4)
   cd ~/btc-implied-prob && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m src.snapshot            # test once; check data/raw/snapshots/
   ```
2. **Install cron** (`crontab -e`), with the path changed and the daily job in UTC:
   ```
   */10 * * * * cd $HOME/btc-implied-prob && .venv/bin/python -m src.snapshot >> logs/cron_snapshot.log 2>&1
   30 22 * * *  cd $HOME/btc-implied-prob && .venv/bin/python -m src.resolutions >> logs/cron_resolutions.log 2>&1
   ```
   Then remove the Mac's jobs (`crontab -r` on the Mac) so the two don't both write snapshots.
3. **Check it's running**: `tail logs/cron_snapshot.log` and `ls data/raw/snapshots/$(date -u +%F)/`.
4. **Copy data back to the Mac** whenever you want to analyse (only new files are transferred):
   ```bash
   rsync -avz user@your-vps:btc-implied-prob/data/raw/snapshots/   data/raw/snapshots/
   rsync -avz user@your-vps:btc-implied-prob/data/raw/resolutions/ data/raw/resolutions/
   ```
   Snapshot files never collide (one file per timestamp), so Mac-era and VPS-era snapshots sit
   side by side. For resolutions, let the VPS copy overwrite the Mac's: the job rebuilds
   everything from the snapshots it can see, so run it once on the VPS after copying the Mac's
   snapshots up (`rsync -avz data/raw/snapshots/ user@your-vps:btc-implied-prob/data/raw/snapshots/`).

Notes: the Binance market-data host (`data-api.binance.vision`) is used because `api.binance.com`
is blocked from some regions (notably US IPs); pick a VPS region where both work, and test with
`curl "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1"`.

The three venues settle on **different reference prices and times**:

| Venue | Settles on | Time |
|---|---|---|
| Deribit | Deribit BTC index, 30-min TWAP | 08:00 UTC |
| Polymarket | Binance BTC/USDT 1-minute close | 12:00 ET (16:00 UTC in summer, 17:00 UTC in winter) |
| Kalshi | CF Benchmarks BRTI, 60-second average | 12:00 or 17:00 ET |

## Known data limitations

- **No forward price in the trade data.** Historical option trades carry `index_price` (spot)
  but not the forward/futures price for each expiry. `src/forwards.py` backs it out from put-call
  parity on calls and puts traded close together; it is checked against Deribit's own forwards in
  the live snapshots and against futures in `reports/phase3/robustness/`.
- **Option prices are in BTC.** Deribit BTC options are inverse (quoted and settled in BTC);
  `price_usd = price × index_price`.
- **Trade history comes from `history.deribit.com`**, which serves the full public archive but is
  not in Deribit's current API docs. `www.deribit.com` only keeps the last 24 hours of trades.

## Setup

The code is in git; the **data is not** (`data/` is about 2.3 GB, mostly option trades, whose full
download takes about 47 hours).

1. Create the Python environment (Python 3.11+):

   **Windows** (PowerShell or cmd):
   ```bat
   py -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
   **Mac / Linux**:
   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```
2. Check it works: `python -m src.snapshot` (with the venv's python) should save two files in
   `data/raw/snapshots/<today>/`.
3. Rebuild the history from the APIs: `src.deribit_prices`, `src.deribit_dvol`,
   `src.deribit_options 2021-01-01 <next month>` (the slow one), `src.binance_bulk`,
   `src.pm_backfill`, `src.pm_kalshi_trades` and `src.resolutions`. Past live snapshots can't be
   rebuilt: they exist only where they were recorded.

Every script runs as a module from the project root, e.g. `python -m src.phase2`. Paths are built
from the project folder (`config.py`), so the project can live anywhere.
