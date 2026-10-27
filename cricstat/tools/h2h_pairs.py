"""Head to Head pairs that get an indexed page (docs/h2h-plan.md §3, step H5).

    python3 cricstat/tools/h2h_pairs.py [--db cricstat/data/db/cricstat.sqlite]

Reads the owner's hand-picked list (docs/h2h/picked.csv: kind, a, b, note; players and teams by their
page slug, never by name, because names repeat: two SR Taylors, three Rashid Khans), adds the
data-driven pairs below and writes docs/h2h/pairs.csv. That file is the indexed set: the landing
page lists it (gen_pages.py), the API marks only these pages `index` and puts them in the sitemap.
Any other pair still works for visitors, as `noindex`.

Rules for every pair: internationals only (Test, ODI, T20I); both sides indexable (the player-page
bar) and of the same gender; ICC Full Members only for the data-driven pairs; no Afghanistan men,
because Cricsheet withholds their matches (CLAUDE.md). Re-run after the data grows; it is
deterministic for a given database.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
CRICSTAT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(CRICSTAT, "cricstat-api")]

from application_logic.services import matches_service, players_service  # noqa: E402
from application_logic.services.common import team_slugs  # noqa: E402
from application_logic.services.slugs import player_slug  # noqa: E402
from db_logic.repository import meta_repo, pages_repo  # noqa: E402
from db_logic.repository.db import ServingDB  # noqa: E402

PICKED = os.path.join(CRICSTAT, "docs", "h2h", "picked.csv")
OUT = os.path.join(CRICSTAT, "docs", "h2h", "pairs.csv")
INTL = ("ODI", "TEST", "T20I")
LABEL = {"ODI": "ODI", "TEST": "Test", "T20I": "T20I"}
FULL_MEMBERS = {"Afghanistan", "Australia", "Bangladesh", "England", "India", "Ireland",
                "New Zealand", "Pakistan", "South Africa", "Sri Lanka", "West Indies", "Zimbabwe"}
WITHHELD = ("Afghanistan", "male")          # Cricsheet withholds Afghanistan men's matches
MIN_INTL, MIN_LEAGUE = 10, 20               # the player-page index bar (shared/config.py defaults)

# Matchups: minimum balls between the two (either direction) in the format, how many data-driven
# pairs per (gender, format), and how many data-driven pairs one player may appear in.
MATCHUP_BAR = {"TEST": 60, "ODI": 60, "T20I": 36}
MATCHUP_QUOTA = {("male", "TEST"): 22, ("male", "ODI"): 20, ("male", "T20I"): 8,
                 ("female", "ODI"): 12, ("female", "T20I"): 8}
PER_PLAYER = 3
PICKED_MIN_BALLS = 30                       # below this a matchup is a "small sample" (h2h_service)
# Comparisons: leaders over the last five years, paired #1 v #2, #3 v #4 … (pairs per list).
COMPARE_QUOTA = {("male", "ODI", "batting"): 3, ("male", "TEST", "batting"): 3,
                 ("male", "T20I", "batting"): 2, ("male", "ODI", "bowling"): 2,
                 ("male", "TEST", "bowling"): 2, ("male", "T20I", "bowling"): 1,
                 ("female", "ODI", "batting"): 2, ("female", "T20I", "batting"): 2,
                 ("female", "ODI", "bowling"): 1, ("female", "T20I", "bowling"): 2}
COUNTRY_QUOTA = {"male": 20, "female": 10}
COLUMNS = ["kind", "path", "a", "b", "a_name", "b_name", "gender", "source", "why"]


def path(a: str, b: str) -> str:
    return "-vs-".join(sorted((a, b)))


class Data:
    def __init__(self, db: ServingDB):
        self.db = db
        rows = db.all("SELECT player_key, player_id, name FROM players")
        self.by_id = {r["player_id"]: r for r in rows}
        self.by_key = {r["player_key"]: r for r in rows}
        self.indexable = {r["player_id"] for r in pages_repo.indexable_players(db, MIN_INTL,
                                                                              MIN_LEAGUE)}
        # Each player's main international team (most matches) and gender.
        self.team = {}
        for r in db.all(
                "SELECT x.player_key, t.name, x.gender, COUNT(DISTINCT x.match_key) AS n FROM ("
                " SELECT player_key, team_key, gender, match_key FROM batting_innings"
                "  WHERE format_key IN ('ODI', 'TEST', 'T20I')"
                " UNION ALL SELECT player_key, team_key, gender, match_key FROM bowling_innings"
                "  WHERE format_key IN ('ODI', 'TEST', 'T20I')) x"
                " JOIN teams t ON t.team_key = x.team_key GROUP BY 1, 2, 3 ORDER BY 1, 4"):
            self.team[r["player_key"]] = (r["name"], r["gender"])     # the last row = most
        self.names = {}
        self.slugs = team_slugs(db)

    def player(self, pid: str) -> dict:
        return self.by_id[pid]

    def slug(self, p: dict) -> str:
        return player_slug(p["name"], p["player_id"])

    def full_names(self, pids):
        missing = [p for p in pids if p not in self.names]
        for k, v in players_service.display(self.db, missing).items():
            self.names[k] = v["full_name"]
        return [self.names.get(p, self.by_id[p]["name"]) for p in pids]

    def problem(self, p: dict, full_member: bool) -> str:
        """Why this player can't be in an indexed pair ('' when they can)."""
        team = self.team.get(p["player_key"])
        if p["player_id"] not in self.indexable:
            return "below the player-page index bar"
        if not team:
            return "no international matches"
        if team == WITHHELD:
            return "Afghanistan men (matches withheld by Cricsheet)"
        if full_member and team[0] not in FULL_MEMBERS:
            return "not a Full Member player"
        return ""


