"""Read M&S stock for each product in data/products.json across stores around London; write public/stock.json.

A real browser opens the product page, which gives it an M&S guest session. Every M&S call then runs as a fetch
inside that page, the same calls the "Select your store" modal makes: range (which stores sell it) and one stock
query for all of them. No clicks, no model calls.

  uv run python -m scripts.poll                         headless Chromium (what GitHub Actions runs)
  uv run --with-editable ../jev-ultrafast python -m scripts.poll --local    your Chrome via Jev's Browser
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import history, og
from scripts.posthog_client import get_posthog_client
from scripts.posthog_logs import get_posthog_logger
from scripts.stock import join, stores_from

# Any product page gives the browser a guest session; this one also owned the single-product history.
PRODUCT = "61273052"
PAGE = "https://www.marksandspencer.com/food/banana-caramel-and-pecan-pudding/p/fdp" + PRODUCT
ROOT = Path(__file__).resolve().parent.parent
STORES = ROOT / "data" / "stores.json"
PRODUCTS = ROOT / "data" / "products.json"
OUT = ROOT / "public" / "stock.json"
OG = ROOT / "public" / "og.png"
HISTORY = ROOT / "public" / "history.json"
CONFIG = ROOT / "public" / "config.js"
ENV = ROOT / ".env"
STORES_MAX_AGE = timedelta(days=7)
# London and roughly 50 miles around it: Oxford to Canterbury, Milton Keynes to Brighton. Seeds overlap, so one
# failing town loses nothing.
SEEDS = ["London", "Watford", "Enfield", "Romford", "Croydon", "Kingston upon Thames", "Uxbridge", "Dartford",
         "Reading", "Oxford", "High Wycombe", "Luton", "Milton Keynes", "Stevenage", "Chelmsford", "Colchester",
         "Southend-on-Sea", "Maidstone", "Canterbury", "Tunbridge Wells", "Brighton", "Crawley", "Guildford",
         "Basingstoke"]
BOX = {"south": 50.78, "west": -1.35, "north": 52.10, "east": 1.15}
BLOCKED = ("access denied", "captcha", "verify you are human", "unusual traffic", "request blocked")

# Shared by both scripts below: the guest token from the page's own session and the GraphQL endpoint.
PRELUDE = """
  const session = await (await fetch('/api/auth/session')).json();
  if (!session.accessToken) return {error: 'no guest token'};
  const auth = {authorization: 'Bearer ' + session.accessToken};
  const graphql = async (query, variables) => {
    const r = await fetch('https://experience.marksandspencer.app/v1/graphql', {method: 'POST', body: JSON.stringify(
      {query, variables}), headers: {...auth, 'content-type': 'application/json',
      'mns-graphql-client-name': 'food-catalogue', 'x-ms-graphql-client-name': 'food-catalogue'}});
    if (!r.ok) throw new Error('graphql ' + r.status);
    return r.json();
  };
