from datetime import datetime, timedelta, timezone

from scripts.history import floor, record, upgrade

T0 = datetime(2026, 10, 27, 14, 47, 12, tzinfo=timezone.utc)


def reading(**statuses):
    return {"p": statuses}


def test_slots_start_on_the_half_hour():
    assert floor(T0) == datetime(2026, 10, 27, 14, 30, tzinfo=timezone.utc)


def test_first_poll_starts_a_history():
    h = record(None, reading(a="in", b="not_sold"), T0)
    assert h == {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "products": {"p": {"a": "I", "b": "N"}}}


def test_missed_polls_become_gaps():
    h = record(None, reading(a="in"), T0)
    h = record(h, reading(a="low"), T0 + timedelta(hours=1, minutes=30))
    assert h["products"]["p"]["a"] == "I--L"


def test_a_second_poll_in_the_same_slot_overwrites():
    h = record(None, reading(a="in"), T0)
    h = record(h, reading(a="out"), T0 + timedelta(minutes=5))
    assert h["products"]["p"]["a"] == "O"


def test_new_and_vanished_stores_stay_aligned():
    h = record(None, reading(a="in"), T0)
    h = record(h, reading(b="out"), T0 + timedelta(minutes=30))
    assert h["products"]["p"] == {"a": "I-", "b": "-O"}


def test_a_product_added_later_starts_with_gaps():
    h = record(None, reading(a="in"), T0)
    h = record(h, {"p": {"a": "in"}, "q": {"a": "low"}}, T0 + timedelta(minutes=30))
    assert h["products"] == {"p": {"a": "II"}, "q": {"a": "-L"}}


def test_old_slots_are_dropped():
    h = record(None, reading(a="in", gone="out"), T0)
    h = record(h, reading(a="low"), T0 + timedelta(days=1, minutes=30), keep_days=1)
    # Second poll lands in the 15:00 slot a day later; the 48 kept slots begin at 15:30 the day before.
    assert h["start"] == "2026-10-27T15:30:00+00:00"
    assert h["products"]["p"] == {"a": "-" * 47 + "L"}


def test_single_product_history_is_upgraded():
    old = {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "stores": {"a": "IO"}}
    new = {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "products": {"p": {"a": "IO"}}}
    assert upgrade(old, "p") == new
    assert upgrade(None, "p") is None
