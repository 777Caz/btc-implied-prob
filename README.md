# BTC Deribit Options vs Prediction Markets

How well do BTC options-implied probabilities predict what actually happens, and how do they
compare with prediction-market prices (Polymarket, Kalshi) on the same events?

Deribit options prices contain the market's view of where BTC will be at each expiry. This project
pulls those prices, turns them into probabilities (e.g. "P(BTC > $100k on Friday 08:00 UTC)"), and
checks them against realised outcomes. Later it compares them with prediction-market prices
(Polymarket, Kalshi) on the same events, to look for mispricing or arbitrage.

**Phase 1 (data collection)** is done. **Phase 2 (DVOL-based lognormal forecasts and calibration
tests vs a realised-vol baseline)** is in [reports/phase2/SUMMARY.md](reports/phase2/SUMMARY.md).
Code: `src/models/`, `src/calibration.py`, `src/phase2.py` (`python -m src.phase2`).
**Phase 3 (risk-neutral distributions from the full option smile: parity forwards, arbitrage-penalised
SVI, Breeden-Litzenberger densities, total-variance interpolation)** is in
[reports/phase3/SUMMARY.md](reports/phase3/SUMMARY.md). Code: `src/models/smile.py`, `src/forwards.py`,
`src/clean_trades.py`, `src/phase3.py`, `src/phase3_hist.py`.

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
│   └── visuals.py         # progress charts → reports/figures/ (python -m src.visuals)
├── deploy/crontab.txt   # the cron jobs (snapshot every 10 min, resolutions daily)
├── data/
│   ├── raw/             # data exactly as fetched (parquet)
│   │   ├── option_trades/  # Deribit option trades, one file per month (YYYY-MM.parquet)
│   │   ├── snapshots/   # one folder per day, two zstd parquet files per snapshot run
│   │   └── resolutions/ # settlement prices + outcomes for everything the snapshots quoted
│   └── processed/       # cleaned / merged data built from raw/
├── notebooks/
│   └── 01_data_checks.ipynb  # step 6: coverage, timezones, duplicates, bad values, BTC vs DVOL
├── reports/figures/     # PNG charts of each step's data
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

Windows has no cron; use Task Scheduler. From a **cmd** prompt (replace the path with the project's):

```bat
schtasks /Create /TN "btc-snapshot" /SC MINUTE /MO 10 /TR "cmd /c cd /d C:\path\to\btc-implied-prob && .venv\Scripts\python -m src.snapshot >> logs\cron_snapshot.log 2>&1"
schtasks /Create /TN "btc-resolutions" /SC DAILY /ST 23:30 /TR "cmd /c cd /d C:\path\to\btc-implied-prob && .venv\Scripts\python -m src.resolutions >> logs\cron_resolutions.log 2>&1"
```

Check with `schtasks /Query /TN btc-snapshot`, remove with `schtasks /Delete /TN btc-snapshot /F`.
Like cron on a laptop, tasks don't run while the PC sleeps. In the Task Scheduler app you can tick
"Wake the computer to run this task" and "Run whether user is logged on or not" for fewer gaps.

### Scheduling on a Mac (cron)

The cron jobs are in [deploy/crontab.txt](deploy/crontab.txt) (install with `crontab deploy/crontab.txt`,
check with `crontab -l`, remove with `crontab -r`). Edit the path inside first if the project lives
elsewhere. Times are local time. cron doesn't run while the Mac sleeps, so expect gaps. Output goes
to `logs/cron_*.log`. (History: this ran on the original Mac from 2026-09-30 until it was switched
off on 2026-10-02, when collection moved to a Windows PC.)

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
  but not the forward/futures price for each expiry. Implied probabilities have to be computed
  against the forward, so a later phase will need to **back it out from put-call parity**
  (C − P = e^(−rT)·(F − K) across strikes of the same expiry), using calls and puts traded close
  together in time. The live snapshots (step 5) record Deribit's `underlying_price` directly,
  which can be used to check that estimate.
- **Option prices are in BTC.** Deribit BTC options are inverse (quoted and settled in BTC);
  `price_usd = price × index_price`.
- **Trade history comes from `history.deribit.com`**, which serves the full public archive but is
  not in Deribit's current API docs. `www.deribit.com` only keeps the last 24 hours of trades.

## Setup

The code is in git; the **data is not** (`data/` is ~1.1 GB, mostly option trades that took ~47 h
to download). It travels separately as a zip, `btc-implied-prob-data.zip`, that unzips to `data/`.

1. Clone the repo, then unzip the data zip **into the project folder** so `data/` sits next to `src/`.
2. Create the Python environment (Python 3.11+):

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
3. Check it works: `python -m src.snapshot` (with the venv's python) should save two files in
   `data/raw/snapshots/<today>/`.

Every script runs as a module from the project root, e.g. `python -m src.phase2`. Paths are built
from the project folder (`config.py`), so the project can live anywhere.

Without the data zip, everything can be rebuilt from the APIs: `src.deribit_prices`,
`src.deribit_dvol`, `src.deribit_options 2021-01-01 <next month>` (the slow one), and
`src.resolutions`. Past live snapshots can't be rebuilt; they only exist in the zip.