"""
STOCK_JS = """async ([product, ids]) => {""" + PRELUDE + """
  const range = await fetch('https://api.range.marksandspencer.app/v1/range/product/' + product, {headers: auth});
  if (!range.ok) return {error: 'range ' + range.status};
  // Only ask about our stores that sell it, not the whole country.
  const ours = new Set(ids);
  const ranged = (await range.json()).stores.map(s => s.storeId).filter(id => ours.has(id));
  const d = await graphql(`query GetStockLevel($input: Stock_GetFoodStockLevelIndicatorInput!) { stock {
    getFoodStockLevelIndicator(input: $input) { __typename
      ... on Stock_GetFoodStockLevelIndicatorSuccess { indicator { stockLevelIndicator locationId } }
      ... on Stock_GetFoodStockLevelIndicatorFailure { errors { __typename ... on Stock_GenericError { message } } }
    } } }`, {input: {locationIds: ranged, productId: product}});
  const result = d?.data?.stock?.getFoodStockLevelIndicator;
  if (!result?.indicator) return {error: 'stock: ' + JSON.stringify(result?.errors || d.errors).slice(0, 300)};
  return {ranged, indicators: result.indicator, title: document.title};
}"""
STORES_JS = """async (seeds) => {""" + PRELUDE + """
  const locations = [], failed = [];
  // No ownedBys filter: franchise stores (e.g. SSP at London stations) also sell M&S food.
  for (const query of seeds) {
    const d = await graphql(`query Stores($query: String!) { location { location {
      getLocationsByQueryFilters(input: {query: $query, radius: 25, limit: 2000, countryCode: GB, statuses: [OPEN]}) {
        __typename ... on Location_LocationsGetByQuerySuccess {
          locations { id name capabilities type { name } coordinates { latitude longitude } } } } } } }`,
      {query});
    // M&S's location service sometimes errors on one town; neighbouring seeds overlap it.
    const found = d?.data?.location?.location?.getLocationsByQueryFilters?.locations;
    if (found) locations.push(...found); else failed.push(query);
  }
  if (failed.length === seeds.length) return {error: 'every store search failed'};
  return {locations, failed};
}"""
READY_JS = """async () => {
  const text = (document.title + ' ' + (document.body?.innerText || '')).toLowerCase();
  const session = await fetch('/api/auth/session').then(r => r.json()).catch(() => ({}));
  return {ready: !!session.accessToken, text: text.slice(0, 2000)};
}"""


class Blocked(RuntimeError):
    """M&S showed a block page or never gave the browser a guest session."""


class Playwright:
    """Headless Chromium. run(js, arg) calls an async JS function in the page and returns its value."""

    def __init__(self):
        from playwright.sync_api import sync_playwright

        self.pw = sync_playwright().start()
        # BROWSER_CHANNEL=chrome uses an installed Google Chrome (GitHub's runners have one) instead of Playwright's.
        self.browser = self.pw.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL") or None)
        self.page = self.browser.new_page(locale="en-GB", user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"))

    def go(self, url):
        self.page.goto(url, wait_until="domcontentloaded", timeout=45_000)

    def run(self, js, arg=None):
        return self.page.evaluate(js, arg)

    def close(self):
        self.browser.close()
        self.pw.stop()


class Jev:
    """Your Chrome through Jev's Browser. Its evaluate() doesn't await promises, so this calls CDP directly."""

    def __init__(self):
        from jev_ultrafast import Browser

        self.browser = Browser("about:blank")

    def go(self, url):
        self.browser.call("Page.navigate", url=url)

    def run(self, js, arg=None):
        response = self.browser.call("Runtime.evaluate", expression=f"({js})({json.dumps(arg)})",
                                     awaitPromise=True, returnByValue=True)
        if response.get("exceptionDetails"):
            raise RuntimeError(response["exceptionDetails"].get("exception", {}).get("description", "JS error"))
        return response.get("result", {}).get("value")

    def close(self):
        self.browser.close()


def open_page(driver, timeout=30):
    """Load the product page and wait for the guest session the page creates for itself."""
    driver.go(PAGE)
    deadline = time.monotonic() + timeout
    state = {}
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            state = driver.run(READY_JS) or {}
        except Exception:  # page still navigating
            continue
        if any(word in state.get("text", "") for word in BLOCKED):
            raise Blocked("M&S is showing a block page: " + state["text"][:200])
        if state.get("ready"):
            return
    raise Blocked("No M&S guest session after %ss. Page said: %s" % (timeout, state.get("text", "")[:200]))


def checked(result, what):
    if not result or result.get("error"):
        raise RuntimeError(f"{what} failed: {(result or {}).get('error', 'no result')}")
    return result


def load_env(path=ENV):
    """Fill the environment from a .env file. Variables already set win."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def write_config(token, path=CONFIG):
    token = token.strip()
    if not token:
        raise SystemExit("Set MAPBOX_TOKEN in .env or the environment.")
    path.write_text(f"const MAPBOX_TOKEN = {json.dumps(token)};\n")


