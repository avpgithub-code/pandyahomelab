"""Pytest configuration: puts the service root on sys.path so the symlinked db_logic /
application_logic / presentation_logic packages resolve, and builds tiny serving DBs and supplement
folders in tmp_path. No test touches the network or the real data/ folder."""
import csv
import os
import shutil
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CRICSTAT = os.path.dirname(ROOT)
SCHEMA = os.path.join(CRICSTAT, "sql", "serving_schema.sql")

from db_logic.repository import supplement_store  # noqa: E402

TEAMS = ["India", "Australia", "Pakistan", "Ireland", "Scotland", "Asia XI", "Africa XI"]


def make_serving_db(path, matches):
    """matches: (match_id, date, team1, team2, venue_country, result, winner[, match_type])."""
    conn = sqlite3.connect(path)
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    keys = {}
    for t in TEAMS:
        keys[t] = conn.execute("INSERT INTO teams (name, gender, team_type) VALUES (?, 'male',"
                               " 'international')", (t,)).lastrowid
    venues = {}
    conn.execute("INSERT INTO build_info (build_id, built_at, mode, data_as_of, status)"
                 " VALUES (1, '2026-10-08', 'full', '2026-10-07', 'ok')")
    for m in matches:
        mid, date, t1, t2, country, result, winner = m[:7]
        mtype = m[7] if len(m) > 7 else "ODI"
        for t in (t1, t2):
            if t not in keys:
                keys[t] = conn.execute("INSERT INTO teams (name, gender, team_type) VALUES"
                                       " (?, 'male', 'international')", (t,)).lastrowid
        if country not in venues:
            venues[country] = conn.execute("INSERT INTO venues (name, city, country) VALUES"
                                           " (?, ?, ?)", ("Ground " + country, "City " + country,
                                                          country)).lastrowid
        mk = conn.execute(
            "INSERT INTO matches (match_id, match_type, team_type, gender, balls_per_over,"
            " format_key, season, start_date, end_date, n_days, venue_key, team1_key, team2_key,"
            " result, winner_key, decided_by, has_deliveries, source_sha256)"
            " VALUES (?, ?, 'international', 'male', 6, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 'play', 1,"
            " 'sha')",
            (mid, mtype, "ODI" if mtype == "ODI" else "OD_INTL_OTHER", date[:4], date, date,
             venues[country], keys[t1], keys[t2], result, keys.get(winner))).lastrowid
        for a, b in ((t1, t2), (t2, t1)):
            ha = "home" if country == a else "away" if country == b else "neutral"
            outcome = "no_result" if result == "no_result" else "tied" if result == "tie" else \
                ("won" if winner == a else "lost")
            conn.execute("INSERT INTO team_results (match_key, team_key, opponent_key, format_key,"
                         " gender, start_date, venue_key, outcome, home_away) VALUES"
                         " (?, ?, ?, 'ODI', 'male', ?, ?, ?, ?)",
                         (mk, keys[a], keys[b], date, venues[country], outcome, ha))
    conn.commit()
    conn.close()
    return path


def supp_row(**kw):
    row = {
        "match_key": "900001", "match_id": "900001", "odi_no": "4000", "start_date": "2018-03-01",
        "team1": "Afghanistan", "team2": "Ireland", "venue": "Ground, Sharjah", "city": "Sharjah",
        "venue_country": "United Arab Emirates", "result": "win", "winner": "Afghanistan",
        "method": "", "decided_by": "play", "has_play": "1", "margin": "5 wickets",
        "source_page": "International cricket in 2017–18", "source_revid": "1",
        "check_article": "Afghan cricket team in the UAE", "check_status": "confirmed", "note": "",
    }
    row.update(kw)
    if "match_id" in kw and "match_key" not in kw:
        row["match_key"] = kw["match_id"] or "odi-%s" % row["odi_no"]
    return row


def totals_for(rows):
    from application_logic.quality.supplement_checks import record_by_opponent
    rec = record_by_opponent(rows)
    out = [dict(zip(("opponent", "matches", "won", "lost", "tied", "no_result"), (k,) + v))
           for k, v in rec.items()]
    out.append(dict(zip(("opponent", "matches", "won", "lost", "tied", "no_result"),
                        ("TOTAL",) + tuple(sum(v[i] for v in rec.values()) for i in range(5)))))
    for r in out:
        r.update(source_page="Afghanistan national cricket team", source_revid="1", as_of="test")
    return out


@pytest.fixture
def venue_map(tmp_path):
    path = tmp_path / "venue_map.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["venue", "city", "canonical_venue", "canonical_city", "country"])
        for country, city in (("India", "Mumbai"), ("Australia", "Perth"), ("Ireland", "Dublin"),
                              ("United Arab Emirates", "Sharjah"), ("Pakistan", "Lahore"),
                              ("Scotland", "Edinburgh"), ("England", "London")):
            w.writerow(["Ground", city, "Ground", city, country])
    return str(path)


@pytest.fixture
def cfg(tmp_path, venue_map, monkeypatch):
    """A config pointing at tmp_path: empty supplement folder (with the real crosswalks)."""
    supp = tmp_path / "supplement"
    supp.mkdir()
    for name in (supplement_store.TEAM_CODES_FILE, supplement_store.VENUES_FILE):
        shutil.copy(os.path.join(ROOT, "supplement", name), str(supp / name))
    monkeypatch.setenv("CRICSTAT_HOME", str(tmp_path))
    monkeypatch.setenv("CRICSTAT_SERVING_DB", str(tmp_path / "cricstat.sqlite"))
    monkeypatch.setenv("CRICSTAT_VENUE_MAP", venue_map)
    monkeypatch.setenv("CRICSTAT_SUPPLEMENT_DIR", str(supp))
    monkeypatch.setenv("CRICSTAT_LOG_DIR", str(tmp_path / "logs"))
    from shared.config import get_config
    return get_config(reload=True)
