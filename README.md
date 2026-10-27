# M&S Pudding Map

mcbroken-style map: is the M&S Banana, Caramel and Pecan Pudding (61273052) in stock at each UK store?

- `scripts/poll.py` opens the product page in a browser and runs M&S's own store-modal calls as in-page fetches:
  range (stores that sell it) + one GraphQL `GetStockLevel` for all of them. No clicks, no model calls.
- Codes (from M&S `_app.js`): H/M = in stock, L = low, O = out. Not in range = not sold.
- Scope: London + ~50 miles (`BOX` in `poll.py`); the page opens on central London. Store list from 24 seed towns,
  no ownedBys filter (station franchises sell M&S food), cached in `data/stores.json`, refreshed weekly.
  Northern Ireland stores only have the `FOODSCATALOGUE` capability, not `FOOD`.
- Keep load low: one poll per 30 min. Never present the site as M&S.
- GitHub Actions (`.github/workflows/poll.yml`) polls and deploys `public/` to Pages. A failed poll doesn't deploy.
- If Actions gets blocked: `uv run --with-editable ../jev-ultrafast python -m scripts.poll --local` uses your Chrome.
- `scripts/history.py` keeps 30 days of readings, one letter per store per 30-min slot, in `public/history.json`.
  On Actions the run fetches the deployed copy (SITE_URL) and adds to it; only a 404 starts afresh.
- `scripts/og.py` renders `public/og.png` (link preview) after each poll; deploy rewrites its URL to absolute.

Checks: `uv run ruff check . && uv run pytest`. Live run: `uv run python -m scripts.poll` (~35s).
