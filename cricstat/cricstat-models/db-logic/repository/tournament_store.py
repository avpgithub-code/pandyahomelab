"""Tournament configs: tournaments/<id>/format.json + tournaments/<id>/fixtures.csv.

format.json   name, dates, hosts, teams, points, stages (round robin / knockout rules),
              tie-breakers, sources, and every assumption the simulator makes where the rules
              aren't published.
fixtures.csv  one row per scheduled match, all stages:
    match_no, stage, group, date, slot1, slot2, venue, city, venue_country, match_key,
    team1, team2, result, winner, has_play
  slot1/slot2 = a team name for a fixed fixture, or a placeholder the format resolves during the
  simulation (A2 = 2nd in group A, 4TH = best 4th-placed team, S7-1 = 1st in the Super 7,
  W51 = winner of match 51, Q1..Q4 = Qualifier places, SSW = Super Series winner, QA/QB = the two
  qualifier slots in groups A and B).
  team1/team2/result/winner/has_play = what actually happened (blank until played). The replay test
  and the in-tournament forecast both read them.
  match_key = the ESPNcricinfo match id (Cricsheet's id space) when the source lists one.
"""
import csv
import json
import os
from typing import Dict, List

FIXTURE_COLUMNS = ("match_no", "stage", "group", "date", "slot1", "slot2", "venue", "city",
                   "venue_country", "match_key", "team1", "team2", "result", "winner", "has_play")


def tournament_dir(root: str, tid: str) -> str:
    return os.path.join(root, tid)


def read_format(root: str, tid: str) -> Dict[str, object]:
    with open(os.path.join(tournament_dir(root, tid), "format.json"), encoding="utf-8") as f:
        return json.load(f)


def write_format(root: str, tid: str, fmt: Dict[str, object]) -> None:
    os.makedirs(tournament_dir(root, tid), exist_ok=True)
    path = os.path.join(tournament_dir(root, tid), "format.json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(fmt, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(path + ".tmp", path)


def read_fixtures(root: str, tid: str) -> List[Dict[str, str]]:
    with open(os.path.join(tournament_dir(root, tid), "fixtures.csv"), encoding="utf-8",
              newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def write_fixtures(root: str, tid: str, rows: List[Dict[str, object]]) -> None:
    os.makedirs(tournament_dir(root, tid), exist_ok=True)
    path = os.path.join(tournament_dir(root, tid), "fixtures.csv")
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(FIXTURE_COLUMNS), lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: int(r["match_no"])):
            w.writerow({k: "" if r.get(k) is None else r.get(k) for k in FIXTURE_COLUMNS})
    os.replace(path + ".tmp", path)


def tournament_ids(root: str) -> List[str]:
    return sorted(d for d in os.listdir(root)
                  if os.path.exists(os.path.join(root, d, "format.json")))
