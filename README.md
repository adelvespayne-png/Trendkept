# Trendrail

A small, dependency-free toolkit for one thing: trading a **confirmed uptrend
with disciplined risk**. Trendrail turns a mechanical trend-following ruleset into
code you can *write down, backtest, and paper-trade* before a single pound is at
risk.

Pure Python standard library. No `pip install`. Runs on Python 3.9+.

---

## The rules (write them down — then never improvise)

These are the exact rules the code enforces. The edge is not any single rule; it
is following all of them, every time.

### 1. Trade only a confirmed uptrend
Take a liquid asset and a **daily** chart. Enter only when **all** are true:
- Price (close) is above **both** the 50-day and 200-day simple moving averages.
- The 50-day average is above the 200-day average (the trend is aligned).
- The structure is making **higher highs and higher lows**.

If the trend isn't confirmed, you stay out. No exceptions.

### 2. Enter without chasing
Once the trend is confirmed, enter on **either**:
- a **small pullback** toward the 50-day average that closes back up, or
- a **breakout** above a recent (20-day) high.

Never chase a move that has already run far: Trendrail refuses any entry more than
~12% extended above the 50-day average.

### 3. Set the stop the moment you enter
The stop-loss sits **just below the most recent swing low**. This is the price
at which you admit you were wrong and exit. It is decided *before* the trade, not
in the heat of a drawdown.

### 4. Size by risk, not by gut
Size the position so that **if the stop is hit you lose no more than 1–2% of your
account**. On a £1,000 account that is £10–£20 per trade.

```
risk per share  = entry price − stop price
shares          = (account × risk%) ÷ risk per share
```

### 5. Hold the trend; trail the stop
While the trend continues, **trail the stop upward** under each new higher swing
low. The stop only ever rises — you lock in gains, you never loosen risk.

### 6. Exit when the trend breaks
Exit completely when **either**:
- price **closes below the 50-day average**, or
- the structure makes a **lower low**.
(Or, of course, when the trailing stop is hit.)

### The whole edge, in one sentence
**Cut losers fast and small, let winners run big.** You can be wrong well over
half the time and still come out ahead, because each win dwarfs each loss. The
scorecard that matters is the **R-multiple** — profit measured in units of the
risk you set at entry — not your win rate.

> ⚠️ This is an educational backtesting/paper-trading tool, **not financial
> advice**. Backtests use idealized fills and lookback-free (causal) signals,
> but real markets gap, slip, and surprise. Paper-trade until you can follow the
> rules without flinching before risking real money.

---

## Install / run

Nothing to install. Clone and run:

```bash
# The dashboard: the whole toolkit in a browser (local only, no dependencies)
python -m trendrail.web
# then open http://127.0.0.1:8181
```

Or from the command line:

```bash
# Backtest the rules over a price history
python -m trendrail.cli backtest examples/sample_uptrend.csv --account 1000 --risk 0.02 -v

# The same on real AAPL data (bundled)
python -m trendrail.cli backtest examples/aapl_2015_2017.csv --account 1000 --risk 0.02 -v

# Ask the rules what to do *today* (the paper-trading helper)
python -m trendrail.cli scan examples/aapl_2015_2017.csv --account 1000 --risk 0.02
```

### Real data, straight from a ticker
With a network connection you can skip the CSV entirely. Free, no API key:

```bash
# Stooq (default) or Yahoo — auto tries both
python -m trendrail.cli backtest --symbol AAPL --account 1000 --risk 0.02 -v
python -m trendrail.cli scan     --symbol MSFT --provider yahoo

# Save history to a CSV for offline/repeatable runs
python -m trendrail.cli fetch AAPL --out data/aapl.csv
python -m trendrail.cli backtest data/aapl.csv --account 1000
```

### Your own data
Provide a CSV with a header row. Column names are matched by meaning, so files
from Yahoo (`Date,Open,High,Low,Close,Adj Close,Volume`), Stooq, brokers, or
wide frames (`AAPL.Open`, …) all load as-is. Daily bars, any date order.

```csv
date,open,high,low,close
2023-01-03,100.00,101.20,99.50,100.80
2023-01-04,100.80,102.10,100.40,101.90
```

When an adjusted-close column is present, the **whole OHLC bar is scaled by the
split/dividend factor** so a 2-for-1 split never reads as a 50% "lower low".
Disable with `load_csv(path, adjust=False)` if your source is already raw.

## Alpaca Markets (live data + paper trading)

