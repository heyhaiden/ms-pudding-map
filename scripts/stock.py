"""Pure stock logic: M&S stock codes become map statuses, joined onto the store list. No network."""

# From M&S's own _app.js: H and M both show "In stock", L "Low stock", O "Out of stock".
STATUS = {"H": "in", "M": "in", "L": "low", "O": "out"}
# Northern Ireland stores sell food but only carry FOODSCATALOGUE.
FOOD = {"FOOD", "FOODSCATALOGUE"}
ORDER = ("in", "low", "out", "unknown", "not_sold")


def status(code):
    """'M' -> 'in'. A ranged store with no or unrecognised code -> 'unknown'."""
    return STATUS.get(code, "unknown")


def inside(coords, box):
    return box["south"] <= coords["latitude"] <= box["north"] and box["west"] <= coords["longitude"] <= box["east"]


def stores_from(locations, box=None):
    """GraphQL locations from every seed town -> one food store per id inside `box`, sorted by id."""
    stores = {}
    for loc in locations:
        coords = loc.get("coordinates")
        if not FOOD & set(loc.get("capabilities") or []) or not coords or (box and not inside(coords, box)):
            continue
        stores[loc["id"]] = {"id": loc["id"], "name": loc["name"].title(), "type": (loc.get("type") or {}).get("name"),
                             "lat": loc["coordinates"]["latitude"], "lng": loc["coordinates"]["longitude"]}
    return sorted(stores.values(), key=lambda s: int(s["id"]) if s["id"].isdigit() else s["id"])


def join(stores, ranged, indicators):
    """Every store with its status, the count per status, and ranged ids missing from the store list."""
    levels = {i["locationId"]: i["stockLevelIndicator"] for i in indicators}
    ranged = set(ranged)
    out = [{**s, "status": status(levels.get(s["id"])) if s["id"] in ranged else "not_sold"} for s in stores]
    counts = {name: 0 for name in ORDER}
    for s in out:
        counts[s["status"]] += 1
    missing = sorted(ranged - {s["id"] for s in stores})
    return out, counts, missing
