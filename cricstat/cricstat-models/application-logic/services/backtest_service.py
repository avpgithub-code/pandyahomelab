"""P1.2: tune Elo on past data only and run backtest A (P1 plan §2.2, §3).

    grid      every parameter combination is replayed once over all men's ODIs (one step ahead);
              each window then picks the combination with the lowest log loss on its own training
              matches (2007-01-01 up to the window's cutoff). 2003–06 is burn-in.
    test A    walk-forward over every match since 2019-01-01: each calendar year is predicted with
              the parameters chosen on the years before it. Baselines: coin flip and the 24-month
              win-rate model (also refitted each year).
    windows   'wc2019' (cutoff 2019-05-30), 'wc2023' (2023-10-05) for P1.3's tournament backtests,
              'current' (all data) = the candidate parameters for the live forecast.
Writes a report folder and logs one MLflow run (experiment cricstat-elo-backtest). The whole grid is
an artifact (grid.csv), not 2,000 child runs.
"""
import bisect
import csv
import datetime
import itertools
import json
import math
import os
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple

from application_logic.models import baselines, elo, metrics
from application_logic.services import data_service
from db_logic.tracking.mlflow_rest import MlflowClient, MlflowError
from shared.logger import get_logger

log = get_logger("backtest")

EXPERIMENT = "cricstat-elo-backtest"
TRAIN_FROM = "2007-01-01"
TEST_FROM = "2019-01-01"
WINDOWS = {"wc2019": "2019-05-30", "wc2023": "2023-10-05"}
GRID = {"k": (12, 16, 20, 24, 32, 40), "home": (0, 30, 45, 60, 75, 90, 120),
        "margin": (False, True), "regress": (0.0, 0.05, 0.1, 0.2),
        "delta": (0, 200, 300, 400, 500, 600)}
# Publish bar §3.3 gates 1 and 2 (test A).
SLOPE_RANGE = (0.8, 1.2)
BIN_TOLERANCE, BIN_MIN_N = 0.08, 30


def full_members(path: str) -> Dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return {r["team"]: r["full_member_from"] for r in csv.DictReader(f)}


def _ll(p: float, y: float) -> float:
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


class Grid:
    """All replays: params list, the scored match indices (same for every replay) and P(team1)."""

    def __init__(self, c: elo.Compiled):
        self.c = c
        self.params = [elo.EloParams(*g) for g in itertools.product(*GRID.values())]
        self.idx: List[int] = []
        self.probs: List[List[float]] = []
        for p in self.params:
            preds, _, _ = elo.run(c, p)
            if not self.idx:
                self.idx = [i for i, _ in preds]
            self.probs.append([q for _, q in preds])
        self.dates = [c.matches[i].date for i in self.idx]
        self.ys = [c.matches[i].s1 for i in self.idx]
        # Prefix sums of log loss per parameter set: any date window is O(1).
        self.prefix = []
        for probs in self.probs:
            acc, run_sum = [0.0], 0.0
            for p, y in zip(probs, self.ys):
                run_sum += _ll(p, y)
                acc.append(run_sum)
            self.prefix.append(acc)

    def train_loss(self, g: int, until: str) -> Tuple[float, int]:
        lo = bisect.bisect_left(self.dates, TRAIN_FROM)
        hi = bisect.bisect_left(self.dates, until)
        return (self.prefix[g][hi] - self.prefix[g][lo]) / (hi - lo), hi - lo

    def best(self, until: str) -> Tuple[int, float, int]:
        scored = [(self.train_loss(g, until), g) for g in range(len(self.params))]
        (loss, n), g = min(scored)
        return g, loss, n

    def ranking(self, until: str, top: int = 10) -> List[Dict[str, object]]:
        scored = sorted((self.train_loss(g, until)[0], g) for g in range(len(self.params)))
        return [dict(self.params[g].as_dict(), train_log_loss=round(loss, 5))
                for loss, g in scored[:top]]


def _subset_summary(p: Sequence[float], y: Sequence[float], mask: Sequence[bool]) -> Dict:
    pp = [a for a, m in zip(p, mask) if m]
    yy = [b for b, m in zip(y, mask) if m]
    return metrics.summary(pp, yy) if pp else {"n": 0}


