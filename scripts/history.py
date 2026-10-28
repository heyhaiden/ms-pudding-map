"""Stock over time, one letter per store per 30-minute slot, for each product. No network.

  {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "products": {"61273052": {"291": "IILLO-O", ...}}}

Slot i covers start + i * 30 min. '-' means no reading (a failed or skipped poll). Only the last KEEP_DAYS are kept.
"""

from datetime import datetime, timedelta, timezone

SLOT = timedelta(minutes=30)
KEEP_DAYS = 30
CODE = {"in": "I", "low": "L", "out": "O", "not_sold": "N", "unknown": "U"}
GAP = "-"


def floor(moment):
    """Round down to the start of its 30-minute slot, in UTC."""
    moment = moment.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return moment - timedelta(minutes=moment.minute % 30)


def upgrade(history, product):
    """The first history only tracked one product, under "stores"; file it under that product."""
    if history and "stores" in history:
        history = {"start": history["start"], "slot_minutes": history["slot_minutes"],
                   "products": {product: history["stores"]}}
    return history


def record(history, readings, now, keep_days=KEEP_DAYS):
    """Add this poll ({product: {store: status}}) to `history`, or start one. A second poll in a slot overwrites it."""
    slot_start = floor(now)
    if not history:
        history = {"start": slot_start.isoformat(), "slot_minutes": 30, "products": {}}
    start = datetime.fromisoformat(history["start"])
    index = (slot_start - start) // SLOT
    products = history["products"]
    for product, statuses in readings.items():
        lines = products.setdefault(product, {})
        for store_id, status in statuses.items():
            line = lines.get(store_id, "").ljust(index, GAP)
            lines[store_id] = line[:index] + CODE[status] + line[index + 1:]
    # Every line ends at this slot, so products and stores missing from this poll stay aligned.
    for lines in products.values():
        for store_id, line in lines.items():
            lines[store_id] = line.ljust(index + 1, GAP)
    drop = index + 1 - keep_days * 48
    if drop > 0:
        history["start"] = (start + drop * SLOT).isoformat()
        history["products"] = {product: {k: v[drop:] for k, v in lines.items() if v[drop:].strip(GAP)}
                               for product, lines in products.items()}
    return history
