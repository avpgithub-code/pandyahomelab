"""Build modes and the swap: incremental no-op / change / removal, escalation to full, and a
failed quality check that must leave the live serving DB untouched."""
import copy
import os
import sqlite3

import pytest

from application_logic.services import build_service
from db_logic.repository.raw_store import RawStore, connect
from shared.exceptions import DataQualityError
from tests.serving.conftest import CASES, case_doc

C1 = next(c for c in CASES["delivery_cases"] if c["id"].startswith("C1_"))
C9 = next(c for c in CASES["delivery_cases"] if c["id"].startswith("C9_"))


def _one(conn, sql, args=()):
    return conn.execute(sql, args).fetchone()[0]


def test_incremental_without_changes_keeps_the_live_db(build_env, tmp_path):
    conn, first = build_env({"1": case_doc(C1)}, mode="incremental")
    assert first["mode"] == "build-full" and first["escalated"] == "no live serving DB"
    serving = tmp_path / "db" / "cricstat.sqlite"
    before = os.stat(serving).st_mtime_ns
    _, again = build_env({}, mode="incremental", add=True)
    assert again["status"] == "unchanged" and again["build_id"] == first["build_id"]
    assert os.stat(serving).st_mtime_ns == before


def test_incremental_rebuilds_only_changed_matches(build_env):
    build_env({"1": case_doc(C1), "2": case_doc(C9, start_date="2026-01-02")})
    changed = copy.deepcopy(C9)
    changed["overs"][0]["deliveries"][0]["runs_batter"] = 6
    changed["overs"][0]["deliveries"][0].pop("non_boundary")
    conn, s = build_env({"2": case_doc(changed, start_date="2026-01-02")}, mode="incremental",
                        add=True)
    assert s["mode"] == "build-incremental" and s["changed_matches"] == 1
    assert s["build_id"] == 2
    assert _one(conn, "SELECT COUNT(*) FROM matches") == 2
    assert _one(conn, "SELECT total_runs FROM innings JOIN matches USING (match_key)"
                      " WHERE match_id = '2'") == 11
    assert _one(conn, "SELECT SUM(sixes) FROM player_career WHERE scope = 'ODI'") == 1
    assert [r[0] for r in conn.execute("SELECT status FROM build_info ORDER BY build_id")] == \
        ["success", "success"]


def test_incremental_drops_removed_matches(build_env, tmp_path):
    build_env({"1": case_doc(C1), "2": case_doc(C9, start_date="2026-01-02")})
    raw = connect(str(tmp_path / "db" / "raw.sqlite"))
    raw.execute("UPDATE matches_raw SET removed_at = 'x' WHERE match_id = '2'")
    raw.close()
    conn, s = build_env({}, mode="incremental", add=True)
    assert s["removed_matches"] == 1
    assert [r[0] for r in conn.execute("SELECT match_id FROM matches")] == ["1"]
    assert _one(conn, "SELECT COUNT(*) FROM deliveries d JOIN matches m USING (match_key)") == \
        _one(conn, "SELECT COUNT(*) FROM deliveries")


def test_rule_change_escalates_to_full(build_env, tmp_path):
    build_env({"1": case_doc(C1)})
    serving = str(tmp_path / "db" / "cricstat.sqlite")
    c = sqlite3.connect(serving)
    c.execute("UPDATE build_info SET notes = json_set(notes, '$.rules_sha', 'old')")
    c.commit()
    c.close()
    conn, s = build_env({}, mode="incremental", add=True)
    assert s["mode"] == "build-full" and s["escalated"] == "rules or transform code changed"
    assert _one(conn, "SELECT COUNT(*) FROM build_info") == 2      # history carried over


def test_failed_check_keeps_live_db_and_saves_failed_file(build_env, tmp_path):
    build_env({"1": case_doc(C1)})
    serving = tmp_path / "db" / "cricstat.sqlite"
    before = os.stat(serving).st_mtime_ns
    bad = case_doc(C9, start_date="2026-01-02")
    del bad["info"]["registry"]["people"]["A"]          # an unresolvable batter
    with pytest.raises(DataQualityError) as err:
        build_env({"2": bad}, mode="incremental", add=True)
    assert "no registry entry" in str(err.value)
    assert os.stat(serving).st_mtime_ns == before
    assert (tmp_path / "db" / "cricstat.sqlite.failed").exists()
    assert not (tmp_path / "db" / "cricstat.sqlite.new").exists()
    assert err.value.summary["unresolved_sample"] == ["2: A"]


def test_unmapped_format_fails_the_build(build_env):
    doc = case_doc(C1)
    doc["info"]["balls_per_over"] = 8
    with pytest.raises(DataQualityError) as err:
        build_env({"1": doc})
    assert "unmapped formats" in str(err.value)
    assert "unmapped format (ODI, international, 8)" in err.value.summary["problems_sample"][0]