def previous_history():
    """The history so far: the local file, else the deployed site's copy (SITE_URL), else None to start one.

    Only a 404 starts afresh. Any other failure stops the run, so a network blip never wipes the history.
    """
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if not site:
        return None
    try:
        with urllib.request.urlopen(f"{site}/history.json?t={int(time.time())}", timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def stale(path):
    if not path.exists():
        return True
    updated = datetime.fromisoformat(json.loads(path.read_text())["updated"])
    return datetime.now(timezone.utc) - updated > STORES_MAX_AGE


def poll(driver, posthog_client, posthog_logger):
    open_page(driver)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if stale(STORES):
        found = checked(driver.run(STORES_JS, SEEDS), "store list")
        stores = stores_from(found["locations"], BOX)
        if found["failed"]:
            print(f"warning: store search failed for {', '.join(found['failed'])}")
        STORES.write_text(json.dumps({"updated": now, "stores": stores}, indent=1) + "\n")
        if posthog_logger:
            posthog_logger.info(
                "store catalogue refreshed",
                extra={
                    "event": "store_catalogue_refreshed",
                    "store_count": len(stores),
                    "seed_count": len(SEEDS),
                    "failed_seed_count": len(found["failed"]),
                },
            )
        if posthog_client:
            posthog_client.capture(
                "store_list_refreshed",
                properties={
                    "store_count": len(stores),
                    "seed_count": len(SEEDS),
                    "failed_seed_count": len(found["failed"]),
                },
            )
        print(f"store list: {len(stores)} food stores from {len(SEEDS)} towns")
    stores = json.loads(STORES.read_text())["stores"]
    ids = [s["id"] for s in stores]
    products, readings = [], {}
    # One guest session covers every product: two M&S calls each (range + stock).
    for product in json.loads(PRODUCTS.read_text()):
        found = checked(driver.run(STOCK_JS, [product["id"], ids]), "stock for " + product["short"])
        out, counts, missing = join(stores, found["ranged"], found["indicators"])
        if missing:
            print(f"warning: {product['short']}: {len(missing)} ranged stores aren't in the store list")
        readings[product["id"]] = {s["id"]: s["status"] for s in out}
        # One letter per store, in the same order as "stores", keeps the file small.
        products.append({**product, "counts": counts, "statuses": "".join(history.CODE[s["status"]] for s in out)})
        print(f"{product['short']}: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
        if posthog_client:
            posthog_client.capture("stock_snapshot_published", properties={
                "product": product["short"], "store_count": len(out), "in_stock_count": counts.get("in", 0),
                "low_stock_count": counts.get("low", 0), "out_of_stock_count": counts.get("out", 0)})
    stock = {"updated": now, "stores": stores, "products": products}
    OUT.write_text(json.dumps(stock, separators=(",", ":")) + "\n")
    past = history.upgrade(previous_history(), PRODUCT)
    HISTORY.write_text(json.dumps(history.record(past, readings, datetime.now(timezone.utc)),
                                  separators=(",", ":")) + "\n")
    if posthog_logger:
        posthog_logger.info("stock snapshot published", extra={
            "event": "stock_snapshot_published", "product_count": len(products), "store_count": len(stores),
            "history_started": past is None})
    print(f"history: {'started' if past is None else 'added a reading'}")
    return stock


def main():
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--local", action="store_true", help="use your Chrome through Jev's Browser")
    local = args.parse_args().local
    load_env()
    posthog_client = get_posthog_client()
    posthog_logger = get_posthog_logger()
    write_config(os.environ.get("MAPBOX_TOKEN", ""))
    for attempt in (1, 2):
        driver = Jev() if local else Playwright()
        try:
            stock = poll(driver, posthog_client, posthog_logger)
            break
        except Exception as error:
            print(f"attempt {attempt}: {type(error).__name__}: {error}", file=sys.stderr)
        finally:
            driver.close()
    else:
        sys.exit("Stock not updated; public/stock.json keeps the last good reading.")
    # After the driver closes: Playwright allows one sync session per thread. A failed preview keeps the old one.
    try:
        og.render(og.first_product(stock), OG)
    except Exception as error:
        print(f"warning: link preview not updated: {type(error).__name__}: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