Trendrail talks to [Alpaca](https://alpaca.markets) for real-time-ish data and
order placement — standard library only, no SDK. **Start with a free paper
account.** Put your keys in the environment (never in code or shell history):

```bash
export APCA_API_KEY_ID=your_paper_key_id
export APCA_API_SECRET_KEY=your_paper_secret
```

```bash
# Account & open positions (paper)
python -m trendrail.cli account

# Data from Alpaca (split/dividend adjusted)
python -m trendrail.cli backtest --symbol AAPL --provider alpaca --account 1000 -v

# Scan a symbol and size a stop-protected order against your live equity.
# DRY RUN by default — prints the order, sends nothing:
python -m trendrail.cli trade AAPL --risk 0.01

# Actually submit it to your PAPER account:
python -m trendrail.cli trade AAPL --risk 0.01 --confirm
```

The entry is sent as an **OTO order** — a buy with a protective stop-loss
attached, so rule #3 (a stop the moment you enter) is enforced by the broker,
not your nerves. Position size is computed from your *real* account equity so
"risk 1%" means 1% of the actual account.

### Managing open positions (trail stops, exit broken trends)
Rules #5 and #6 — trail the stop up, exit when the trend breaks — run with
`manage`. It reads each open position, and on the latest daily bar either:

* **exits** (cancels the stop, closes at market) if the trend broke — a close
  below the 50-day average or a lower low; or
* **raises the stop** under the newest higher swing low (never lowers it); or
* **installs a stop** if a position somehow has none; or
* **holds**.

```bash
# Review what would happen to every open position (DRY RUN — acts on nothing)
python -m trendrail.cli manage

# Just one symbol, and actually amend/close orders on the paper account
python -m trendrail.cli manage AAPL --confirm
```

Because the rules act on **daily** bars, run `manage` once per day after the
close — e.g. a cron entry:

```cron
30 21 * * 1-5  cd /path/to/Trendrail && /usr/bin/python3 -m trendrail.cli manage --confirm >> manage.log 2>&1
```

The same safety rails apply: paper by default, dry run unless `--confirm`, and
LIVE management needs `--live --i-understand-live`.

> 🔴 **Live trading risks real money.** Live orders require **both** `--live`
> **and** `--i-understand-live`, on top of `--confirm`. Don't reach for them
> until you've paper-traded the rules without flinching. Free Alpaca data uses
> the `iex` feed; `--feed sip` needs a paid subscription. This software comes
> with no warranty and is not financial advice.

### Example backtest output
```
Starting equity  : 1,000.00
Ending equity    : 1,252.00
Total return     : +25.20%
Max drawdown     : -2.28%
Closed trades    : 2
Win rate         : 100.0%
Expectancy       : +7.13R per trade
Profit factor    : inf
```

---

## How it's organized

| Module | Responsibility |
| --- | --- |
| `trendrail/web.py` | Local browser dashboard (`python -m trendrail.web`) |
| `trendrail/data.py` | `Bar` type + robust CSV loader (column matching, adjustment) |
| `trendrail/indicators.py` | SMAs and **causal** swing-point detection |
| `trendrail/strategy.py` | The rules above, as signals (trend filter, entries, stop, exit) |
| `trendrail/backtest.py` | Bar-by-bar simulator: risk-based sizing, trailing stops, stats |
| `trendrail/fetch.py` | Free no-key data: Stooq + Yahoo |
| `trendrail/alpaca.py` | Alpaca data, account/positions/orders, trade & manage logic |
| `trendrail/cli.py` | `backtest`, `scan`, `fetch`, `account`, `trade`, `manage` |
| `examples/` | Synthetic + real (AAPL) sample data and the generator |
| `tests/` | 47 unit tests (`python -m unittest discover -s tests`) |

**A note on honesty:** every signal is *causal* — a value at bar *i* is computed
only from bars at or before *i*. Swing pivots need confirmation bars, so a pivot
is only acted on once the market has actually revealed it. A backtest that peeks
at the future looks brilliant and trades terribly; Trendrail refuses to peek.

## Tuning
Defaults match the written rules (50/200 MA, 20-day breakout, 1–2% risk). The
knobs live in `StrategyConfig` and as CLI flags (`--fast-ma`, `--slow-ma`,
`--breakout-lookback`, `--risk`, `--account`). Change them on a *copy* and
re-backtest — don't tweak mid-trade.

## Testing
```bash
python -m unittest discover -s tests -v
```

## The business around Trendrail

This repo also contains a complete plan for turning Trendrail into an
owner-operated product business (**Trendrail Pro** — sell the discipline, not
predictions). Start at [`business/PLAN.md`](business/PLAN.md); the financial
projections in [`business/FINANCIALS.md`](business/FINANCIALS.md) are
generated by `python business/model.py --md`, and a deployable landing page
lives in [`site/`](site/).
