# Higgsfield pay-as-you-go API — setup & cheap-generation test

Goal: use Higgsfield's new **pay-per-use API** (launched Sep 16) and the **7-day
launch discount** to find the cheapest viable image/video models, separate from
your Max subscription.

## The launch offer (7 days from when you claim it)
- **15% off** all "sale" models, applied automatically
- Pick **2 video models + 1 image model** for **up to 50% off**
- **$15 in free credits** when you connect a card with an eligible business email
- Pay-per-use in USD, **no subscription**; **$5 minimum top-up**; spend stops at $0
- **Video billed per second**, **images per image** (DoP is per-generation)
- One key unlocks 50+ models; 20 concurrent requests

## Step 1 — Claim it (you, in a browser — I can't do billing)
1. Go to the Higgsfield API console (`console.higgsfield.ai` / `cloud.higgsfield.ai`).
2. Sign up for the API, connect a card with an eligible **business email** → $15 free credits.
3. Select your **2 video + 1 image** discounted models (this starts the 7-day clock).
4. Top up the **$5** minimum.
5. Create an **API key** (and secret, if shown).

## Step 2 — Add credentials
Paste them into `.env` (already created, git-ignored so they never get committed):
```
HIGGSFIELD_API_KEY=...
HIGGSFIELD_API_SECRET=...
```

## Step 3 — Verify the endpoint schema (30 seconds)
The docs site was network-blocked while this was built, so open
`docs.higgsfield.ai` and confirm the four ALL-CAPS constants in the CONFIG block
at the top of `higgsfield/client.py` match the quickstart:
`SUBMIT_PATH`, `STATUS_PATH`, `BALANCE_PATH`, and the status/cost/output field
names. Adjust if needed — nothing else should change.

## Step 4 — Run the cost comparison
```bash
pip install -r requirements.txt

# see the plan without spending anything
python -m higgsfield.cost_test --kind image --dry-run

# real runs (each one charges your API balance)
python -m higgsfield.cost_test --kind image
python -m higgsfield.cost_test --kind video --prompt "a neon city drone shot"
```
Every run appends to `cost_results.csv` and prints a **cheapest-first** table, so
you can see exactly what each model costs and lock in the discounted ones.

Edit the `IMAGE_MODELS` / `VIDEO_MODELS` lists in `higgsfield/cost_test.py` with
the real model slugs + params from the console catalog (put your 3 discounted
models at the top).

## Note on running from this Claude session
This remote environment's network policy **blocks all `higgsfield.ai` hosts**, so
the API calls above must run on **your own machine** (or in an environment whose
egress policy allows Higgsfield). The Higgsfield **MCP tools** in the Claude
session still work, but those spend **Max-plan credits**, not the discounted API
balance — so they don't measure API cost.
