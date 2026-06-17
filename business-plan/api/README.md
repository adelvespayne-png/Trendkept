# Stillwater — Reference API & Website

A **dependency-free** (Python 3.9+ standard library only) demo of the
operational backbone for the supplement brand described in this `business-plan/`
folder. Same philosophy as the rest of this repo: no `pip install`, runnable
today, the rules written down in code.

> **This is a reference/demo, not a production store.** It uses an in-memory
> store and a *mock* fulfillment hand-off — there is no real payment capture.
> Its purpose is to show the **compliant shape** of each piece. In production
> you'd run on a real e-commerce platform (see `../06-ai-automation-stack.md`).

## Run it

```bash
cd business-plan/api
python3 server.py            # http://127.0.0.1:8000
# or choose a port:
PORT=8077 python3 server.py
```

Then open <http://127.0.0.1:8000> for the storefront.

## What's here

| File | Role |
|------|------|
| `server.py` | Stdlib HTTP server: JSON API + serves the static site in `../site` |
| `claims.py` | The **claims-compliance gate** from `../06` — screens copy for illegal disease claims; never auto-approves |
| `catalog.py` | Reference product (single hero SKU + subscribe-and-save), compliant copy |
| `../site/` | The storefront (HTML/CSS/JS) — trust-first, consumes the API |
| `../tools/unit_economics.py` | The economics gates from `../04`, reused by `/api/economics` |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/categories` | The three categories (Supplements, Vitamins, Skincare) |
| GET | `/api/products` | Catalog with compliant copy; optional `?category=skincare` |
| POST | `/api/claims-check` | Run the compliance gate. Body: `{"copy":"...","product_type":"supplement"\|"skincare"}` |
| POST | `/api/economics` | Run the unit-economics gates. Body: `{"price":35,"cogs":9,"expected_orders":6,...}` |
| POST | `/api/orders` | Create a mock order/subscription. Body: `{"sku":"...","email":"...","marketing_consent":true}` |
| GET | `/` | The storefront |

> **Two compliance regimes.** The claims gate screens **supplements/vitamins**
> (structure/function + FDA disclaimer) and **skincare/cosmetics** (appearance
> claims only, no drug claims) with different rules. On startup the server
> **audits every catalog product's copy** against its regime and refuses to
> claim compliance if any fail — non-compliant copy can't slip through unnoticed.

### Examples

```bash
# Compliance gate catches illegal claims:
curl -s -X POST localhost:8000/api/claims-check \
  -H 'Content-Type: application/json' \
  -d '{"copy":"This cures insomnia and treats anxiety"}'
#   -> passed: false, prohibited_hits: ["cures","treats","anxiety","insomnia"]

# Economics gate enforces the file 04 thresholds:
curl -s -X POST localhost:8000/api/economics \
  -H 'Content-Type: application/json' \
  -d '{"price":35,"cogs":9,"expected_orders":6}'
#   -> all_gates_pass: true

# A one-off (expected_orders:1) fails LTV:CAC — the whole point of subscriptions.
```

## How this maps to the plan

- **Compliance is the default path** (`02`, `06`): every product field is
  pre-written in structure/function language, the FDA disclaimer ships from the
  catalog, and `claims.py` gates any new copy.
- **Subscription is the engine** (`04`): the catalog defaults to subscribe-and-
  save; `/api/economics` proves a one-off loses money where a subscription wins.
- **Honest subscriptions** (`02`, `07`): orders return a real `cancel_url` and
  `one_click_cancel: true`; no free-trial/surprise-auto-ship pattern.
- **Blind-ship fulfillment** (`07`): orders queue to the supplier with
  `blind_ship: true`.

## Notes / limitations (honest)

- In-memory data resets on restart; no database.
- No real payments, auth, or rate limiting — add these before any real use.
- The claims gate is a deterministic first pass. In production it sits in front
  of an LLM check **and** a human reviewer; it must never be the sole approver.
