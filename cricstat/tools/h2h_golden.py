"""Golden head-to-heads (docs/h2h-plan.md §6, step H2): our numbers for a fixed set of famous
batter-v-bowler duels and country records, written to docs/validation/h2h-golden.csv for the owner to
check against published figures. Re-running keeps the reference/source/checked_on/explanation columns.

    python3 cricstat/tools/h2h_golden.py [--db cricstat/data/db/cricstat.sqlite]

Matchups come from the `matchups` mart when the DB has it, otherwise from the same rules applied to
deliveries directly (R3 balls faced, runs off the bat, outs credited to the bowler, no super overs).
"""
import argparse
import csv
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
CRICSTAT = os.path.dirname(HERE)
OUT = os.path.join(CRICSTAT, "docs", "validation", "h2h-golden.csv")

# (batter, bowler, scope): Cricsheet names; famous duels that are often quoted in print.
MATCHUPS = [
    ("DA Warner", "SCJ Broad", "TEST"), ("BA Stokes", "R Ashwin", "TEST"),
    ("SR Tendulkar", "JM Anderson", "TEST"), ("V Kohli", "JM Anderson", "TEST"),
    ("CA Pujara", "NM Lyon", "TEST"), ("DA Warner", "R Ashwin", "TEST"),
    ("SPD Smith", "JJ Bumrah", "TEST"), ("JE Root", "JJ Bumrah", "TEST"),
    ("V Kohli", "JR Hazlewood", "TEST"), ("V Kohli", "TG Southee", "ODI"),
    ("RG Sharma", "MA Starc", "ODI"), ("RG Sharma", "Shaheen Shah Afridi", "T20I"),
    ("S Mandhana", "S Ecclestone", "T20I"), ("S Mandhana", "EA Perry", "ODI"),
    ("H Kaur", "EA Perry", "ODI"),
]
# (team, opponent, gender, scope)
COUNTRIES = [
    ("India", "Australia", "male", "ODI"), ("India", "Pakistan", "male", "ODI"),
    ("Australia", "England", "male", "TEST"), ("India", "Australia", "male", "TEST"),
    ("India", "Australia", "female", "ODI"),
]
COLUMNS = ["kind", "pair", "gender", "scope", "metric", "ours", "our_period", "reference", "source",
           "checked_on", "explanation"]
KEEP = ("reference", "source", "checked_on", "explanation")

MATCHUP_SQL = """
SELECT SUM(d.wides = 0) AS balls, SUM(d.runs_batter) AS runs, COUNT(DISTINCT d.match_key) AS matches,
       MIN(m.start_date), MAX(m.start_date)
FROM deliveries d JOIN matches m USING (match_key)
JOIN innings i ON i.match_key = d.match_key AND i.innings_no = d.innings_no
WHERE m.has_deliveries = 1 AND m.format_key = ? AND i.is_super_over = 0
  AND d.batter_key = ? AND d.bowler_key = ?"""
OUTS_SQL = """
SELECT COUNT(*) FROM dismissals x JOIN matches m USING (match_key)
JOIN innings i ON i.match_key = x.match_key AND i.innings_no = x.innings_no
WHERE m.has_deliveries = 1 AND m.format_key = ? AND i.is_super_over = 0
  AND x.credited_to_bowler = 1 AND x.counts_as_out = 1 AND x.player_out_key = ? AND x.bowler_key = ?"""


def _key(conn, name):
    row = conn.execute("SELECT player_key FROM players WHERE name = ?", (name,)).fetchone()
    if not row:
        raise SystemExit("unknown player: %s" % name)
    return row[0]


def matchup(conn, batter, bowler, scope, have_mart):
    a, b = _key(conn, batter), _key(conn, bowler)
    if have_mart:
        r = conn.execute("SELECT balls, runs, outs, matches, first_date, last_date FROM matchups"
                         " WHERE scope = ? AND batter_key = ? AND bowler_key = ?",
                         (scope, a, b)).fetchone()
        return r or (0, 0, 0, 0, None, None)
    balls, runs, matches, first, last = conn.execute(MATCHUP_SQL, (scope, a, b)).fetchone()
    outs = conn.execute(OUTS_SQL, (scope, a, b)).fetchone()[0]
    return balls or 0, runs or 0, outs, matches, first, last


def country(conn, team, opp, gender, scope):
    return conn.execute(
        "SELECT COUNT(*), SUM(r.outcome = 'won'), SUM(r.outcome = 'lost'), SUM(r.outcome = 'tied'),"
        " SUM(r.outcome = 'drawn'), SUM(r.outcome = 'no_result'), MIN(r.start_date), MAX(r.start_date)"
        " FROM team_results r JOIN teams t ON t.team_key = r.team_key"
        " JOIN teams o ON o.team_key = r.opponent_key"
        " WHERE t.name = ? AND o.name = ? AND r.gender = ? AND r.format_key = ?"
        " AND t.team_type = 'international'", (team, opp, gender, scope)).fetchone()


def rows(conn):
    have_mart = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'matchups'").fetchone()
    for batter, bowler, scope in MATCHUPS:
        balls, runs, outs, matches, first, last = matchup(conn, batter, bowler, scope, have_mart)
        period = "%s to %s (%d matches)" % (first, last, matches) if first else "no meetings"
        for metric, value in (("dismissals", outs), ("runs", runs), ("balls", balls)):
            yield {"kind": "matchup", "pair": "%s v %s" % (batter, bowler), "gender": "",
                   "scope": scope, "metric": metric, "ours": value, "our_period": period}
    for team, opp, gender, scope in COUNTRIES:
        n, won, lost, tied, drawn, nr, first, last = country(conn, team, opp, gender, scope)
        period = "%s to %s" % (first, last)
        metrics = [("matches", n), ("won", won), ("lost", lost), ("tied", tied)]
        metrics.append(("drawn", drawn) if scope == "TEST" else ("no_result", nr))
        for metric, value in metrics:
            yield {"kind": "country", "pair": "%s v %s" % (team, opp), "gender": gender,
                   "scope": scope, "metric": metric, "ours": value or 0, "our_period": period}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(CRICSTAT, "data", "db", "cricstat.sqlite"))
    args = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro&immutable=1" % args.db, uri=True)
    old = {}
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                old[(r["pair"], r["gender"], r["scope"], r["metric"])] = r
    out = []
    for r in rows(conn):
        prev = old.get((r["pair"], r["gender"], r["scope"], r["metric"]), {})
        out.append(dict(r, **{k: prev.get(k, "") for k in KEEP}))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    print("%d rows written to %s" % (len(out), OUT))


if __name__ == "__main__":
    main()
