"""Internal admin endpoints (P0.3b): jobs, overview, golden figures; and the golden rules, which
must match cricstat-pipeline's `golden` command."""
from datetime import datetime, timezone

import pytest

from application_logic.services import admin_service, golden
from tests.conftest import pid


def data(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()["data"]


def test_jobs_reads_runs_and_schedules(client):
    d = data(client, "/v1/admin/jobs")
    jobs = {j["key"]: j for j in d["jobs"]}
    assert set(jobs) == {"cd_pull", "daily", "register", "monthly"}
    assert jobs["monthly"]["last_run"]["status"] == "success"      # the fixture's `full` ingest
    assert jobs["monthly"]["last_run"]["build"]["build_id"] >= 1
    assert jobs["register"]["last_run"] is None and jobs["register"]["overdue"]
    assert d["builds"][0]["notes"]["rules_sha"]


def test_next_run_uses_nas_local_time():
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)          # 07:00 at UTC-5
    daily = next(j for j in admin_service.JOBS if j["key"] == "daily")
    weekly = next(j for j in admin_service.JOBS if j["key"] == "register")
    monthly = next(j for j in admin_service.JOBS if j["key"] == "monthly")
    assert admin_service.next_run(daily, now, -5) == datetime(2026, 10, 7, 10, 30,
                                                               tzinfo=timezone.utc)
    assert admin_service.next_run(weekly, now, -5) == datetime(2026, 10, 11, 11, 0,
                                                                tzinfo=timezone.utc)
    assert admin_service.next_run(monthly, now, -5) == datetime(2026, 11, 1, 9, 0,
                                                                 tzinfo=timezone.utc)


def test_cd_log_runs_are_grouped(tmp_path):
    from db_logic.repository import ops_repo

    (tmp_path / "cd-20261006.log").write_text(
        "2026-10-06T10:15:01Z ok cricstat-pipeline up to date (abc)\n"
        "2026-10-06T10:15:20Z FAIL cricstat-api: cannot pull x\n"
        "2026-10-06T17:52:21Z deployed cricstat-api db3 from y (previous none)\n")
    runs = ops_repo.cd_pull_runs(str(tmp_path))
    assert [r["failed"] for r in runs] == [False, True] and len(runs[1]["lines"]) == 2


def test_overview(client):
    d = data(client, "/v1/admin/overview")
    assert d["counts"]["matches"] >= 7 and d["files"]["serving_db"] > 0
    assert {"year", "format_key", "gender", "matches"} <= set(d["matches_per_year"][0])


def test_golden_figures(client, home, monkeypatch):
    sel = home / "docs" / "validation" / "golden-selection.csv"
    sel.parent.mkdir(parents=True, exist_ok=True)
    sel.write_text("kind,id,name,gender,scopes,role,why\n"
                   "player,%s,V Kohli,male,ODI;T20I,bat,test\n"
                   "team,India|male|international,India men,male,ODI,team,\n"
                   % pid("V Kohli"))
    d = data(client, "/v1/admin/golden")
    assert d["team_from"] == "2016-01-01" and not d["missing"]
    kohli = d["blocks"][0]
    assert kohli["scope"] == "ODI" and kohli["window"] == "career" and kohli["mat"]
    assert [r["metric"] for r in kohli["rows"]] == ["Mat", "Inn", "NO", "Runs", "HS", "Ave", "100"]
    team = d["blocks"][-1]
    assert team["slug"] == "india-men" and dict((r["metric"], r["ours"])
                                                 for r in team["rows"])["Win %"] == "50.00"


@pytest.mark.parametrize("ours,ref,expl,mat_now,mat_chk,want", [
    ("9230", "", "", "", "", ""), ("9230", "9,230", "", "", "", "match"),
    ("46.85", "46.850", "", "", "", "match"), ("94", "122*", "", "", "", "DIFF"),
    ("94", "122*", "Afghanistan withheld", "", "", "explained"),
    ("9300", "9230", "", "124", "123", "stale"), ("9231", "9230", "", "123", "123", "DIFF")])
def test_status_rules_match_the_pipeline(ours, ref, expl, mat_now, mat_chk, want):
    assert golden.status(ours, ref, expl, mat_now, mat_chk) == want


def test_a_build_is_linked_only_when_it_followed_the_run(home, monkeypatch):
    """A build finishing hours after an ingest was not part of that DSM chain."""
    from db_logic.repository import meta_repo, ops_repo
    from db_logic.repository.db import ServingDB

    db = ServingDB(str(home / "data" / "db" / "cricstat.sqlite"))
    build = {"build_id": 9, "built_at": "2026-10-06T15:02:00Z", "mode": "full",
             "matches": 1, "deliveries": 1, "data_as_of": "x", "status": "success",
             "raw_run_id": 1, "notes": "{}"}
    runs = [{"run_id": 3, "mode": "register", "status": "success",
             "started_at": "2026-10-06T14:30:20Z", "finished_at": "2026-10-06T14:30:23Z",
             "added": 0, "updated": 0, "unchanged": 0, "failed": 0, "removed": 0,
             "active_after": 1},
            {"run_id": 2, "mode": "recent", "status": "success",
             "started_at": "2026-10-06T10:30:08Z", "finished_at": "2026-10-06T10:30:11Z",
             "added": 0, "updated": 0, "unchanged": 0, "failed": 0, "removed": 0,
             "active_after": 1}]
    monkeypatch.setattr(ops_repo, "builds", lambda db, limit=15: [dict(build)])
    monkeypatch.setattr(meta_repo, "ingest_runs", lambda raw, limit=60: runs)
    d, _ = admin_service.jobs(db, "unused", str(home), -5,
                              now=datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc))
    jobs = {j["key"]: j for j in d["jobs"]}
    assert jobs["register"]["last_run"]["build"]["build_id"] == 9      # 32 min later: chained
    assert jobs["daily"]["last_run"]["build"] is None                   # 4.5 h later: not