def test_crash_removes_the_half_built_file(build_env, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(build_service.serving_store, "build_marts", boom)
    with pytest.raises(RuntimeError):
        build_env({"1": case_doc(C1)})
    assert not (tmp_path / "db" / "cricstat.sqlite.new").exists()
    assert not (tmp_path / "db" / "cricstat.sqlite").exists()


def test_register_names_and_ids_reach_players(build_env, tmp_path):
    raw = tmp_path / "db" / "raw.sqlite"
    build_env({"1": case_doc(C1)})
    c = connect(str(raw))
    store = RawStore(c)
    store.begin()
    store.replace_register(
        [("41000000", "A Batter", "A Batter (2)", '{"cricinfo": ["11", "12"]}')],
        [("41000000", "Alpha Batter")])
    store.commit()
    store.start_run("register", "test", "2026-10-06T00:00:00Z")
    c.execute("UPDATE ingest_runs SET status = 'success' WHERE mode = 'register'")
    c.close()
    conn, s = build_env({}, mode="incremental", add=True)
    assert s["status"] == "success"           # register run changed inputs_sha → not a no-op
    assert _one(conn, "SELECT name FROM players WHERE player_id = '41000000'") == "A Batter"
    ids = [r[0] for r in conn.execute(
        "SELECT external_id FROM player_external_ids JOIN players USING (player_key)"
        " WHERE player_id = '41000000' AND source = 'cricinfo' ORDER BY external_id")]
    assert ids == ["11", "12"]
    names = {r[0] for r in conn.execute(
        "SELECT n.name FROM player_names n JOIN players USING (player_key)"
        " WHERE player_id = '41000000'")}
    assert {"A Batter", "A Batter (2)", "Alpha Batter", "Batter"} <= names


def test_one_id_in_both_genders_gets_one_career_row_and_a_warning(build_env):
    women = case_doc(C9, start_date="2026-01-02")
    women["info"]["gender"] = "female"
    conn, s = build_env({"1": case_doc(C1), "2": case_doc(C9, start_date="2026-01-03"),
                         "3": women})
    assert s["status"] == "success"
    assert any("both men's and women's" in w for w in s["warnings"])
    assert _one(conn, "SELECT COUNT(*) FROM player_career c JOIN players p USING (player_key)"
                      " WHERE p.player_id = '41000000' AND c.scope = 'ODI'") == 1
    assert _one(conn, "SELECT gender FROM player_career c JOIN players p USING (player_key)"
                      " WHERE p.player_id = '41000000' AND c.scope = 'ODI'") == "male"


def test_enrichment_reaches_player_bio(build_env, tmp_path):
    """An `enrich` run alone makes the next incremental build re-apply player_bio (P0.5)."""
    raw = tmp_path / "db" / "raw.sqlite"
    build_env({"1": case_doc(C1)})
    adult, teen = _one_pair(build_env, raw)
    c = connect(str(raw))
    store = RawStore(c)
    store.begin()
    store.upsert_wikidata([
        {"cricinfo_id": "11", "qid": "Q1", "label_en": "Alpha Batter", "image_file": "a.jpg",
         "date_of_birth": "1990-01-02", "birthplace": "Delhi", "country_for_sport": "India"},
        {"cricinfo_id": "22", "qid": "Q2", "label_en": "Young Teen", "image_file": "t.jpg",
         "date_of_birth": "2015-05-05", "birthplace": "Pune"}], "2026-10-07T00:00:00Z")
    for name in ("a.jpg", "t.jpg"):
        store.upsert_image(name, {"status": "ok", "licence": "CC BY-SA 4.0", "author": "Jane Doe",
                                  "thumb_path": name, "width": 320, "height": 400,
                                  "description_url": "https://commons.wikimedia.org/wiki/F"},
                           "2026-10-07T00:00:00Z")
    store.commit()
    store.start_run("enrich", "test", "2026-10-07T00:00:00Z")
    c.execute("UPDATE ingest_runs SET status = 'success' WHERE mode = 'enrich'")
    c.close()
    conn, s = build_env({}, mode="incremental", add=True)
    assert s["status"] == "success"              # enrich run changed inputs_sha → not a no-op
    assert s["bio"]["bio"] == 2 and s["bio"]["photos"] == 1 and s["bio"]["minors"] == 1
    row = conn.execute("SELECT b.full_name, b.date_of_birth, b.birthplace, b.photo_file,"
                       " b.photo_author FROM player_bio b JOIN players p USING (player_key)"
                       " WHERE p.player_id = ?", (adult,)).fetchone()
    assert row == ("Alpha Batter", "1990-01-02", "Delhi", "a.jpg", "Jane Doe")
    row = conn.execute("SELECT b.full_name, b.date_of_birth, b.birthplace, b.photo_file"
                       " FROM player_bio b JOIN players p USING (player_key)"
                       " WHERE p.player_id = ?", (teen,)).fetchone()
    assert row == ("Young Teen", None, None, None)          # under 18: no birth details, no photo
    names = {r[0] for r in conn.execute("SELECT name FROM player_names WHERE source = 'wikidata'")}
    assert names == {"Alpha Batter", "Young Teen"}            # Wikidata names are searchable


def _one_pair(build_env, raw):
    """Register two players of fixture match 1 with cricinfo ids 11 and 22."""
    conn = sqlite3.connect("file:%s?mode=ro" % str(raw).replace("raw.sqlite", "cricstat.sqlite"),
                           uri=True)
    ids = [r[0] for r in conn.execute("SELECT player_id, name FROM players ORDER BY player_id"
                                      " LIMIT 2")]
    names = dict(conn.execute("SELECT player_id, name FROM players"))
    conn.close()
    c = connect(str(raw))
    store = RawStore(c)
    store.begin()
    store.replace_register([(ids[0], names[ids[0]], names[ids[0]], '{"cricinfo": ["11"]}'),
                            (ids[1], names[ids[1]], names[ids[1]], '{"cricinfo": ["22"]}')], [])
    store.commit()
    c.close()
    return ids