def _gates(elo_s: Dict, base: Dict[str, Dict]) -> Dict[str, object]:
    beats = all(elo_s["log_loss"] < b["log_loss"] and elo_s["brier"] < b["brier"]
                for b in base.values())
    slope_ok = SLOPE_RANGE[0] <= elo_s["calibration_slope"] <= SLOPE_RANGE[1]
    bad_bins = [b for b in elo_s["reliability"]
                if b["n"] >= BIN_MIN_N and abs(b["predicted"] - b["observed"]) > BIN_TOLERANCE]
    return {"gate1_beats_baselines": beats, "gate2_slope_in_range": slope_ok,
            "gate2_bins_within_tolerance": not bad_bins, "gate2_bins_off": bad_bins,
            "test_a_passes": beats and slope_ok and not bad_bins}


def run(cfg, log_to_mlflow: bool = True, out_root: Optional[str] = None) -> Dict[str, object]:
    rows, data_rep = data_service.load_matches(cfg)
    fm = full_members(cfg.FULL_MEMBERS)
    c = elo.compile_matches(rows, fm)
    grid = Grid(c)
    log.info("grid: %d parameter sets x %d scored matches", len(grid.params), len(grid.idx))

    # -- walk-forward test A ------------------------------------------------------------------
    feats = baselines.win_rate_features(c)
    years = sorted({d[:4] for d in grid.dates if d >= TEST_FROM})
    test_rows, chosen = [], {}
    for y in years:
        g, loss, n = grid.best("%s-01-01" % y)
        chosen[y] = dict(grid.params[g].as_dict(), train_log_loss=round(loss, 5), train_n=n)
        train = [i for i in feats if TRAIN_FROM <= c.matches[i].date < "%s-01-01" % y]
        w = baselines.fit_win_rate(c, feats, train)
        for j, (i, d) in enumerate(zip(grid.idx, grid.dates)):
            if d[:4] != y:
                continue
            m = c.matches[i]
            both_full = all(c.teams[t] in fm and fm[c.teams[t]] <= d for t in (m.t1, m.t2))
            test_rows.append({
                "match_key": m.key, "date": d, "team1": c.teams[m.t1], "team2": c.teams[m.t2],
                "home": m.h, "y": m.s1, "p_elo": grid.probs[g][j],
                "p_win_rate": baselines.predict_win_rate(w, feats[i]), "p_coin": 0.5,
                "both_full_members": both_full, "source": m.source})
    ys = [r["y"] for r in test_rows]
    elo_s = metrics.summary([r["p_elo"] for r in test_rows], ys)
    base = {"win_rate": metrics.summary([r["p_win_rate"] for r in test_rows], ys),
            "coin": metrics.summary([0.5] * len(ys), ys)}
    full_mask = [r["both_full_members"] for r in test_rows]
    afg_mask = ["Afghanistan" in (r["team1"], r["team2"]) for r in test_rows]
    by_year = {y: _subset_summary([r["p_elo"] for r in test_rows], ys,
                                  [r["date"][:4] == y for r in test_rows]) for y in years}

    # -- windows: tuned on data before each cutoff ---------------------------------------------
    last = max(m.date for m in c.matches)
    end = (datetime.date.fromisoformat(last) + datetime.timedelta(days=1)).isoformat()
    windows = {}
    for name, cutoff in list(WINDOWS.items()) + [("current", end)]:
        g, loss, n = grid.best(cutoff)
        p = grid.params[g]
        _, ratings, _ = elo.run(c, p, until=cutoff)
        table = sorted(((r, t) for t, r in zip(c.teams, ratings)), reverse=True)
        windows[name] = {"cutoff": cutoff, "params": p.as_dict(), "train_log_loss": loss,
                         "train_n": n, "top10_params": grid.ranking(cutoff),
                         "ratings": [{"team": t, "rating": round(r, 1)} for r, t in table]}

    report = {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": data_rep, "grid": {k: list(v) for k, v in GRID.items()},
        "grid_size": len(grid.params), "scored_matches": len(grid.idx),
        "test_a": {"from": TEST_FROM, "elo": elo_s, "baselines": base,
                   "elo_full_members_only": _subset_summary([r["p_elo"] for r in test_rows], ys,
                                                            full_mask),
                   "elo_with_afghanistan": _subset_summary([r["p_elo"] for r in test_rows], ys,
                                                           afg_mask),
                   "by_year": by_year, "params_by_year": chosen},
        "gates": _gates(elo_s, base), "windows": windows,
    }
    out = _write(cfg, report, grid, test_rows, out_root)
    report["report_dir"] = out
    if log_to_mlflow:
        report["mlflow"] = _log(cfg, report, out)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)
    return report


