"""Golden-figure set (F4 §3): our computed figures next to reference figures read by hand.

Reads docs/validation/golden-selection.csv (who and which scopes), queries the live serving DB
read-only, and (re)writes docs/validation/golden-figures.csv. Columns the user fills (reference,
source, checked_on, explanation) are kept across runs, keyed by (id, scope, metric). Once
references exist, any unexplained difference fails the run (exit 2).

Teams are compared from TEAM_FROM (fully covered) up to the data's latest date, so the window
moves forward with every build; player careers are compared whole. Because both keep growing, the
first run after a reference is entered snapshots `ours_at_check` and `mat_at_check`; once that
player's or team's Mat changes, the row turns 'stale' (re-check, not a failure). A figure that
changes while Mat does not is a regression and fails. coverage_note flags careers that begin
before the data is dense.
"""
import csv
import os
import sqlite3
import time
from typing import Dict, List

from application_logic.quality import golden
from db_logic.repository import golden_store
from shared.exceptions import DataQualityError, PipelineError
from shared.logger import get_logger

log = get_logger("golden")
TEAM_FROM = "2016-01-01"
COLUMNS = ["kind", "name", "id", "gender", "scope", "window", "metric", "ours", "reference",
           "status", "source", "checked_on", "explanation", "ours_at_check", "mat_at_check",
           "coverage_note", "why"]
USER_COLUMNS = ("reference", "source", "checked_on", "explanation")
SNAPSHOT = ("ours_at_check", "mat_at_check")

def _read(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run(serving_db: str, validation_dir: str) -> Dict[str, object]:
    t0 = time.time()
    sel_path = os.path.join(validation_dir, "golden-selection.csv")
    out_path = os.path.join(validation_dir, "golden-figures.csv")
    selection = _read(sel_path)
    if not selection:
        raise PipelineError("no golden selection at %s" % sel_path)
    if not os.path.exists(serving_db):
        raise PipelineError("serving DB not found: %s" % serving_db)
    kept = {(r["id"], r["scope"], r["metric"]): r for r in _read(out_path)}

    conn = sqlite3.connect("file:%s?mode=ro" % serving_db, uri=True)
    try:
        build = conn.execute("SELECT build_id, data_as_of FROM build_info"
                             " WHERE status = 'success' ORDER BY build_id DESC LIMIT 1").fetchone()
        rows, missing, dense = [], [], {}
        window_to = build[1] if build else time.strftime("%Y-%m-%d", time.gmtime())
        for sel in selection:
            for scope in sel["scopes"].split(";"):
                scope = scope.strip()
                if sel["kind"] == "team":
                    name, gender, team_type = sel["id"].split("|")
                    rec = golden_store.team_record(conn, name, gender, team_type, scope,
                                                   TEAM_FROM, window_to)
                    if not rec["matches"]:
                        missing.append("%s %s" % (sel["name"], scope))
                    figures, window = golden.team_rows(rec), "%s..%s" % (TEAM_FROM, window_to)
                    note = ""
                else:
                    fig = golden_store.player_figures(conn, sel["id"], scope)
                    if not fig:
                        missing.append("%s %s" % (sel["name"], scope))
                    figures, window = golden.player_rows(sel["role"], fig), "career"
                    key = (scope, sel["gender"])
                    if key not in dense:
                        per_year = golden_store.matches_per_year(conn, scope, sel["gender"])
                        dense[key] = (golden.dense_from(per_year, int(time.strftime(
                            "%Y", time.gmtime()))), min(per_year) if per_year else None)
                    label = "%s %s" % ("women's" if sel["gender"] == "female" else "men's", scope)
                    note = golden.coverage_note(fig.get("first_date"), dense[key][0], label,
                                                dense[key][1])
                mat_now = dict(figures).get("Mat", "")
                for metric, ours in figures:
                    prev = kept.get((sel["id"], scope, metric), {})
                    row = dict(kind=sel["kind"], name=sel["name"], id=sel["id"],
                               gender=sel["gender"], scope=scope, window=window, metric=metric,
                               ours=ours, coverage_note=note, why=sel.get("why", ""))
                    row.update({c: prev.get(c, "") for c in USER_COLUMNS + SNAPSHOT})
                    if row["reference"].strip() and not row["mat_at_check"]:
                        row.update(ours_at_check=ours, mat_at_check=mat_now)
                    elif not row["reference"].strip():
                        row.update(ours_at_check="", mat_at_check="")
                    row["status"] = golden.status(ours, row["reference"], row["explanation"],
                                                  mat_now, row["mat_at_check"])
                    rows.append(row)
    finally:
        conn.close()

    tmp = out_path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out_path)
    counts = {s: sum(1 for r in rows if r["status"] == s)
              for s in ("match", "explained", "stale", "DIFF")}
    summary = {"mode": "golden", "build_id": build[0] if build else None,
               "data_as_of": build[1] if build else None, "rows": len(rows),
               "players": sum(1 for s in selection if s["kind"] == "player"),
               "teams": sum(1 for s in selection if s["kind"] == "team"),
               "window_to": window_to,
               "with_reference": sum(counts.values()), "matches": counts["match"],
               "explained": counts["explained"], "stale": counts["stale"],
               "unexplained": counts["DIFF"],
               "missing": missing, "output": out_path,
               "duration_s": round(time.time() - t0, 1)}
    if counts["DIFF"]:
        diffs = ["%s %s %s: ours %s, reference %s" % (r["name"], r["scope"], r["metric"],
                                                       r["ours"], r["reference"])
                 for r in rows if r["status"] == "DIFF"]
        summary.update(status="dq_failed", diffs=diffs[:20])
        exc = DataQualityError("%d unexplained golden-figure differences" % len(diffs), diffs)
        exc.summary = summary
        raise exc
    summary["status"] = "success"
    log.info("golden: %d rows, %d with a reference (%d match, %d explained)", len(rows),
             summary["with_reference"], counts["match"], counts["explained"])
    return summary

