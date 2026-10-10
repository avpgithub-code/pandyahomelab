"""ODI World Cup 2027 predictor endpoints (F5 "Predictor", P1.5), read from forecast.sqlite.

The forecast is produced by cricstat-models: Elo ratings + 50,000 simulated tournaments, one
model for every team. The disclosures below travel with the data, so every consumer (the predictor
page, the methodology page, later the AI analyst) states the same limits.
"""
import datetime
import json
import math
from typing import Dict, List, Optional, Tuple

from application_logic.services.common import team_slugs
from db_logic.repository import forecast_repo
from db_logic.repository.db import ServingDB
from db_logic.repository.forecast_db import ForecastDB
from shared.exceptions import BadFilter, NoForecast, NotFound

TOURNAMENTS = {"wc-2027": "wc2027"}
STAGES = [("qualified", "Qualify through the Qualifier"),
          ("super_series", "Play the Super Series"), ("group", "Play the group stage"),
          ("super7", "Reach the Super 7"), ("semi", "Reach the semi-finals"),
          ("final", "Reach the final"), ("champion", "Win the World Cup")]
ACTIVE_DAYS = 730          # a team is ranked when it played an ODI in the last two years

DISCLOSURES = {
    "model": "Elo ratings from every men's ODI since 2002, home advantage, and 50,000 simulated "
             "tournaments in the published 2027 format. The same model and parameters for every "
             "team; following a team changes what you see first, never the numbers.",
    "not_advice": "A statistical estimate from past results, not a tip and not betting advice.",
    "not_used": "Squads, injuries, form of individual players, pitches and weather are not used "
                "(yet): the machine-learning and deep-learning challengers will test them.",
    "afghanistan": "Cricsheet withholds Afghanistan men's matches as a protest over Afghan women's "
                   "cricket (cricsheet.org, 14 Nov 2024). To keep the forecast fair to every team, "
                   "Afghanistan's ODI results (not scorecards) come from Wikipedia, are checked "
                   "against a second source and reviewed before use, and are rated by the same "
                   "rule. Afghanistan's player statistics are not in cricstat.",
    "data": "Match data from 2002; no-result rates by host country and season; net run rate is "
            "not simulated (ties on points are split by wins, then at random).",
    "qualifier": "Until the Qualifier (Feb–Mar 2027) settles the last four places, those places "
                 "are drawn by simulating the candidates' chances.",
}