# -- outputs -----------------------------------------------------------------------------------
def _write(cfg, report, grid: Grid, test_rows, out_root) -> str:
    stamp = report["generated_at"].replace(":", "").replace("-", "")
    out = os.path.join(out_root or cfg.REPORT_DIR, "backtest-%s" % stamp)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "grid.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        cuts = [("wc2019", WINDOWS["wc2019"]), ("wc2023", WINDOWS["wc2023"]),
                ("current", report["windows"]["current"]["cutoff"])]
        w.writerow(list(GRID) + ["train_log_loss_%s" % n for n, _ in cuts])
        for g, p in enumerate(grid.params):
            w.writerow(list(p) + ["%.5f" % grid.train_loss(g, cut)[0] for _, cut in cuts])
    with open(os.path.join(out, "test_a_predictions.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(test_rows[0]), lineterminator="\n")
        w.writeheader()
        for r in test_rows:
            w.writerow(dict(r, p_elo="%.4f" % r["p_elo"], p_win_rate="%.4f" % r["p_win_rate"]))
    with open(os.path.join(out, "reliability.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["model", "bin", "n", "predicted", "observed"])
        for model, s in (("elo", report["test_a"]["elo"]),
                         ("win_rate", report["test_a"]["baselines"]["win_rate"])):
            for b in s["reliability"]:
                w.writerow([model, b["bin"], b["n"], "%.4f" % b["predicted"],
                            "%.4f" % b["observed"]])
    with open(os.path.join(out, "ratings_current.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "team", "rating"])
        for i, r in enumerate(report["windows"]["current"]["ratings"], start=1):
            w.writerow([i, r["team"], r["rating"]])
    with open(os.path.join(out, "reliability.svg"), "w", encoding="utf-8") as f:
        f.write(reliability_svg(report["test_a"]["elo"]["reliability"],
                                report["test_a"]["baselines"]["win_rate"]["reliability"],
                                report["test_a"]["elo"]["n"]))
    return out


def _git_sha() -> str:
    sha = os.getenv("CRICSTAT_GIT_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=os.path.dirname(os.path.abspath(__file__)),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _log(cfg, report, out) -> Dict[str, str]:
    client = MlflowClient(cfg.MLFLOW_URI)
    try:
        run = client.start_run(EXPERIMENT, "elo-backtest-%s" % report["generated_at"][:10], {
            "cricstat.step": "P1.2", "cricstat.git_sha": _git_sha(),
            "cricstat.data_as_of": report["data"]["data_as_of"],
            "cricstat.build_id": report["data"]["build_id"],
            "cricstat.supplement_rows": report["data"]["by_source"].get("supplement:wikipedia", 0),
            "mlflow.note.content": "Elo grid search + walk-forward backtest A (every men's ODI "
                                   "since 2019). Grid in grid.csv; chosen parameters per window "
                                   "below. See cricstat/docs/P1-predictor-plan.md §2-3."})
    except MlflowError as exc:
        log.warning("MLflow logging skipped: %s", exc)
        return {"error": str(exc)}
    t, cur = report["test_a"], report["windows"]["current"]
    params = {"grid_size": report["grid_size"], "train_from": TRAIN_FROM, "test_from": TEST_FROM,
              "grid": json.dumps(report["grid"])}
    for name, wnd in report["windows"].items():
        for k, v in wnd["params"].items():
            params["%s.%s" % (name, k)] = v
    m = {"test_a.n": t["elo"]["n"]}
    for model, s in (("elo", t["elo"]), ("win_rate", t["baselines"]["win_rate"]),
                     ("coin", t["baselines"]["coin"]),
                     ("elo_full_members", t["elo_full_members_only"]),
                     ("elo_afghanistan", t["elo_with_afghanistan"])):
        for k in ("log_loss", "brier", "accuracy", "calibration_slope", "calibration_intercept"):
            if k in s:
                m["test_a.%s.%s" % (model, k)] = s[k]
    for name, wnd in report["windows"].items():
        m["%s.train_log_loss" % name] = wnd["train_log_loss"]
    m["gates.test_a_passes"] = 1.0 if report["gates"]["test_a_passes"] else 0.0
    m["current.top_rating"] = cur["ratings"][0]["rating"]
    client.log_batch(run["run_id"], params, m)
    for name in ("grid.csv", "test_a_predictions.csv", "reliability.csv", "reliability.svg",
                 "ratings_current.csv"):
        client.log_artifact(run, os.path.join(out, name))
    client.end_run(run["run_id"])
    return {"run_id": run["run_id"], "experiment_id": run["experiment_id"]}


def reliability_svg(elo_bins: List[Dict], base_bins: List[Dict], n: int) -> str:
    """Reliability diagram: predicted (x) vs observed (y) win rate of the favourite, per bin.
    Two series (validated categorical slots 1-2), legend + direct labels, <title> hover text."""
    W, H, L, R, T, B = 480, 400, 56, 120, 40, 48
    sx = lambda v: L + (v - 0.5) / 0.5 * (W - L - R)              # noqa: E731
    sy = lambda v: H - B - (v - 0.5) / 0.5 * (H - T - B)          # noqa: E731
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"'
           ' font-family="system-ui, sans-serif" font-size="12">' % (W, H, W, H),
           '<rect width="100%" height="100%" fill="#fcfcfb"/>',
           '<text x="%d" y="22" fill="#0b0b0b" font-size="14" font-weight="600">Backtest A'
           ' reliability (%d matches since 2019)</text>' % (L, n)]
    for v in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#e6e5e0"/>'
                   % (L, sy(v), W - R, sy(v)))
        out.append('<text x="%d" y="%.1f" fill="#52514e" text-anchor="end">%.0f%%</text>'
                   % (L - 6, sy(v) + 4, v * 100))
        out.append('<text x="%.1f" y="%d" fill="#52514e" text-anchor="middle">%.0f%%</text>'
                   % (sx(v), H - B + 18, v * 100))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#52514e"'
               ' stroke-dasharray="4 4" stroke-width="1"/>' % (sx(.5), sy(.5), sx(1), sy(1)))
    out.append('<text x="%.1f" y="%.1f" fill="#52514e">perfect</text>' % (sx(.97) - 40, sy(1) - 6))
    out.append('<text x="%.1f" y="%d" fill="#52514e" text-anchor="middle">Predicted chance for'
               ' the favourite</text>' % ((L + W - R) / 2, H - 10))
    out.append('<text transform="translate(16 %.1f) rotate(-90)" fill="#52514e"'
               ' text-anchor="middle">Observed win rate</text>' % ((T + H - B) / 2))
    for bins, colour, label in ((base_bins, "#eb6834", "Win-rate baseline"),
                                (elo_bins, "#2a78d6", "Elo")):
        pts = [(sx(b["predicted"]), sy(min(max(b["observed"], 0.5), 1.0)), b) for b in bins]
        out.append('<polyline fill="none" stroke="%s" stroke-width="2" points="%s"/>'
                   % (colour, " ".join("%.1f,%.1f" % (x, y) for x, y, _ in pts)))
        for x, y, b in pts:
            out.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s" stroke="#fcfcfb"'
                       ' stroke-width="2"><title>%s, bin %s: predicted %.1f%%, observed %.1f%%,'
                       ' %d matches</title></circle>'
                       % (x, y, colour, label, b["bin"], b["predicted"] * 100,
                          b["observed"] * 100, b["n"]))
        if pts:
            x, y, _ = pts[-1]
            ly = min(max(y - 10, T + 12), H - B - 8)     # above the point, inside the plot
            out.append('<text x="%.1f" y="%.1f" fill="#0b0b0b">%s</text>' % (x + 8, ly, label))
    for i, (colour, label) in enumerate((("#2a78d6", "Elo"), ("#eb6834", "Win-rate baseline"))):
        y = T + 8 + i * 18
        out.append('<rect x="%d" y="%d" width="12" height="3" rx="1" fill="%s"/>'
                   % (W - R + 12, y, colour))
        out.append('<text x="%d" y="%d" fill="#0b0b0b">%s</text>' % (W - R + 30, y + 5, label))
    out.append("</svg>")
    return "\n".join(out)
