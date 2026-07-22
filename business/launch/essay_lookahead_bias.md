# Draft essay — "Look-ahead bias: the reason your backtest lies to you"

**Pillar:** honest backtesting. **Postable now** (technical/educational, no
personal claims). **Where:** blog, then r/algotrading or Hacker News
(this audience rewards technical honesty and open source — link the repo).
~650 words. Your name, your voice.

---

## Look-ahead bias: the reason your backtest lies to you

You built a strategy. You backtested it. The equity curve goes up and to
the right like a staircase to heaven. You go live. It bleeds. What
happened?

Nine times out of ten, your backtest cheated — and you didn't tell it to.
The most common way is **look-ahead bias**: somewhere in the code, a
decision made on day *i* quietly used information that only existed on day
*i+1* or later. The backtest "knew" the future, so of course it looks
brilliant. The live market doesn't extend you that courtesy.

It creeps in through the dullest doors:

- **Indicators computed over the whole series.** You normalise or scale a
  feature using the full dataset's mean and standard deviation — which
  includes future data — then test "as if" you knew that scaling on day
  one. You didn't.
- **Signals that use the current bar's close to decide to trade *during*
  that bar.** If your rule fires on today's close, you cannot also have
  entered at today's open. Pick one; be honest about which.
- **Survivorship bias's cousin:** filling a trade at a price that wasn't
  actually available (the exact high, a mid-price that never traded),
  which quietly imports future/idealised information into the fill.

The tell is emotional as much as technical: **if a backtest looks
too good, it's usually cheating, not genius.** Real edges are modest and
lumpy. A curve with no ugly stretches is a curve that peeked.

The fix is a discipline, not a library. Make your backtest *causal* by
construction: a decision at bar *i* may only touch data from bar *i* and
earlier — full stop. Compute rolling statistics on trailing windows, not
the whole series. Enter on the *next* bar's open after a signal fires on
this bar's close, not magically at this bar's price. And label your fills
honestly as idealised — because even a causal backtest assumes you got
filled at a clean price, and real markets gap, slip and surprise.

Here's the mindset shift that helps: **a backtest's job is not to impress
you. It's to try its hardest to talk you out of the strategy, and fail.**
If it can't cheat, and it still shows a positive expectancy across decades
and an out-of-sample stretch it never saw during tuning, *then* you have
something worth risking money on. If it needed to peek to look good, you've
learned something cheaply — before the market taught you expensively.

This is also why I have a soft spot for open-source backtesters:
you can read exactly where the decision boundary is and check it doesn't
leak. A closed "97% win rate" bot that won't show its code is asking for
a lot of faith at exactly the point where faith is most expensive.

Backtesting honestly is unglamorous. It turns dazzling curves into modest
ones and kills a lot of ideas you were excited about. That's the point.
The modest, honest curve is the one that might survive contact with the
real thing.

---

*(If it fits: my trend-following toolkit is built causal-by-construction
and it's open source, so you can audit the no-peek boundary yourself —
[github.com/adelvespayne-png/Trendkept]. But the principle matters more
than any one tool: make your backtest earn your trust the hard way.)*
