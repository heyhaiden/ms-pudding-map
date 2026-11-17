"""Watch M&S's New In and As Seen On Social lists; write a GitHub issue body for new items that aren't bakery.

Nothing goes live from here: the issue is a checklist for a human to approve, and approved items are added to
data/products.json by hand. Every item seen is remembered in data/watch.json, so each one is raised once and
each product page is opened once.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from scripts import poll

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "watch.json"
ISSUE = ROOT / "watch-issue.md"
SITE = "https://www.marksandspencer.com"
LISTS = {"New In": "/food/l/new-in", "As Seen On Social": "/food/l/as-seen-on-social"}
IMAGE = "https://assets.digitalcontent.marksandspencer.app/image/upload/w_160,q_auto,f_auto/"
MAX_PAGES = 5
# outofpud is desserts only. Matched on the title; a savoury word wins ("Yorkshire Pudding Wrap", "Goat's Cheese
# Tarts"). Everything is still remembered in watch.json, so a future meals site can pick up the rest.
SWEET = re.compile(r"pudding|crumble|cookie|dough|cake|tart|pie|trifle|dessert|brownie|churro|custard|choc|caramel|"
                   r"toffee|panettone|stollen|yule|sundae|ice cream|mousse|profiterole|eclair|[ée]clair|roulade|"
                   r"pavlova|meringue|tiramisu|sponge|muffin|flapjack|fudge|biscuit|gateau|gâteau|torte|cr[eè]me|"
                   r"brûlée|brulee|cheesecake|blondie|millionaire|cinnamon|treacle|sticky|jam|sweet|mince|gingerbread|"
                   r"s.more|caterpillar|brandy butter|cream\b|peppermint|marshmallow|honeycomb|praline|malt ball|munch",
                   re.I)
SAVOURY = re.compile(r"yorkshire|onion|cheese(?!cake)|goat|pizza|pork|beef|chicken|steak|sausage|gravy|pigs in|"
                     r"turkey|ham\b|salmon|prawn|wrap|sandwich|soup|potato|stuffing|chutney|sweet potato|"
                     r"sweetcorn|sweet chilli|spices|scourer|sour cream|hand wash|shampoo", re.I)

# In-page fetches: same origin as the guest session, like the stock poll.
TEXT_JS = """async (url) => {
  const r = await fetch(url);
  if (!r.ok) return {error: url + ' ' + r.status};
  return {text: await r.text()};
}"""
BAKERY_JS = """async (url) => {
  const r = await fetch(url);
  if (!r.ok) return {error: url + ' ' + r.status};
  const t = await r.text();
  return {bakery: t.includes('"isISBProduct":true'), known: t.includes('"isISBProduct"')};
}"""


def listing(html):
    """Products and page count from a listing page's Next.js data."""
    found = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not found:
        raise RuntimeError("listing page has no __NEXT_DATA__")
    search = json.loads(found.group(1))["props"]["pageProps"]["viewModel"]["productSearch"]
    items = [{"id": p["id"], "title": p["title"].strip(), "url": SITE + p["seoUrl"].split("#")[0],
              "image": p.get("imageUrl") or "", "weight": p.get("weight") or ""}
             for group in search["productLists"].values() for p in group]
    return items, search["pagination"]["totalPages"]


def dessert(title):
    """True for a sweet thing by its name. Generous on purpose: a human approves every item anyway."""
    return bool(SWEET.search(title)) and not SAVOURY.search(title)


def fresh(found, seen, tracked):
    """Items not seen before and not already in products.json, in list order, one entry per product."""
    out = {}
    for item in found:
        if item["id"] in seen or item["id"] in tracked:
            continue
        if item["id"] in out:
            out[item["id"]]["lists"] = sorted(set(out[item["id"]]["lists"] + item["lists"]))
        else:
            out[item["id"]] = item
    return list(out.values())


def issue(items, owner):
    """Markdown checklist for the items to review, or None when there are none."""
    if not items:
        return None
    lines = [f"@{owner} {len(items)} new dessert{'s' if len(items) != 1 else ''} on M&S's lists (bakery left out).",
             "", "Tick the ones to put on the map, then ask Claude to add the ticked items. Unticked = denied;",
             "nothing here goes live on its own. Close the issue when done.", ""]
    for i in items:
        img = f'<img src="{IMAGE}{i["image"]}" width="80" align="top"> ' if i["image"] else ""
        note = " · bakery unknown" if i.get("bakery") is None else ""
        lines.append(f"- [ ] {img}[{i['title']}]({i['url']}) · {i['weight']} · {', '.join(i['lists'])}"
                     f"{note} · id `{i['id']}`")
    return "\n".join(lines) + "\n"


def collect(driver):
    found = []
    for name, path in LISTS.items():
        page, pages = 1, 1
        while page <= min(pages, MAX_PAGES):
            url = SITE + path + (f"?page={page}" if page > 1 else "")
            items, pages = listing(poll.checked(driver.run(TEXT_JS, url), name)["text"])
            found += [{**i, "lists": [name]} for i in items]
            page += 1
        print(f"{name}: {sum(name in i['lists'] for i in found)} items")
    return found


def main():
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--local", action="store_true", help="use your Chrome through Jev's Browser")
    args.add_argument("--owner", default="heyhaiden", help="GitHub login to mention in the issue")
    opts = args.parse_args()
    state = json.loads(SEEN.read_text()) if SEEN.exists() else {"seen": {}}
    tracked = {p["id"] for p in json.loads(poll.PRODUCTS.read_text()) if "id" in p}
    driver = poll.Jev() if opts.local else poll.Playwright()
    try:
        poll.open_page(driver)
        new = fresh(collect(driver), state["seen"], tracked)
        for item in new:
            item["dessert"] = dessert(item["title"])
            # Only desserts need the bakery check, so only their pages are opened.
            result = (driver.run(BAKERY_JS, item["url"]) or {}) if item["dessert"] else {}
            item["bakery"] = result["bakery"] if result.get("known") else None
    finally:
        driver.close()
    today = date.today().isoformat()
    for item in new:
        state["seen"][item["id"]] = {"title": item["title"], "dessert": item["dessert"], "bakery": item["bakery"],
                                     "lists": item["lists"], "first": today}
    SEEN.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    sweet = [i for i in new if i["dessert"]]
    review = [i for i in sweet if i["bakery"] is not True]
    print(f"{len(new)} new, {len(new) - len(sweet)} not desserts, {len(sweet) - len(review)} bakery, "
          f"{len(review)} to review")
    body = issue(review, opts.owner)
    if body:
        ISSUE.write_text(body)
    elif ISSUE.exists():
        ISSUE.unlink()


if __name__ == "__main__":
    sys.exit(main())