def json_safe(value):
    """NaN/±inf → None, recursively: JSON has no NaN (e.g. a coin flip has no 'accuracy'), and the
    model record stored by cricstat-models may contain it."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def _tournament(tournament: str) -> str:
    tid = TOURNAMENTS.get(tournament)
    if not tid:
        raise NotFound("unknown tournament %r; available: %s" % (tournament,
                                                                  ", ".join(TOURNAMENTS)))
    return tid


def _slug(db: ServingDB, name: str) -> Optional[str]:
    """The team page slug when the team has a page (Afghanistan men has none)."""
    return team_slugs(db).find(name, "male", "international")


def _forecast_meta(run: dict) -> dict:
    out = {k: run[k] for k in ("forecast_id", "created_at", "data_as_of", "n_simulations",
                               "model_version", "mlflow_run_id", "days_to_start")}
    out["rating_uncertainty_sd"] = round(run["sigma"] or 0.0, 1)
    return out


def etag(fdb: ForecastDB, tournament: str = "wc2027") -> str:
    run = forecast_repo.latest(fdb, tournament)
    return "f%s" % (run["forecast_id"] if run else 0)


def latest(db: ServingDB, fdb: ForecastDB, tournament: str) -> Tuple[dict, dict]:
    tid = _tournament(tournament)
    run = forecast_repo.latest(fdb, tid)
    if not run:
        raise NoForecast("no %s forecast yet" % tournament)
    summary = json.loads(forecast_repo.meta(fdb, "tournament:%s" % tid) or "{}")
    group_of = {t: g for g, members in summary.get("groups", {}).items() for t in members}
    ratings = {r["team_uid"]: r for r in forecast_repo.current_ratings(fdb, run["model_version"])}
    teams: Dict[str, dict] = {}
    for r in forecast_repo.probabilities(fdb, run["forecast_id"]):
        t = teams.setdefault(r["team_uid"], {
            "team": r["name"], "team_uid": r["team_uid"], "slug": _slug(db, r["name"]),
            "rating": round(ratings[r["team_uid"]]["rating"], 1)
            if r["team_uid"] in ratings else None,
            "group": group_of.get(r["name"]), "probabilities": {}})
        t["probabilities"][r["stage"]] = round(r["probability"], 5)
    for t in teams.values():
        t["direct_qualifier"] = "qualified" not in t["probabilities"]
    rows = sorted(teams.values(), key=lambda t: (-t["probabilities"].get("champion", 0),
                                                 -t["probabilities"].get("semi", 0),
                                                 -(t["rating"] or 0)))
    model = forecast_repo.model_version(fdb, run["model_version"]) or {"params": {}}
    data = {"tournament": {k: summary.get(k) for k in ("id", "name", "start", "end", "hosts",
                                                         "groups", "matches", "played")},
            "forecast": _forecast_meta(run),
            "stages": [{"id": s, "label": label} for s, label in STAGES],
            "teams": rows,
            "model": {"family": model["params"].get("family", "elo"), "label": "cricstat Elo",
                      "version": run["model_version"], "elo": model["params"].get("elo")},
            "assumptions": summary.get("assumptions", []),
            "disclosures": DISCLOSURES}
    defs = {"probabilities": "Share of the simulated tournaments in which the team reached the "
                             "stage (champion: won it; a washed-out final counts half each).",
            "rating": "Elo rating after the team's last ODI (1500 = an average Full Member at "
                      "the start of the data)."}
    return data, defs


def history(db: ServingDB, fdb: ForecastDB, tournament: str, team: Optional[str]
            ) -> Tuple[dict, dict]:
    tid = _tournament(tournament)
    if team and not forecast_repo.team(fdb, team):
        raise NotFound("no team %r in the forecast" % team)
    names = {u: r["name"] for u, r in forecast_repo.teams(fdb).items()}
    stages = ["champion", "final", "semi", "super7"] if team else ["champion"]
    by_run: Dict[int, dict] = {}
    for r in forecast_repo.runs(fdb, tid):
        by_run[r["forecast_id"]] = dict(r, probabilities={}, moved_by=[])
    for p in forecast_repo.stage_series(fdb, tid, team, stages):
        run = by_run.get(p["forecast_id"])
        if run is not None:
            key = p["stage"] if team else p["team_uid"]
            run["probabilities"][key] = round(p["probability"], 5)
    for i in forecast_repo.inputs(fdb, tid):
        run = by_run.get(i["forecast_id"])
        if run is None or (team and team not in (i["team1_uid"], i["team2_uid"])):
            continue
        run["moved_by"].append({"match_id": i["match_id"], "date": i["start_date"],
                                "team1": names.get(i["team1_uid"]),
                                "team2": names.get(i["team2_uid"]), "result": i["result"],
                                "winner": names.get(i["winner_uid"]), "source": i["source"]})
    series = list(by_run.values())
    data = {"team": team and {"team_uid": team, "team": names.get(team),
                              "slug": _slug(db, names.get(team, ""))},
            "series": series}
    defs = {"moved_by": "Men's ODIs added since the previous forecast"
                        + (" involving this team." if team else "."),
            "probabilities": ("Chance of each stage, per forecast." if team
                              else "Chance of winning the World Cup per team (team_uid), per "
                                   "forecast.")}
    return data, defs


def fixtures(db: ServingDB, fdb: ForecastDB, tournament: str) -> Tuple[dict, dict]:
    """The schedule (with each fixed match's chances) and the venues (facts, photo credit, history),
    as stored with the latest forecast."""
    tid = _tournament(tournament)
    run = forecast_repo.latest(fdb, tid)
    if not run:
        raise NoForecast("no %s forecast yet" % tournament)
    fx = json.loads(forecast_repo.meta(fdb, "fixtures:%s" % tid) or "[]")
    venues = json.loads(forecast_repo.meta(fdb, "venues:%s" % tid) or "[]")
    last = last_changes(forecast_repo.fixture_series(fdb, tid))
    slugs: Dict[str, Optional[str]] = {}
    for f in fx:
        change = last.get(str(f["match_no"]))
        if change and f.get("chances") and change["teams"] == (f["slot1"], f["slot2"]):
            f["last_change"] = {k: change[k]
                                for k in ("team1_pts", "team2_pts", "data_as_of")}
        for k in ("slot1", "slot2"):
            name = f[k]
            if name not in slugs:
                slugs[name] = _slug(db, name)
            f[k + "_slug"] = slugs[name]
    data = {"forecast": _forecast_meta(run), "fixtures": fx, "venues": venues,
            "source": "Schedule, venues, capacities and start times: Wikipedia, 2027 Cricket World "
                      "Cup (CC BY-SA 4.0), from the ICC schedule of 1 Oct 2026. Venue history: "
                      "Cricsheet men's ODIs. Venue photos: Wikimedia Commons, credited per photo."}
    defs = {"chances": "For a match whose teams are known: win, tie and no-result chances from "
                       "the current ratings, home advantage and the host country's October–"
                       "November no-result rate (the same inputs the simulation uses).",
            "last_change": "The most recent change in a match's chances (percentage points) "
                           "and the data date of the forecast that moved it: it moves only when "
                           "one of the two teams plays.",
            "slot": "A placeholder until a stage decides it: A2 = 2nd in Group A, 4TH = best "
                    "fourth-placed team, S7-1 = 1st in the Super 7, W55 = winner of match 55, "
                    "Q2–Q4 = Qualifier places, QA/QB = the two qualifier slots in the groups.",
            "history.avg_first_innings": "Average first-innings total in men's ODIs at the ground "
                                         "(full innings only: 50 overs or all out, no D/L)."}
    return data, defs


def last_changes(series: List[dict], min_pts: float = 0.05) -> Dict[str, dict]:
    """Per fixture: the most recent forecast in which its chances moved, and by how much (points).
    A card's chances depend only on its two teams, so they move only when one of them plays."""
    out: Dict[str, dict] = {}
    prev: Dict[str, dict] = {}
    for r in series:                                    # ordered by match_no, forecast_id
        p = prev.get(r["match_no"])
        if p and (p["team1"], p["team2"]) == (r["team1"], r["team2"]):
            d1, d2 = 100 * (r["p_team1"] - p["p_team1"]), 100 * (r["p_team2"] - p["p_team2"])
            if abs(d1) >= min_pts or abs(d2) >= min_pts:
                out[r["match_no"]] = {"team1_pts": round(d1, 1), "team2_pts": round(d2, 1),
                                      "data_as_of": r["data_as_of"],
                                      "teams": (r["team1"], r["team2"])}
        prev[r["match_no"]] = r
    return out


def _parse_scope(scope: str, gender: str) -> None:
    if scope != "ODI" or gender != "male":
        raise BadFilter("ratings are available for scope=ODI and gender=male (the 2027 ODI World "
                        "Cup model); other formats come later")


def ratings(db: ServingDB, fdb: ForecastDB, scope: str, gender: str) -> Tuple[list, dict]:
    _parse_scope(scope, gender)
    run = forecast_repo.latest(fdb, "wc2027")
    if not run:
        raise NoForecast("no ratings yet")
    as_of = datetime.date.fromisoformat(run["data_as_of"])
    rows = []
    for r in forecast_repo.current_ratings(fdb, run["model_version"]):
        last = datetime.date.fromisoformat(r["last_match"])
        rows.append({"team": r["name"], "team_uid": r["team_uid"], "slug": _slug(db, r["name"]),
                     "rating": round(r["rating"], 1), "matches": r["matches"],
                     "last_match": r["last_match"],
                     "active": (as_of - last).days <= ACTIVE_DAYS})
    rows.sort(key=lambda r: -r["rating"])
    rank = 0
    for r in rows:
        if r["active"]:
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = None
    defs = {"rating": "Elo rating after the team's last men's ODI (model %s, data to %s)."
                      % (run["model_version"], run["data_as_of"]),
            "rank": "Rank among teams with a men's ODI in the last two years.",
            "matches": "Rated men's ODIs since 2002 (Afghanistan from the reviewed results list)."}
    return rows, defs


def rating_history(db: ServingDB, fdb: ForecastDB, slug: str, scope: str) -> Tuple[dict, dict]:
    _parse_scope(scope, "male")
    t = forecast_repo.team(fdb, slug)
    if not t:
        raise NotFound("no rated team %r (ratings exist for men's ODI teams)" % slug)
    run = forecast_repo.latest(fdb, "wc2027")
    if not run:
        raise NoForecast("no ratings yet")
    points = [dict(p, rating=round(p["rating"], 1))
              for p in forecast_repo.rating_history(fdb, run["model_version"], slug)]
    data = {"team": t["name"], "team_uid": slug, "slug": _slug(db, t["name"]),
            "model_version": run["model_version"], "points": points}
    return data, {"rating": "Elo rating after each men's ODI the team played."}


def backtest(fdb: ForecastDB) -> Tuple[dict, dict]:
    run = forecast_repo.latest(fdb, "wc2027")
    if not run:
        raise NoForecast("no model yet")
    model = forecast_repo.model_version(fdb, run["model_version"]) or {"params": {}}
    p = model["params"]
    data = {"champion": {"model_version": run["model_version"],
                         "registered_version": model.get("registered_version"),
                         "mlflow_run_id": model.get("mlflow_run_id"),
                         "trained_at": p.get("trained_at"), "data_as_of": p.get("data_as_of"),
                         "elo": p.get("elo"), "rating_drift_a": p.get("sigma_a"),
                         "conditions": p.get("conditions")},
            "metrics": p.get("metrics", {}), "gates": p.get("gates", {}),
            "backtest": p.get("backtest"),
            "reliability": forecast_repo.reliability(fdb, run["model_version"]),
            "comparison": [
                {"model": "cricstat Elo (baseline)", "kind": "statistics", "status": "live",
                 "test_a_log_loss": p.get("metrics", {}).get("test_a.log_loss"),
                 "test_b_log_loss": p.get("metrics", {}).get("test_b.log_loss")},
                {"model": "Win-rate baseline", "kind": "baseline", "status": "reference",
                 "test_a_log_loss": p.get("metrics", {}).get("test_a.win_rate.log_loss"),
                 "test_b_log_loss": p.get("metrics", {}).get("test_b.win_rate.log_loss")},
                {"model": "Gradient boosting with squad features", "kind": "machine learning",
                 "status": "planned"},
                {"model": "Player embeddings from ball-by-ball data", "kind": "deep learning",
                 "status": "planned"}],
            "versions": forecast_repo.model_versions(fdb),
            "disclosures": DISCLOSURES}
    defs = {"test_a": "Every men's ODI since 2019, each year predicted with parameters tuned on "
                      "the years before it.",
            "test_b": "Every match of the 2019 and 2023 World Cups, from ratings frozen on the "
                      "eve of the tournament.",
            "test_c": "Pre-tournament simulation vs what happened (reported, not a gate: two "
                      "tournaments can't prove much).",
            "log_loss": "Average −ln(probability given to what happened); lower is better; a coin "
                        "flip scores 0.693.",
            "brier": "Mean squared error of the win probability; lower is better; a coin flip "
                     "scores 0.25.",
            "calibration_slope": "1.0 = well calibrated; below 1 overconfident, above 1 "
                                 "underconfident."}
    return data, defs


def admin_block(fdb: ForecastDB) -> Optional[dict]:
    """For /v1/admin/jobs: the predictor job's last forecast and model (None if not deployed)."""
    try:
        run = forecast_repo.latest(fdb, "wc2027")
    except NoForecast:
        return None
    if not run:
        return None
    return {k: run[k] for k in ("forecast_id", "created_at", "data_as_of", "model_version",
                                "n_simulations", "mlflow_run_id", "days_to_start")}
