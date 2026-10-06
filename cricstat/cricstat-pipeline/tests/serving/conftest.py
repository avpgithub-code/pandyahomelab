"""Helpers for build-step tests: turn F4 fixture cases into Cricsheet match files, ingest them
into a tmp raw store, and run the real serving-DB build over them (cricstat/sql is the real one).
"""
import json
import sqlite3
from pathlib import Path

import pytest

from db_logic.repository.raw_store import RawStore, connect, migrate
from db_logic.transforms.match_record import build_record

CRICSTAT = Path(__file__).resolve().parents[3]
SQL_DIR = CRICSTAT / "sql"
CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "f4_metric_cases.json").read_text()
)

# Fixture "format" → Cricsheet (match_type, team_type, balls_per_over, overs).
FORMATS = {
    "ODI": ("ODI", "international", 6, 50),
    "T20": ("T20", "international", 6, 20),
    "HUNDRED": ("T20", "club", 5, 20),
    "TEST": ("Test", "international", 6, None),
}
NOW = "2026-10-06T00:00:00Z"


def _delivery(d):
    """Fixture delivery → Cricsheet delivery (runs.batter/extras/total, runs.non_boundary)."""
    extras = dict(d.get("extras", {}))
    rb = d.get("runs_batter", 0)
    ex = sum(extras.values())
    out = {"batter": d["batter"], "bowler": d["bowler"], "non_striker": d["non_striker"],
           "runs": {"batter": rb, "extras": ex, "total": rb + ex}}
    if d.get("non_boundary"):
        out["runs"]["non_boundary"] = True
    if extras:
        out["extras"] = extras
    if d.get("wickets"):
        out["wickets"] = d["wickets"]
    return out


def _names(innings, side):
    """Every name that plays for `side` ('bat' or 'bowl') in these innings."""
    names = []
    for inn in innings:
        for ov in inn["overs"]:
            for d in ov["deliveries"]:
                if side == "bat":
                    cand = [d["batter"], d["non_striker"]]
                    cand += [w["player_out"] for w in d.get("wickets", [])]
                else:
                    cand = [d["bowler"]]
                    cand += [f["name"] for w in d.get("wickets", []) for f in w.get("fielders", [])
                             if not f.get("substitute")]
                names += [n for n in cand if n not in names]
    return names


def case_doc(case, start_date="2026-01-01"):
    """A Cricsheet-shaped match document for one F4 delivery case."""
    mt, tt, bpo, overs = FORMATS[case["format"]]
    if "innings" in case:
        innings = case["innings"]
    else:
        innings = [{"team": "Home", "overs": case["overs"]}]
    home = _names([i for i in innings if i["team"] == "Home"], "bat")
    home_bowl = _names([i for i in innings if i["team"] == "Away"], "bowl")
    home += [n for n in home_bowl if n not in home]
    away = _names([i for i in innings if i["team"] == "Away"], "bat")
    away_bowl = _names([i for i in innings if i["team"] == "Home"], "bowl")
    away += [n for n in away_bowl if n not in away]
    home, away = home or ["H0"], away or ["A0"]
    people = sorted(set(home + away + [
        f["name"] for i in innings for ov in i["overs"] for d in ov["deliveries"]
        for w in d.get("wickets", []) for f in w.get("fielders", [])]))
    info = {
        "balls_per_over": bpo, "city": "Testville", "dates": [start_date], "gender": "male",
        "match_type": mt, "team_type": tt, "teams": ["Home", "Away"], "season": start_date[:4],
        "venue": "Test Ground",
        "outcome": case.get("outcome", {"winner": "Home", "by": {"runs": 1}}),
        "players": {"Home": home, "Away": away},
        "registry": {"people": {n: pid(n) for n in people}},
        "toss": {"winner": "Home", "decision": "bat"},
    }
    if overs:
        info["overs"] = overs
    if tt == "club":
        info["event"] = {"name": "The Hundred Men's Competition"}
    out_innings = []
    for inn in innings:
        o = {"team": inn["team"], "overs": [
            {"over": ov["over"], "deliveries": [_delivery(d) for d in ov["deliveries"]]}
            for ov in inn["overs"]]}
        if inn.get("super_over"):
            o["super_over"] = True
        out_innings.append(o)
    return {"meta": {"data_version": "1.2.0", "created": "2026-01-02", "revision": 1},
            "info": info, "innings": out_innings}


def pid(name):
    """Deterministic 8-hex Cricsheet-style id for a test player name."""
    return name.encode().hex()[:8].ljust(8, "0")


def write_raw(db_path, docs):
    """docs: {match_id: doc} → a migrated raw store holding them."""
    conn = connect(str(db_path))
    migrate(conn, NOW)
    store = RawStore(conn)
    store.begin()
    for mid, doc in docs.items():
        store.insert_match(build_record(mid, json.dumps(doc, indent=1).encode()), NOW, 1)
    store.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def build_env(tmp_path):
    """Returns build(docs, mode='full') → open read-only connection to the swapped serving DB."""
    from application_logic.services import build_service

    raw = tmp_path / "db" / "raw.sqlite"
    serving = tmp_path / "db" / "cricstat.sqlite"
    venue_map = tmp_path / "venue_map.csv"
    venue_map.write_text("venue,city,canonical_venue,canonical_city,country,basis,checked\n"
                         "Test Ground,Testville,Test Ground,Testville,Home,fixture,\n")
    conns = []

    def _build(docs, mode="full", add=False):
        if not add:
            write_raw(raw, docs)
        else:
            conn = connect(str(raw))
            store = RawStore(conn)
            store.begin()
            for mid, doc in docs.items():
                rec = build_record(mid, json.dumps(doc, indent=1).encode())
                if store.get_match(mid):
                    store.update_match(rec, NOW, 2)
                else:
                    store.insert_match(rec, NOW, 2)
            store.commit()
            conn.close()
        summary = build_service.build(str(raw), str(serving), str(SQL_DIR), mode=mode,
                                      venue_map_path=str(venue_map))
        c = sqlite3.connect("file:%s?mode=ro" % serving, uri=True)
        conns.append(c)
        return c, summary

    yield _build
    for c in conns:
        c.close()
