"""Queries on forecast.sqlite (schema: cricstat-models db-logic/repository/forecast_store.py).
Stable identifiers only: team_uid (= the API team slug), match_id, model_version."""
import json
from typing import Dict, List, Optional

from db_logic.repository.forecast_db import ForecastDB


def latest(db: ForecastDB, tournament: str) -> Optional[dict]:
    return db.one("SELECT * FROM forecast_runs WHERE tournament = ? ORDER BY forecast_id DESC"
                  " LIMIT 1", (tournament,))


def probabilities(db: ForecastDB, forecast_id: int) -> List[dict]:
    return db.all("SELECT f.team_uid, t.name, f.stage, f.probability FROM forecast_team f"
                  " JOIN team_identities t ON t.team_uid = f.team_uid WHERE f.forecast_id = ?",
                  (forecast_id,))


def runs(db: ForecastDB, tournament: str) -> List[dict]:
    return db.all("SELECT forecast_id, created_at, data_as_of, model_version, n_simulations"
                  " FROM forecast_runs WHERE tournament = ? ORDER BY forecast_id", (tournament,))


def stage_series(db: ForecastDB, tournament: str, team_uid: Optional[str],
                 stages: List[str]) -> List[dict]:
    marks = ",".join("?" * len(stages))
    sql = ("SELECT f.forecast_id, f.team_uid, f.stage, f.probability FROM forecast_team f"
           " JOIN forecast_runs r ON r.forecast_id = f.forecast_id"
           " WHERE r.tournament = ? AND f.stage IN (%s)" % marks)
    args: list = [tournament] + list(stages)
    if team_uid:
        sql += " AND f.team_uid = ?"
        args.append(team_uid)
    return db.all(sql + " ORDER BY f.forecast_id", tuple(args))


def inputs(db: ForecastDB, tournament: str) -> List[dict]:
    return db.all("SELECT i.forecast_id, i.match_id, i.start_date, i.team1_uid, i.team2_uid,"
                  " i.result, i.winner_uid, i.source FROM forecast_inputs i"
                  " JOIN forecast_runs r ON r.forecast_id = i.forecast_id"
                  " WHERE r.tournament = ? ORDER BY i.forecast_id, i.start_date", (tournament,))


def team(db: ForecastDB, team_uid: str) -> Optional[dict]:
    return db.one("SELECT * FROM team_identities WHERE team_uid = ?", (team_uid,))


def teams(db: ForecastDB) -> Dict[str, dict]:
    return {r["team_uid"]: r for r in db.all("SELECT * FROM team_identities")}


def current_ratings(db: ForecastDB, version: str) -> List[dict]:
    """Each team's rating after its last rated match, with its match count and last date."""
    return db.all(
        "SELECT r.team_uid, t.name, r.rating, r.as_of_date AS last_match, n.matches"
        " FROM team_ratings r JOIN team_identities t ON t.team_uid = r.team_uid"
        " JOIN (SELECT team_uid, MAX(as_of_date || '|' || match_id) AS k, COUNT(*) AS matches"
        "       FROM team_ratings WHERE model_version = ? GROUP BY team_uid) n"
        "   ON n.team_uid = r.team_uid AND n.k = r.as_of_date || '|' || r.match_id"
        " WHERE r.model_version = ?", (version, version))


def rating_history(db: ForecastDB, version: str, team_uid: str) -> List[dict]:
    return db.all("SELECT as_of_date AS date, match_id, rating FROM team_ratings"
                  " WHERE model_version = ? AND team_uid = ? ORDER BY as_of_date, match_id",
                  (version, team_uid))


def model_version(db: ForecastDB, version: str) -> Optional[dict]:
    row = db.one("SELECT * FROM model_versions WHERE model_version = ?", (version,))
    if row:
        row["params"] = json.loads(row.pop("params_json") or "{}")
    return row


def model_versions(db: ForecastDB) -> List[dict]:
    return db.all("SELECT model_version, registered_version, mlflow_run_id, promoted_at"
                  " FROM model_versions ORDER BY promoted_at")


def reliability(db: ForecastDB, version: str) -> List[dict]:
    return db.all("SELECT test, model, bin, n, predicted, observed FROM reliability_bins"
                  " WHERE model_version = ? ORDER BY test, model, bin", (version,))


def meta(db: ForecastDB, key: str) -> Optional[str]:
    row = db.one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else None
