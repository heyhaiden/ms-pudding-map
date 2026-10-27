from datetime import datetime, timedelta, timezone

from scripts.history import floor, record

T0 = datetime(2026, 10, 27, 14, 47, 12, tzinfo=timezone.utc)


def stock(**statuses):
    return {"stores": [{"id": k, "status": v} for k, v in statuses.items()]}


def test_slots_start_on_the_half_hour():
    assert floor(T0) == datetime(2026, 10, 27, 14, 30, tzinfo=timezone.utc)


def test_first_poll_starts_a_history():
    h = record(None, stock(a="in", b="not_sold"), T0)
    assert h == {"start": "2026-10-27T14:30:00+00:00", "slot_minutes": 30, "stores": {"a": "I", "b": "N"}}


def test_missed_polls_become_gaps():
    h = record(None, stock(a="in"), T0)
    h = record(h, stock(a="low"), T0 + timedelta(hours=1, minutes=30))
    assert h["stores"]["a"] == "I--L"


def test_a_second_poll_in_the_same_slot_overwrites():
    h = record(None, stock(a="in"), T0)
    h = record(h, stock(a="out"), T0 + timedelta(minutes=5))
    assert h["stores"]["a"] == "O"


def test_new_and_vanished_stores_stay_aligned():
    h = record(None, stock(a="in"), T0)
    h = record(h, stock(b="out"), T0 + timedelta(minutes=30))
    assert h["stores"] == {"a": "I-", "b": "-O"}


def test_old_slots_are_dropped():
    h = record(None, stock(a="in", gone="out"), T0)
    h = record(h, stock(a="low"), T0 + timedelta(days=1, minutes=30), keep_days=1)
    # Second poll lands in the 15:00 slot a day later; the 48 kept slots begin at 15:30 the day before.
    assert h["start"] == "2026-10-27T15:30:00+00:00"
    assert h["stores"] == {"a": "-" * 47 + "L"}
