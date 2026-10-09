"""data/db/forecast.sqlite: the predictor's own file (P1 plan §4), written only by cricstat-models.

The pipeline owns cricstat.sqlite; this file sits next to it and the API opens both read-only.
Every write copies the live file to forecast.sqlite.new, adds to it, runs the checks, then
os.replace()s it, so readers never see a half-written forecast and a failed check leaves the live
file untouched. Keys are stable identifiers only (team_uid, match_id): never the serving surrogates.
"""
import json
import os
import re
import shutil
import sqlite3
from typing import Dict, Iterable, List, Optional

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_identities (            -- one stable id per team, incl. Afghanistan
  team_uid TEXT PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL, team_type TEXT NOT NULL,
  in_serving INTEGER NOT NULL, UNIQUE (name, gender, team_type));
CREATE TABLE IF NOT EXISTS model_versions (             -- each parameter set behind a forecast
  model_version TEXT PRIMARY KEY, registered_version TEXT, mlflow_run_id TEXT, promoted_at TEXT,
  params_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_ratings (               -- rating after every rated match
  team_uid TEXT NOT NULL REFERENCES team_identities(team_uid), as_of_date TEXT NOT NULL,
  match_id TEXT NOT NULL, rating REAL NOT NULL, model_version TEXT NOT NULL,
  PRIMARY KEY (team_uid, match_id, model_version));
CREATE TABLE IF NOT EXISTS forecast_runs (
  forecast_id INTEGER PRIMARY KEY, tournament TEXT NOT NULL, created_at TEXT NOT NULL,
  data_as_of TEXT NOT NULL, build_id INTEGER, fingerprint TEXT NOT NULL,
  n_simulations INTEGER NOT NULL,
  model_version TEXT NOT NULL REFERENCES model_versions(model_version),
  mlflow_run_id TEXT, days_to_start INTEGER, sigma REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS forecast_team (
  forecast_id INTEGER NOT NULL REFERENCES forecast_runs(forecast_id),
  team_uid TEXT NOT NULL REFERENCES team_identities(team_uid), stage TEXT NOT NULL,
  probability REAL NOT NULL, PRIMARY KEY (forecast_id, team_uid, stage));
CREATE TABLE IF NOT EXISTS forecast_inputs (            -- the matches that are new since the
  forecast_id INTEGER NOT NULL REFERENCES forecast_runs(forecast_id),   -- previous forecast:
  match_id TEXT NOT NULL, start_date TEXT NOT NULL,     -- "why did the odds move?"
  team1_uid TEXT NOT NULL, team2_uid TEXT NOT NULL, result TEXT NOT NULL, winner_uid TEXT,
  source TEXT NOT NULL, PRIMARY KEY (forecast_id, match_id));
CREATE TABLE IF NOT EXISTS forecast_fixtures (          -- each known fixture's chances, per
  forecast_id INTEGER NOT NULL REFERENCES forecast_runs(forecast_id),   -- forecast: "last moved"
  match_no TEXT NOT NULL, team1 TEXT NOT NULL, team2 TEXT NOT NULL,
  p_team1 REAL NOT NULL, p_team2 REAL NOT NULL, p_tie REAL NOT NULL, p_no_result REAL NOT NULL,
  PRIMARY KEY (forecast_id, match_no));
CREATE TABLE IF NOT EXISTS backtest_metrics (           -- for the methodology page
  model_version TEXT NOT NULL, test TEXT NOT NULL, model TEXT NOT NULL, metric TEXT NOT NULL,
  value REAL NOT NULL, PRIMARY KEY (model_version, test, model, metric));
CREATE TABLE IF NOT EXISTS reliability_bins (
  model_version TEXT NOT NULL, test TEXT NOT NULL, model TEXT NOT NULL, bin TEXT NOT NULL,
  n INTEGER NOT NULL, predicted REAL NOT NULL, observed REAL NOT NULL,
  PRIMARY KEY (model_version, test, model, bin));
CREATE INDEX IF NOT EXISTS ix_team_ratings_date ON team_ratings(model_version, as_of_date);
"""
STAGES = ("qualified", "super_series", "group", "super7", "semi", "final", "champion")


def team_uid(name: str, gender: str = "male", team_type: str = "international") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return "%s-%s%s" % (slug, "men" if gender == "male" else "women",
                        "" if team_type == "international" else "-club")


class ForecastWriter:
    """with ForecastWriter(path) as w: ...; w.commit()  → checks + atomic swap."""

    def __init__(self, path: str):
        self.path = path
        self.tmp = path + ".new"

    def __enter__(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)
        if os.path.exists(self.path):
            shutil.copyfile(self.path, self.tmp)
        self.conn = sqlite3.connect(self.tmp)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)",
                          (str(SCHEMA_VERSION),))
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.conn.close()
        finally:
            if exc_type is not None and os.path.exists(self.tmp):
                os.remove(self.tmp)
        return False

    # -- writes ----------------------------------------------------------------------------------
    def teams(self, names: Iterable[str], in_serving: Iterable[str]) -> Dict[str, str]:
        serving = set(in_serving)
        out = {}
        for n in sorted(set(names)):
            uid = team_uid(n)
            self.conn.execute("INSERT INTO team_identities VALUES"
                              " (?, ?, 'male', 'international', ?) ON CONFLICT(team_uid)"
                              " DO UPDATE SET in_serving = excluded.in_serving",
                              (uid, n, 1 if n in serving else 0))
            out[n] = uid
        return out

    def meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def model_version(self, version: str, params: Dict[str, object], registered: Optional[str],
                      run_id: Optional[str], promoted_at: Optional[str]) -> None:
        self.conn.execute("INSERT OR IGNORE INTO model_versions VALUES (?, ?, ?, ?, ?)",
                          (version, registered, run_id, promoted_at,
                           json.dumps(params, sort_keys=True)))

    def ratings(self, version: str, rows: Iterable[tuple]) -> None:
        """rows: (team_uid, date, match_id, rating). Replaces this version's history."""
        self.conn.execute("DELETE FROM team_ratings WHERE model_version = ?", (version,))
        self.conn.executemany("INSERT INTO team_ratings VALUES (?, ?, ?, ?, ?)",
                              ((u, d, m, round(r, 3), version) for u, d, m, r in rows))

    def forecast(self, run: Dict[str, object], probs: Dict[str, Dict[str, float]],
                 inputs: List[Dict[str, object]]) -> int:
        cur = self.conn.execute(
            "INSERT INTO forecast_runs (tournament, created_at, data_as_of, build_id, fingerprint,"
            " n_simulations, model_version, mlflow_run_id, days_to_start, sigma, notes)"
            " VALUES (:tournament, :created_at, :data_as_of, :build_id, :fingerprint,"
            " :n_simulations, :model_version, :mlflow_run_id, :days_to_start, :sigma, :notes)", run)
        fid = cur.lastrowid
        self.conn.executemany("INSERT INTO forecast_team VALUES (?, ?, ?, ?)",
                              ((fid, uid, st, p) for uid, stages in probs.items()
                               for st, p in stages.items()))
        self.conn.executemany(
            "INSERT INTO forecast_inputs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ((fid, i["match_id"], i["start_date"], i["team1_uid"], i["team2_uid"], i["result"],
              i["winner_uid"], i["source"]) for i in inputs))
        return fid

    def fixtures(self, forecast_id: int, rows) -> None:
        """rows: fixtures_summary() entries; only those with chances (two known teams)."""
        self.conn.executemany(
            "INSERT INTO forecast_fixtures VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ((forecast_id, r["match_no"], r["slot1"], r["slot2"], r["chances"]["team1"],
              r["chances"]["team2"], r["chances"]["tie"], r["chances"]["no_result"])
             for r in rows if r.get("chances")))

    def backtest(self, version: str, metric_rows: Iterable[tuple], bins: Iterable[tuple]) -> None:
        self.conn.execute("DELETE FROM backtest_metrics WHERE model_version = ?", (version,))
        self.conn.execute("DELETE FROM reliability_bins WHERE model_version = ?", (version,))
        self.conn.executemany("INSERT INTO backtest_metrics VALUES (?, ?, ?, ?, ?)",
                              ((version,) + tuple(r) for r in metric_rows))
        self.conn.executemany("INSERT INTO reliability_bins VALUES (?, ?, ?, ?, ?, ?, ?)",
                              ((version,) + tuple(r) for r in bins))

    # -- checks + swap ---------------------------------------------------------------------------
    def check(self, forecast_id: Optional[int], expect: Dict[str, float]) -> List[str]:
        """Integrity (foreign keys, quick_check) and, for a new forecast, the stage sums."""
        errors = []
        if self.conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            errors.append("quick_check failed")
        fk = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            errors.append("%d foreign-key violations" % len(fk))
        if forecast_id is not None:
            got = dict(self.conn.execute(
                "SELECT stage, SUM(probability) FROM forecast_team WHERE forecast_id = ?"
                " GROUP BY stage", (forecast_id,)).fetchall())
            for stage, want in expect.items():
                if abs(got.get(stage, 0.0) - want) > 1e-6:
                    errors.append("stage %s sums to %.6f, expected %s" % (stage, got.get(stage, 0),
                                                                          want))
            bad = self.conn.execute("SELECT COUNT(*) FROM forecast_team WHERE forecast_id = ? AND"
                                    " (probability < 0 OR probability > 1)",
                                    (forecast_id,)).fetchone()[0]
            if bad:
                errors.append("%d probabilities outside [0, 1]" % bad)
        return errors

    def commit(self) -> None:
        self.conn.commit()
        self.conn.close()
        os.replace(self.tmp, self.path)
        self.conn = sqlite3.connect(":memory:")     # so __exit__ has something to close


def connect_ro(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def last_forecast(path: str, tournament: str) -> Optional[Dict[str, object]]:
    if not os.path.exists(path):
        return None
    with connect_ro(path) as conn:
        try:
            row = conn.execute("SELECT * FROM forecast_runs WHERE tournament = ?"
                               " ORDER BY forecast_id DESC LIMIT 1", (tournament,)).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None


def model_params(path: str, version: str) -> Optional[Dict[str, object]]:
    if not os.path.exists(path):
        return None
    with connect_ro(path) as conn:
        row = conn.execute("SELECT params_json FROM model_versions WHERE model_version = ?",
                           (version,)).fetchone()
        return json.loads(row[0]) if row else None
