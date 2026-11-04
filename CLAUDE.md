# M&S Pudding Map

mcbroken-style map: are the new M&S puddings and cookie doughs in stock at each store around London?

- `scripts/poll.py` opens the product page in a browser and runs M&S's own store-modal calls as in-page fetches:
  range (stores that sell it) + one GraphQL `GetStockLevel` for all of them. No clicks, no model calls.
- Products: `data/products.json` (id, slug, names, pack colours for the skin). Add one there and it's polled and
  appears in the title's flavour menu. Any store with a stock reading counts as selling it.
  Announced but not on M&S yet: leave out `id`/`url` and add `"soon": "YYYY-MM-DD"`; it shows as coming soon, unpolled.
  With an `id` and `"soon"`, it stays coming soon while M&S stock says not found; drop `"soon"` once it reads.
- In-store bakery products (`"bakery": true`; M&S page JSON has `"isISBProduct":true`): M&S's own site skips the stock
  check and says "Freshly baked – Ask in store", so the poll only reads the range and stores show "Ask in store".
  `"new": false` drops the NEW IN tag on the chooser card.
- Codes (from M&S `_app.js`): H/M = in stock, L = low, O = out. Not in range = not sold. No reading ('unknown') is
  kept in the data but never shown to visitors.
- Store popups show "Best time to look" (that store's best two shop hours this week). The 7-day grid is dev only (localhost or `?dev`).
- Scope: London + ~50 miles (`BOX` in `poll.py`); the page opens on central London. Store list from 24 seed towns,
  no ownedBys filter (station franchises sell M&S food), cached in `data/stores.json`, refreshed weekly.
  Northern Ireland stores only have the `FOODSCATALOGUE` capability, not `FOOD`.
- Keep load low: one poll per 30 min. Never present the site as M&S.
- GitHub Actions (`.github/workflows/poll.yml`) polls and deploys `public/` to Pages. A failed poll doesn't deploy.
- What starts it: cron-job.org POSTs `workflow_dispatch` every 30 min (fine-grained token, Actions read/write,
  this repo only; it lives in cron-job.org, renew yearly). GitHub's own `schedule` (:13/:43, fires irregularly) is
  only a backup: its `guard` job skips the poll unless no dispatch/push run started in the last 25 min.
  Pages deploy retries once; a failed store-list push never blocks the deploy.
  Stale map? Check cron-job.org's history first, then `gh run list`.
- Mapbox tokens: DEV in `.env` (local, allows 127.0.0.1:8731); PROD only in the GitHub secret `MAPBOX_TOKEN`
  (URL-restricted to heyhaiden.github.io). Update prod with `gh secret set MAPBOX_TOKEN`, never `-f .env`.
- If Actions gets blocked: `uv run --with-editable ../jev-ultrafast python -m scripts.poll --local` uses your Chrome.
- `scripts/history.py` keeps 30 days of readings, one letter per store per 30-min slot, in `public/history.json`.
  On Actions the run fetches the deployed copy (SITE_URL) and adds to it; only a 404 starts afresh.
- `scripts/og.py` renders `public/og.png` (link preview) after each poll; deploy rewrites its URL to absolute.

Checks: `uv run ruff check . && uv run pytest`. Live run: `uv run python -m scripts.poll` (~35s).
