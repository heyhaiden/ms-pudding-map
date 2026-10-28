# M&S Pudding Map

mcbroken-style map: are the new M&S puddings and cookie doughs in stock at each store around London?

- `scripts/poll.py` opens the product page in a browser and runs M&S's own store-modal calls as in-page fetches:
  range (stores that sell it) + one GraphQL `GetStockLevel` for all of them. No clicks, no model calls.
- Products: `data/products.json` (id, slug, names, pack colours for the skin). Add one there and it's polled and
  appears in the title's flavour menu. Any store with a stock reading counts as selling it.
- Codes (from M&S `_app.js`): H/M = in stock, L = low, O = out. Not in range = not sold. No reading ('unknown') is
  kept in the data but never shown to visitors.
- Dev: localhost (or ?dev) shows a DEV pill that toggles the hidden 7-day grid in store popups.
- Scope: London + ~50 miles (`BOX` in `poll.py`); the page opens on central London. Store list from 24 seed towns,
  no ownedBys filter (station franchises sell M&S food), cached in `data/stores.json`, refreshed weekly.
  Northern Ireland stores only have the `FOODSCATALOGUE` capability, not `FOOD`.
- Keep load low: one poll per 30 min. Never present the site as M&S.
- GitHub Actions (`.github/workflows/poll.yml`) polls and deploys `public/` to Pages. A failed poll doesn't deploy.
- What starts it: cron-job.org POSTs `workflow_dispatch` every 30 min (fine-grained token, Actions read/write,
  this repo only; it lives in cron-job.org, renew yearly). GitHub's own `schedule` is only a backup: it never fired
  on this repo. Stale map? Check cron-job.org's history first, then `gh run list`.
- Mapbox tokens: DEV in `.env` (local, allows 127.0.0.1:8731); PROD only in the GitHub secret `MAPBOX_TOKEN`
  (URL-restricted to heyhaiden.github.io). Update prod with `gh secret set MAPBOX_TOKEN`, never `-f .env`.
- If Actions gets blocked: `uv run --with-editable ../jev-ultrafast python -m scripts.poll --local` uses your Chrome.
- `scripts/history.py` keeps 30 days of readings, one letter per store per 30-min slot, in `public/history.json`.
  On Actions the run fetches the deployed copy (SITE_URL) and adds to it; only a 404 starts afresh.
- `scripts/og.py` renders `public/og.png` (link preview) after each poll; deploy rewrites its URL to absolute.

Checks: `uv run ruff check . && uv run pytest`. Live run: `uv run python -m scripts.poll` (~35s).
