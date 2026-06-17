# Archie

A small, dependency-free toolkit for one thing: trading a **confirmed uptrend
with disciplined risk**. Archie turns a mechanical trend-following ruleset into
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

Never chase a move that has already run far: Archie refuses any entry more than
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
# Backtest the rules over a price history
python -m archie.cli backtest examples/sample_uptrend.csv --account 1000 --risk 0.02 -v

# Ask the rules what to do *today* (the paper-trading helper)
python -m archie.cli scan examples/sample_uptrend.csv --account 1000 --risk 0.02
```

### Your own data
Provide a CSV with a header row and columns `date,open,high,low,close`
(`volume` optional). Daily bars, oldest or newest first — Archie sorts by date.

```csv
date,open,high,low,close
2023-01-03,100.00,101.20,99.50,100.80
2023-01-04,100.80,102.10,100.40,101.90
```

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
| `archie/data.py` | `Bar` type + CSV loader |
| `archie/indicators.py` | SMAs and **causal** swing-point detection |
| `archie/strategy.py` | The rules above, as signals (trend filter, entries, stop, exit) |
| `archie/backtest.py` | Bar-by-bar simulator: risk-based sizing, trailing stops, stats |
| `archie/cli.py` | `backtest` and `scan` commands |
| `examples/` | Deterministic sample data + its generator |
| `tests/` | Unit tests (`python -m unittest discover -s tests`) |

**A note on honesty:** every signal is *causal* — a value at bar *i* is computed
only from bars at or before *i*. Swing pivots need confirmation bars, so a pivot
is only acted on once the market has actually revealed it. A backtest that peeks
at the future looks brilliant and trades terribly; Archie refuses to peek.

## Tuning
Defaults match the written rules (50/200 MA, 20-day breakout, 1–2% risk). The
knobs live in `StrategyConfig` and as CLI flags (`--fast-ma`, `--slow-ma`,
`--breakout-lookback`, `--risk`, `--account`). Change them on a *copy* and
re-backtest — don't tweak mid-trade.

## Testing
```bash
python -m unittest discover -s tests -v
```
