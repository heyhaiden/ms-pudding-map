"""Stock over time, one letter per store per 30-minute slot. No network.

  {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "stores": {"291": "IILLO-O", ...}}

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


def record(history, stock, now, keep_days=KEEP_DAYS):
    """Add this poll's statuses to `history` (or start one) and return it. A second poll in a slot overwrites it."""
    slot_start = floor(now)
    if not history:
        history = {"start": slot_start.isoformat(), "slot_minutes": 30, "stores": {}}
    start = datetime.fromisoformat(history["start"])
    index = (slot_start - start) // SLOT
    stores = history["stores"]
    for store in stock["stores"]:
        line = stores.get(store["id"], "").ljust(index, GAP)
        stores[store["id"]] = line[:index] + CODE[store["status"]] + line[index + 1:]
    # Stores that vanished from the list this time get a gap, so every line ends at the same slot.
    for store_id, line in stores.items():
        stores[store_id] = line.ljust(index + 1, GAP)
    drop = index + 1 - keep_days * 48
    if drop > 0:
        history["start"] = (start + drop * SLOT).isoformat()
        history["stores"] = {k: v[drop:] for k, v in stores.items() if v[drop:].strip(GAP)}
    return history
