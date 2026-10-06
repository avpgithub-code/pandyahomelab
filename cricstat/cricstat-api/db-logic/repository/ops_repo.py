"""Operations data for the admin page: build history, CD-pull log, data shape, file sizes.
Everything is read-only; logs come from cricstat/logs mounted read-only."""
import glob
import os
import re
from typing import Dict, List

from db_logic.repository.db import ServingDB

_CD_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) (\S+) (.*)$")


def builds(db: ServingDB, limit: int = 15) -> List[dict]:
    return db.all("SELECT build_id, built_at, mode, raw_run_id, matches, deliveries, data_as_of,"
                  " status, notes FROM build_info ORDER BY build_id DESC LIMIT ?", (limit,))


def matches_per_year(db: ServingDB) -> List[dict]:
    return db.all("SELECT substr(start_date, 1, 4) AS year, format_key, gender, COUNT(*) AS matches"
                  " FROM matches GROUP BY 1, 2, 3 ORDER BY 1")


def scope_matches_per_year(db: ServingDB, scope: str, gender: str) -> Dict[int, int]:
    """{year: matches} for a format key or competition slug (coverage density hints)."""
    return {int(r["year"]): r["matches"] for r in db.all(
        "SELECT substr(m.start_date, 1, 4) AS year, COUNT(*) AS matches"
        " FROM matches m LEFT JOIN competitions c USING (competition_key)"
        " WHERE m.gender = ? AND (m.format_key = ? OR c.competition_slug = ?) GROUP BY 1",
        (gender, scope, scope))}


def table_counts(db: ServingDB) -> Dict[str, int]:
    one = db.one("SELECT (SELECT COUNT(*) FROM matches) AS matches,"
                 " (SELECT COUNT(*) FROM players) AS players,"
                 " (SELECT COUNT(*) FROM teams) AS teams,"
                 " (SELECT COUNT(*) FROM venues) AS venues,"
                 " (SELECT COUNT(*) FROM competitions) AS competitions,"
                 " (SELECT COUNT(*) FROM player_career) AS career_rows,"
                 " (SELECT COUNT(*) FROM batting_innings) AS batting_innings,"
                 " (SELECT COUNT(*) FROM bowling_innings) AS bowling_innings")
    return dict(one or {})


def cricinfo_ids(db: ServingDB, player_ids: List[str]) -> Dict[str, List[str]]:
    if not player_ids:
        return {}
    marks = ", ".join("?" * len(player_ids))
    out: Dict[str, List[str]] = {}
    for r in db.all("SELECT p.player_id, e.external_id FROM player_external_ids e"
                    " JOIN players p USING (player_key)"
                    " WHERE e.source = 'cricinfo' AND p.player_id IN (%s)" % marks, player_ids):
        out.setdefault(r["player_id"], []).append(r["external_id"])
    return out


def file_sizes(paths: Dict[str, str]) -> Dict[str, int]:
    out = {}
    for label, path in paths.items():
        try:
            out[label] = os.path.getsize(path)
        except OSError:
            out[label] = None
    return out


def cd_pull_runs(log_dir: str, days: int = 14) -> List[dict]:
    """Group cd-YYYYMMDD.log lines into runs (lines within the same minute), newest first."""
    lines = []
    for path in sorted(glob.glob(os.path.join(log_dir, "cd-*.log")))[-days:]:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = _CD_LINE.match(line.strip())
                    if m:
                        lines.append({"at": m.group(1), "word": m.group(2), "text": m.group(3)})
        except OSError:
            continue
    runs: List[dict] = []
    for ln in lines:
        if runs and runs[-1]["at"][:16] == ln["at"][:16]:
            runs[-1]["lines"].append("%s %s" % (ln["word"], ln["text"]))
            runs[-1]["failed"] = runs[-1]["failed"] or ln["word"] == "FAIL"
        else:
            runs.append({"at": ln["at"], "lines": ["%s %s" % (ln["word"], ln["text"])],
                         "failed": ln["word"] == "FAIL"})
    return list(reversed(runs))
