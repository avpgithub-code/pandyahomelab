"""Tests for application-logic/quality/gates."""
from application_logic.quality.gates import evaluate, failed_threshold


def test_failed_threshold_is_max_of_abs_and_fraction():
    assert failed_threshold(100, 5, 0.005) == 5
    assert failed_threshold(20000, 5, 0.005) == 100


def test_pass_and_fail_on_parse_failures():
    assert evaluate("recent", 100, 5, 0, 0) == []
    assert evaluate("recent", 100, 6, 0, 0)


def test_active_drop_only_in_full_mode():
    assert evaluate("full", 1000, 0, 1000, 980) == []
    assert evaluate("full", 1000, 0, 1000, 979)
    assert evaluate("recent", 10, 0, 1000, 10) == []


def test_empty_full_zip_fails():
    assert evaluate("full", 0, 0, 0, 0)
    assert evaluate("recent", 0, 0, 0, 0) == []
