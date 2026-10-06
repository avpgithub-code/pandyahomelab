"""API tests run against a real serving DB: a handful of Cricsheet-format matches are zipped, then
the actual cricstat-pipeline ingests them and builds the DB (subprocesses: the two services both
have packages named shared/db_logic, so they can't share one interpreter). No network.
"""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
CRICSTAT = API.parent
PIPELINE = CRICSTAT / "cricstat-pipeline"
sys.path.insert(0, str(API))

RUNS = [0, 1, 4, 0, 2, 6, 1, 0, 1, 0, 0, 3]          # repeating run pattern off the bat


def pid(name):
    return name.encode().hex()[:8].ljust(8, "0")


def innings(team, batters, bowlers, fielder, overs, balls_per_over=6, wicket_every=17, seed=0):
    """Deterministic, internally consistent innings: runs cycle through RUNS, a wide every 13th
    ball, a caught wicket every `wicket_every` balls, bowlers change each over."""
    on_strike, off, nxt = batters[0], batters[1], 2
    out, n = [], seed
    for o in range(overs):
        dels = []
        bowler = bowlers[o % len(bowlers)]
        legal = 0
        while legal < balls_per_over:
            n += 1
            d = {"batter": on_strike, "bowler": bowler, "non_striker": off}
            if n % 13 == 0:
                d["runs"] = {"batter": 0, "extras": 1, "total": 1}
                d["extras"] = {"wides": 1}
                dels.append(d)
                continue
            legal += 1
            r = RUNS[n % len(RUNS)]
            d["runs"] = {"batter": r, "extras": 0, "total": r}
            if n % wicket_every == 0 and nxt < len(batters):
                d["runs"] = {"batter": 0, "extras": 0, "total": 0}
                d["wickets"] = [{"player_out": on_strike, "kind": "caught",
                                 "fielders": [{"name": fielder}]}]
                on_strike, nxt = batters[nxt], nxt + 1
            elif r % 2 == 1:
                on_strike, off = off, on_strike
            dels.append(d)
        out.append({"over": o, "deliveries": dels})
        on_strike, off = off, on_strike
    return {"team": team, "overs": out}


def match(match_type, team_type, gender, date, teams, squads, venue, city, overs, winner,
          event=None, balls_per_over=6, n_innings=2):
    a, b = teams
    inns = []
    for i in range(n_innings):
        bat, bowl = (a, b) if i % 2 == 0 else (b, a)
        inns.append(innings(bat, squads[bat], squads[bowl][-4:], squads[bowl][0], overs,
                            balls_per_over, seed=i * 5 + len(date)))
    people = {n: pid(n) for s in squads.values() for n in s}
    info = {"balls_per_over": balls_per_over, "city": city, "dates": [date], "gender": gender,
            "match_type": match_type, "team_type": team_type, "teams": list(teams),
            "season": date[:4], "venue": venue, "players": squads,
            "registry": {"people": people}, "toss": {"winner": a, "decision": "bat"},
            "outcome": {"winner": winner, "by": {"runs": 5}} if winner else {"result": "no result"}}
    if overs and match_type != "Test":
        info["overs"] = overs
    if event:
        info["event"] = {"name": event}
    return {"meta": {"data_version": "1.2.0", "created": date, "revision": 1}, "info": info,
            "innings": inns}


def squad(prefix, n=11):
    return ["%s %d" % (prefix, i) for i in range(1, n + 1)]


IND, AUS = squad("IndM"), squad("AusM")
INDW, ENGW = squad("IndW"), squad("EngW")
MI, CSK = squad("Mi"), squad("Csk")
IND[0] = "V Kohli"                    # appears in every men's India fixture and in the IPL one
MI[0] = "V Kohli"


def fixture_matches():
    return {
        "9001": match("ODI", "international", "male", "2024-01-10", ("India", "Australia"),
                      {"India": IND, "Australia": AUS}, "Wankhede Stadium, Mumbai", "Mumbai", 10,
                      "India"),
        "9002": match("ODI", "international", "male", "2024-02-10", ("Australia", "India"),
                      {"Australia": AUS, "India": IND}, "Melbourne Cricket Ground", "Melbourne",
                      10, "Australia"),
        "9003": match("T20", "international", "male", "2024-03-10", ("India", "Australia"),
                      {"India": IND, "Australia": AUS}, "Eden Gardens", "Kolkata", 20, "India"),
        "9004": match("Test", "international", "male", "2024-04-10", ("India", "Australia"),
                      {"India": IND, "Australia": AUS}, "Wankhede Stadium, Mumbai", "Mumbai", 15,
                      "India", n_innings=4),
        "9005": match("T20", "international", "female", "2024-05-10", ("India", "England"),
                      {"India": INDW, "England": ENGW}, "Eden Gardens", "Kolkata", 20, "England"),
        "9006": match("T20", "club", "male", "2024-04-20", ("Mumbai Indians",
                                                           "Chennai Super Kings"),
                      {"Mumbai Indians": MI, "Chennai Super Kings": CSK},
                      "Wankhede Stadium, Mumbai", "Mumbai", 20, "Mumbai Indians",
                      event="Indian Premier League"),
        "9007": match("ODI", "international", "male", "2025-01-10", ("India", "Australia"),
                      {"India": IND, "Australia": AUS}, "Wankhede Stadium, Mumbai", "Mumbai", 10,
                      None),
    }


def pipeline(home, *args):
    env = dict(os.environ, CRICSTAT_HOME=str(home), CRICSTAT_SQL_DIR=str(CRICSTAT / "sql"),
               CRICSTAT_VENUE_MAP=str(CRICSTAT / "sql" / "venue_map.csv"))
    res = subprocess.run([sys.executable, "-m", "presentation_logic.cli"] + list(args)
                         + ["--quiet"], cwd=str(PIPELINE), env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    return json.loads(res.stdout)


def ingest(home, docs, name="all_json.zip", mode="full"):
    path = home / name
    with zipfile.ZipFile(path, "w") as zf:
        for mid, doc in docs.items():
            zf.writestr(mid + ".json", json.dumps(doc, indent=1))
    pipeline(home, mode, "--zip-path", str(path))


@pytest.fixture(scope="session")
def home(tmp_path_factory):
    h = tmp_path_factory.mktemp("cricstat")
    ingest(h, fixture_matches())
    pipeline(h, "build", "--full")
    return h


@pytest.fixture(scope="session")
def client(home):
    from fastapi.testclient import TestClient

    from presentation_logic.api.app import create_app
    from shared.config import Config

    os.environ["CRICSTAT_HOME"] = str(home)
    with TestClient(create_app(Config())) as c:
        yield c
