# The three warm yeses — how to actually run it

The cheapest, highest-signal validation available. It costs £0, needs no
traffic, and does not depend on what the paper account did this week.

**The goal:** three sincere "yes, I'd pay £12/month for that" answers from
real traders, in direct conversation. Three yeses = a pulse. Ten blank
stares = a messaging finding, which is also worth having.

**Why "warm":** you ask people you have *some* connection to — someone whose
post you replied to, a person you know who trades, someone already in a
community you genuinely participate in. Cold-DMing strangers is spam, gets
you banned, and produces polite lies. Warm asks produce honest answers.

---

## 1. Who counts (the profile)

You are looking for someone who:

- trades their own money, **swing/position style** (days to weeks — not scalpers),
- has **rules they don't always follow** — this is the core pain,
- has felt the specific sting: moved a stop, sized by conviction, revenge-traded,
- is **not** a professional quant (they'd build it themselves).

One good-fit answer beats ten from people who'd never buy.

**Where to find them, in order of warmth:**

1. **People you already know** who trade. Start here. It feels awkward; do it anyway.
2. **Communities you already read** — r/swingtrading, r/algotrading, trading
   Discords. Reply usefully to a few threads *first* (a week of genuine
   participation), then ask the people whose problems match.
3. **X/Twitter replies** — people posting about blowing through a stop or
   over-sizing. Reply with something genuinely useful, then ask.
4. **Anyone who signs up** to The Trend Check from here on.

---

## 2. The rules (do not break these)

- **Disclose you built it.** Every single time. "I'm building something —"
  never pretend to be a neutral punter.
- **No return promises.** Not even casually, not even in a DM. The same
  compliance line applies in private as in public (LEGAL.md §2).
- **Don't pitch.** You are asking a question, not selling. If you find
  yourself explaining for three paragraphs, stop.
- **Never mass-paste.** Ten tailored messages beat a hundred copies.
- **Take a no gracefully and ask why.** The no is the valuable part.

---

## 3. The scripts

### A. Someone you know

> Can I get your honest opinion on something? I've been building a tool for
> my own trading and I can't tell if it's just useful to me.
>
> It takes a written ruleset and enforces it on your own account — works out
> the position size from your risk, puts the stop in *with* the entry so
> there's never a naked position, trails it daily, and journals every trade
> in R-multiples. No predictions, no signals, no "buy this now."
>
> Honestly: would you pay £12 a month for that, or is that a "nice idea, but
> no"? I'd genuinely rather hear no now than build the wrong thing.

### B. Reply to someone describing the pain

*(after you've said something actually useful about their situation)*

> That thing you said about moving your stop — that's exactly the problem I'm
> building for. It sizes the trade off your risk, attaches the stop to the
> entry so it can't be quietly skipped, trails it every day, then scores you
> on whether you followed your own rules.
>
> Can I ask you a blunt question since you've lived it — would you pay £12 a
> month for something that enforced your rules for you? Straight answer is
> fine either way.

### C. To a Trend Check subscriber

> You've been getting the Sunday email — thank you. Quick question while I
> decide what to build next.
>
> The paid version would run the same ruleset on *your* account: sizing from
> your risk, the stop attached to the entry, trailed daily, plus a journal
> that scores you in R. Keys stay on your machine.
>
> Would that be worth £12/month to you? A no is genuinely useful.

---

## 4. Scoring the answers — this is where people fool themselves

Politeness looks like enthusiasm. Grade honestly:

| Answer | Score |
|---|---|
| "Yeah that sounds great, good luck!" | ❌ **Not a yes.** Enthusiasm with no cost. |
| "Cool idea, I'd definitely check it out." | ❌ **Not a yes.** "Check out" ≠ pay. |
| "Yes — how much again? When's it out?" | ⚠️ **Warm.** Asking about price/date is real interest. Push to the next line. |
| "Yes, £12 is fine. Tell me when it's live." | ✅ **A yes.** |
| "Yes — put me on the list, I'll pay when it launches." | ✅✅ **A strong yes.** Log the name. |
| "No, I already do this manually." | ❌ No — **and a finding.** Ask what they use. |
| "No, I wouldn't pay for software I could script." | ❌ No — that's the free tier's audience, not Pro's. |

**The confirming question** — use it whenever you get a soft yes:

> If it were live today, would you put your card in — or is it more of a
> "maybe later" thing?

That single sentence separates real demand from politeness. Ask it every time.

---

## 5. Log everything

After each conversation, add a line to `business/metrics.csv` notes (or the
table below). Record the **no**s and their reasons just as carefully — a
pattern in the noes is worth more than a yes.

| Date | Who (first name / handle) | Where | Fit? | Answer | Their words |
|---|---|---|---|---|---|
| | | | | | |

**Target: ask ~10 well-fitting people. Three sincere yeses passes the gate.**

---

## 6. What each outcome means

- **3+ yeses** → real demand. Proceed to incorporation and build Pro. The
  paper account's P&L does not change this reading.
- **1–2 yeses out of ~10** → the need is real but the pitch or price is off.
  Re-read their exact words; the fix is usually messaging, not the product.
- **0 yeses, lots of "cool idea"** → you're solving a problem people don't
  feel *painfully enough to pay for*. That's the finding, and it is worth
  far more than another month of building. Stop before spending (START_HERE
  gate).

---

## 7. Why this beats waiting for a green paper account

Trend-following can be flat or down for months and still be working exactly
as designed. If the launch waits on a green number, the timeline belongs to
the market rather than to you — and a green number would not have proved
demand anyway. What sells Trendkept is **enforcement of discipline**, which
is true whatever SPY did this week. This test measures the thing that
actually decides whether there is a business.
