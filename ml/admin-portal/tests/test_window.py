"""Pure tests for the calendar-day reporting window."""
from datetime import date

from app.window import fill_days, win_param, window_label, window_start


def test_window_counts_today_as_one_of_the_days():
    today = date(2026, 11, 6)
    assert window_start(30, today) == date(2026, 10, 8)
    assert (today - window_start(30, today)).days + 1 == 30
    assert window_start(1, today) == today
    assert win_param(30) == "29 days"
    assert win_param(1) == "0 days"


def test_window_label():
    assert window_label(date(2026, 10, 8), date(2026, 11, 6)) == "Oct 8 – Nov 6, 2026"
    assert window_label(date(2026, 12, 28), date(2027, 1, 3)) == "Dec 28, 2026 – Jan 3, 2027"


def test_fill_days_adds_zero_days_oldest_first():
    rows = [
        {"day": date(2026, 10, 5), "visitors": 2, "page_views": 5},
        {"day": date(2026, 10, 2), "visitors": 5, "page_views": None},
    ]
    out = fill_days(rows, date(2026, 10, 2), date(2026, 10, 5), ["visitors", "page_views"])
    assert [r["day"].day for r in out] == [2, 3, 4, 5]
    assert [r["visitors"] for r in out] == [5, 0, 0, 2]
    assert [r["page_views"] for r in out] == [0, 0, 0, 5]


def test_fill_days_with_no_data_is_empty():
    assert fill_days([], None, date(2026, 10, 5), ["visitors"]) == []
