# Outreach pack — everything ready to paste, in order

**The split:** Claude writes every word and drafts every reply. The owner
supplies the account and presses send. Nothing here may be posted by anyone
other than Archie — every post says "I built this", and that has to be true.

**Why Claude does not post directly:** it would be impersonating a real
person; Reddit and X detect and ban automated posting, which would burn the
name; and a bot-run conversation produces worthless demand data. The whole
value of a "warm yes" is that a real person said it to a real person.

**Ground rules for every message, DM and comment:**
1. Always disclose you built it.
2. Never promise returns — not even casually, not even in a DM (LEGAL.md §2).
3. Never give advice about anyone's money. Describe, never instruct.
4. Don't pitch. You are asking a question.
5. Never paste the same text twice in the same place.

---

## WEEK 0 — today, 10 minutes

### Step 1 (2 min): the referral text
WhatsApp, one-to-one, to ~10 ordinary contacts. Not group-blasted. They do
not need to trade — you are asking who they *know*.

> Random one mate — do you know anyone who's into trading stocks? Building
> something for traders and I need to ask someone a couple of questions. No
> selling, just need an actual trader's opinion.

### Step 2 (3 min): the story
Instagram / Snapchat. Reaches everyone at once, near-zero effort.

> Building something for people who trade stocks 📈
> Know anyone who trades? DM me — need to ask them one question.

### Step 3 (5 min): make the Reddit account
reddit.com → sign up. Pick a neutral, human username — **not**
"TrendkeptOfficial"; a brand account cannot credibly do Week 1.
**Post nothing yet.** Join r/swingtrading, r/algotrading, r/stocks.

---

## WEEK 1 — become a face, not a stranger

**15 minutes a day. No links. No mention of Trendkept. At all.**

New accounts get auto-removed by spam filters, and a first post that is a
pitch is dead on arrival. So be useful first, for a week.

Search these phrases and reply to ~3 posts a day:

- "position size" · "how much should I risk" · "moved my stop"
- "stopped out" · "revenge trade" · "blew up my account"

**You can genuinely answer these now.** Adapt these; never paste verbatim.

*On sizing:*
> The formula that fixed this for me: shares = (account × risk %) ÷ (entry −
> stop). At 1% of a £10k account: entry 50, stop 48 → 50 shares; stop 42 →
> 12 shares. The wider the stop, the smaller the position, automatically.
> There's no conviction knob in it, which is the point.

*On moving a stop:*
> What helped me was sending the stop with the entry as one order, so there's
> no later moment where I get to decide. The version of you placing the trade
> is calm; the version watching it fall isn't. Sending both at once means the
> calm one decides.

*On a losing streak:*
> Worth separating "my losses are bigger than 1R" from "I'm having a normal
> losing run". The first is a broken risk rule and needs fixing today. The
> second is just what the distribution feels like from the inside.

After ~15 helpful comments you have history, karma and a recognisable name.

---

## WEEK 2 — ask

### A. DM the people whose posts described the pain
You are now "the person who gave me a straight answer about sizing".

> Hey — you mentioned [their specific problem] the other day. I've been
> building something for exactly that: it takes a written ruleset and enforces
> it on your own account. Sizes off your risk, puts the stop in *with* the
> entry so it can't be skipped, trails it daily, journals everything in R.
> No predictions, no signals.
>
> Blunt question since you've lived it — would you pay £12 a month for that,
> or is it a solved problem for you? A straight no is genuinely useful.

### B. One public question post
Market research, not a results post, so it clears our own gate.
Title:

> Would you pay for something that enforces your own trading rules?

Body:

> I've been building a tool for my own trading and I can't tell if it's only
> useful to me.
>
> It takes a written ruleset and enforces it: works out position size from
> your risk, attaches the stop to the entry so there's never a naked position,
> trails it daily, and journals every trade in R-multiples. It doesn't predict
> anything and doesn't send signals — it just stops me overriding myself.
>
> It's open source, and I'm running it on a paper account in public, losses
> included — currently down about [X]% across [N] trades, mostly because
> almost nothing on the watchlist has been in an uptrend for weeks.
>
> Genuine question: is that worth £12/month to anyone, or is it a solved
> problem? Happy to hear no.

**Check `business/paper_log.csv` and use the true numbers on the day.**

### C. The value post that brings people to you
`business/launch/essay_lookahead_bias.md` — postable as-is to r/algotrading.
Technical, honest, no personal claims. Inbound beats outbound.

---

## LATER — hold these back

- **Show HN** (`business/launch/show_hn.md`) — one good shot. Save it until
  the log is mature and there are a couple of real users.
- **r/swingtrading results post** (`business/launch/reddit_swingtrading.md`) —
  gated on 4+ weeks of log, by our own rule.
- **X/Twitter** — slow burn, needs daily presence. Lowest return right now.

---

## SCORING what comes back

| They say | Score |
|---|---|
| "Sounds great, good luck!" | ❌ not a yes |
| "I'd definitely check it out" | ❌ not a yes |
| "Yes — how much? when's it out?" | ⚠️ warm, push once |
| "Yes, £12 is fine, tell me when it's live" | ✅ **a yes** |
| "Put me on the list, I'll pay at launch" | ✅✅ **strong yes** |
| "No, I do this manually" | ❌ no — **ask what they use** |

**The confirming question, every time you get a soft yes:**
> If it were live today, would you put your card in — or is it more of a
> "maybe later" thing?

Log every answer, especially the noes, in the table in
`business/THREE_WARM_YESES.md`. **Three sincere yeses passes the gate.**

---

## When someone replies

Send the thread to Claude. You get back a draft reply in your voice, checked
against the compliance rules, plus an honest score on whether it is a real
yes. You edit and send.