def balls_between(d: Data):
    """{(key_lo, key_hi): {scope: {"balls", "outs"}}} for international pairs, both directions."""
    out = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "outs": 0}))
    for r in d.db.all("SELECT scope, batter_key, bowler_key, balls, outs FROM matchups"
                      " WHERE scope IN ('ODI', 'TEST', 'T20I') AND balls >= ?",
                      (min(PICKED_MIN_BALLS, *MATCHUP_BAR.values()) // 2,)):
        k = tuple(sorted((r["batter_key"], r["bowler_key"])))
        out[k][r["scope"]]["balls"] += r["balls"]
        out[k][r["scope"]]["outs"] += r["outs"]
    return out


def matchup_why(scopes: dict) -> str:
    best = max(scopes, key=lambda s: scopes[s]["balls"])
    m = scopes[best]
    return "%s: %d balls, %d dismissals" % (LABEL[best], m["balls"], m["outs"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=os.path.join(CRICSTAT, "data", "db", "cricstat.sqlite"))
    args = ap.parse_args()
    d = Data(ServingDB(args.db))
    as_of = (meta_repo.latest_build(d.db) or {}).get("data_as_of") or date.today().isoformat()
    since = "%d%s" % (int(as_of[:4]) - 5, as_of[4:10])
    pairs = balls_between(d)
    rows, seen, rejected = [], set(), []

    def add(kind, a_slug, b_slug, a_name, b_name, gender, source, why):
        p = path(a_slug, b_slug)
        if p in seen:
            return False
        seen.add(p)
        if a_slug > b_slug:                             # columns follow the URL order
            a_slug, b_slug, a_name, b_name = b_slug, a_slug, b_name, a_name
        rows.append(dict(kind=kind, path=p, a=a_slug, b=b_slug, a_name=a_name, b_name=b_name,
                         gender=gender, source=source, why=why))
        return True

    # ── 1. The owner's picks ──
    with open(PICKED, newline="", encoding="utf-8") as f:
        picked = list(csv.DictReader(f))
    for i, r in enumerate(picked, start=2):
        kind, a, b = r["kind"].strip(), r["a"].strip(), r["b"].strip()
        where = "picked.csv line %d (%s)" % (i, r.get("note") or "%s v %s" % (a, b))
        if kind == "country":
            ta, tb = d.slugs.get(a), d.slugs.get(b)
            if not ta or not tb or "international" not in (ta["team_type"], tb["team_type"]):
                rejected.append((where, "unknown international team slug"))
                continue
            if ta["gender"] != tb["gender"]:
                rejected.append((where, "a men's team v a women's team"))
                continue
            ga = " women" if ta["gender"] == "female" else ""
            add(kind, a, b, ta["name"] + ga, tb["name"] + ga, ta["gender"], "picked", "")
            continue
        if kind not in ("matchup", "comparison"):
            rejected.append((where, "kind must be matchup, comparison or country"))
            continue
        ids = [s.rsplit("-", 1)[-1] for s in (a, b)]
        if not all(x in d.by_id for x in ids):
            rejected.append((where, "unknown player id (copy the slug from the player's page)"))
            continue
        pa, pb = d.player(ids[0]), d.player(ids[1])
        bad = [n + ": " + w for n, w in ((pa["name"], d.problem(pa, False)),
                                         (pb["name"], d.problem(pb, False))) if w]
        if bad:
            rejected.append((where, "; ".join(bad)))
            continue
        if d.team[pa["player_key"]][1] != d.team[pb["player_key"]][1]:
            rejected.append((where, "a man v a woman"))
            continue
        why = ""
        if kind == "matchup":
            scopes = pairs.get(tuple(sorted((pa["player_key"], pb["player_key"]))), {})
            if max((s["balls"] for s in scopes.values()), default=0) < PICKED_MIN_BALLS:
                rejected.append((where, "fewer than %d balls between them in any format"
                                 % PICKED_MIN_BALLS))
                continue
            why = matchup_why(scopes)
        na, nb = d.full_names([pa["player_id"], pb["player_id"]])
        if not add(kind, d.slug(pa), d.slug(pb), na, nb, d.team[pa["player_key"]][1], "picked",
                   why):
            rejected.append((where, "listed twice"))

    # ── 2. Matchups from the data: the longest duels per gender and format ──
    used = defaultdict(int)
    buckets = defaultdict(list)
    for k, scopes in pairs.items():
        best = max(scopes, key=lambda s: scopes[s]["balls"])
        pa, pb = d.by_key[k[0]], d.by_key[k[1]]
        if scopes[best]["balls"] < MATCHUP_BAR[best] or d.problem(pa, True) or d.problem(pb, True):
            continue
        g = d.team[pa["player_key"]][1]
        if g == d.team[pb["player_key"]][1]:
            buckets[(g, best)].append((-scopes[best]["balls"], pa["player_id"], pb["player_id"],
                                       scopes))
    for key, quota in MATCHUP_QUOTA.items():
        n = 0
        for _, ia, ib, scopes in sorted(buckets[key]):
            if n >= quota:
                break
            if used[ia] >= PER_PLAYER or used[ib] >= PER_PLAYER:
                continue
            pa, pb = d.player(ia), d.player(ib)
            na, nb = d.full_names([ia, ib])
            if add("matchup", d.slug(pa), d.slug(pb), na, nb, key[0], "data",
                   matchup_why(scopes)):
                used[ia] += 1
                used[ib] += 1
                n += 1

    # ── 3. Comparisons: the leaders of the last five years, paired in order ──
    for (g, scope, kind), quota in COMPARE_QUOTA.items():
        metric = "runs" if kind == "batting" else "wickets"
        board = matches_service.leaderboard(d.db, kind, metric, scope, g, since, None, 40)[0]
        board = [r for r in board if r["team"] in FULL_MEMBERS and (r["team"], g) != WITHHELD
                 and not d.problem(d.player(r["player_id"]), True)]
        n, i = 0, 0
        while n < quota and i + 1 < len(board):
            a, b = board[i], board[i + 1]
            why = "%s %s since %s: #%d v #%d" % (LABEL[scope], metric, since[:4], i + 1, i + 2)
            if add("comparison", a["slug"], b["slug"], a["full_name"], b["full_name"], g, "data",
                   why):
                n += 1
            i += 2

    # ── 4. Countries: the most-played Full Member rivalries ──
    for g, quota in COUNTRY_QUOTA.items():
        met = d.db.all(
            "SELECT MIN(team1_key, team2_key) AS x, MAX(team1_key, team2_key) AS y,"
            " COUNT(*) AS n, SUM(format_key = 'TEST') AS t, SUM(format_key = 'ODI') AS o,"
            " SUM(format_key = 'T20I') AS i FROM matches"
            " WHERE format_key IN ('ODI', 'TEST', 'T20I') AND team_type = 'international'"
            " AND gender = ? GROUP BY 1, 2 ORDER BY n DESC", (g,))
        n = 0
        for r in met:
            sx, sy = d.slugs.slug(r["x"]), d.slugs.slug(r["y"])
            tx, ty = d.slugs.get(sx), d.slugs.get(sy)
            why = ", ".join("%d %s" % (c, w) for c, w in ((r["t"], "Tests"), (r["o"], "ODIs"),
                                                          (r["i"], "T20Is")) if c)
            for row in rows:                    # a picked pair: fill in the numbers
                if row["path"] == path(sx, sy) and not row["why"]:
                    row["why"] = why
            if n >= quota or not (tx["name"] in FULL_MEMBERS and ty["name"] in FULL_MEMBERS) or \
                    (g == WITHHELD[1] and WITHHELD[0] in (tx["name"], ty["name"])):
                continue
            ga = " women" if g == "female" else ""
            if add("country", sx, sy, tx["name"] + ga, ty["name"] + ga, g, "data", why):
                n += 1

    order = {"matchup": 0, "comparison": 1, "country": 2}
    rows.sort(key=lambda r: (order[r["kind"]], r["gender"] != "male", r["source"] != "picked"))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    count = defaultdict(int)
    for r in rows:
        count[(r["kind"], r["source"])] += 1
    print("data as of %s; comparisons use %s onwards" % (as_of, since))
    for kind in order:
        print("  %-10s picked %3d  data %3d" % (kind, count[(kind, "picked")],
                                                count[(kind, "data")]))
    print("  total      %d pairs -> %s" % (len(rows), os.path.relpath(OUT, os.getcwd())))
    for where, why in rejected:
        print("NOT USED %s: %s" % (where, why))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
