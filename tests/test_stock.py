import json
from pathlib import Path

from scripts.stock import join, status, stores_from

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_codes_match_the_ms_site():
    assert [status(c) for c in ("H", "M", "L", "O", None, "X")] == ["in", "in", "low", "out", "unknown", "unknown"]


def test_store_list_keeps_food_stores_once():
    stores = stores_from(load("locations.json"))
    assert [s["id"] for s in stores] == ["291", "1025", "1633", "1666", "2972", "4420"]
    assert stores[0] == {"id": "291", "name": "Marble Arch", "type": "Full Line", "lat": 51.5142, "lng": -0.1568}


def test_join_gives_every_store_a_status():
    stores = stores_from(load("locations.json"))
    ranged = [s["storeId"] for s in load("range.json")["stores"]]
    indicators = load("stock.json")["data"]["stock"]["getFoodStockLevelIndicator"]["indicator"]
    out, counts, missing = join(stores, ranged, indicators)
    assert {s["id"]: s["status"] for s in out} == {"291": "out", "1025": "in", "1633": "low", "1666": "in",
                                                   "2972": "not_sold", "4420": "not_sold"}
    assert counts == {"in": 2, "low": 1, "out": 1, "unknown": 0, "not_sold": 2}
    assert missing == ["9999"]


def test_ranged_store_without_a_reading_is_unknown():
    out, counts, _ = join([{"id": "1", "name": "A", "type": None, "lat": 0, "lng": 0}], ["1"], [])
    assert out[0]["status"] == "unknown" and counts["unknown"] == 1


def test_store_list_keeps_only_stores_inside_the_box():
    london = {"south": 51.22, "west": -0.62, "north": 51.76, "east": 0.36}
    assert [s["id"] for s in stores_from(load("locations.json"), london)] == ["291", "1025", "1633"]
