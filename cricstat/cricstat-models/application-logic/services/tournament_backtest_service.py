"""P1.3: tournament backtests B and C, the replay check, the publish gates and the first 2027
forecast (P1 plan §2.4, §3).

    test B   every World Cup 2019 / 2023 match, predicted with the ratings frozen on the eve of the
             tournament (parameters tuned on data before it), against the frozen win-rate baseline
    test C   the pre-tournament simulation (no results known) vs what happened: Brier per stage over
             all teams and the probability given to the champion. Reported, not a gate (2 events)
    replay   the same tournaments with every real result plugged in must reproduce the real
             semi-finalists and champion (gate 4, with the per-simulation sum checks)
    2027     the current ratings and parameters, rating drift sigma(days to the start), per-country
             October–November no-result rates, the Qualifier slots drawn from the candidates
Gates 1–2 come from backtest A (backtest_service); gate 3 is test B; gate 4 the replay + sums;
gate 5 is the owner's sanity check of the 2027 table (sanity_sheet.md). One MLflow run holds
everything.
"""
import csv
import datetime
import json
import math
import os
from typing import Dict, List, Optional

from application_logic.models import baselines, elo, metrics, simulator, uncertainty
from application_logic.services import (
    backtest_service,
    conditions_service,
    data_service,
    tournament_service,
)
from db_logic.repository import serving_reader
from db_logic.repository import tournament_store as tstore
from db_logic.tracking.mlflow_rest import MlflowClient, MlflowError
from shared.logger import get_logger

log = get_logger("tournament-backtest")

PAST = {"wc2019": {"window": "wc2019", "months": (5, 6, 7)},
        "wc2023": {"window": "wc2023", "months": (10, 11)}}
N_BACKTEST = 20000
N_FORECAST = 50000
SEED = 2027


def _ratings(c: elo.Compiled, p: elo.EloParams, until: str) -> Dict[str, float]:
    _, r, _ = elo.run(c, p, until=until)
    return dict(zip(c.teams, r))


def _params(d: Dict[str, object]) -> elo.EloParams:
    return elo.EloParams(**{k: d[k] for k in elo.EloParams._fields})


def _win_rate_at(c: elo.Compiled, team: str, until: str) -> float:
    lo = (datetime.date.fromisoformat(until) - datetime.timedelta(days=baselines.WINDOW_DAYS)
          ).isoformat()
    t = c.teams.index(team) if team in c.teams else -1
    s = n = 0.0
    for m in c.matches:
        if lo <= m.date < until and m.s1 is not None and t in (m.t1, m.t2):
            s += m.s1 if m.t1 == t else 1 - m.s1
            n += 1
    return (s + 1.0) / (n + 2.0)


def _stage_names(fmt) -> List[str]:
    return [st["id"] for st in fmt["stages"]]


def test_b(c, fixtures, ratings, home, w, until) -> List[Dict[str, object]]:
    out = []
    wr = {}
    for f in fixtures:
        if f["has_play"] != "1" or f["result"] not in ("win", "tie"):
            continue
        a, b = f["team1"], f["team2"]
        h = 1 if f["venue_country"] == a else -1 if f["venue_country"] == b else 0
        for t in (a, b):
            if t not in wr:
                wr[t] = _win_rate_at(c, t, until)
        x = math.log(wr[a] / (1 - wr[a])) - math.log(wr[b] / (1 - wr[b]))
        y = 0.5 if f["result"] == "tie" else (1.0 if f["winner"] == a else 0.0)
        out.append({"match_no": f["match_no"], "date": f["date"], "team1": a, "team2": b,
                    "stage": f["stage"], "y": y,
                    "p_elo": elo.probability(ratings[a], ratings[b], home, h),
                    "p_win_rate": baselines.predict_win_rate(w, (x, h))})
    return out


def test_c(fmt, fixtures, res: simulator.Result) -> Dict[str, object]:
    """Stage probabilities vs what happened, for every team in the tournament."""
    actual: Dict[str, set] = {}
    for f in fixtures:
        if f["stage"] != "league" and f["team1"]:
            actual.setdefault(f["stage"], set()).update((f["team1"], f["team2"]))
    final = [f for f in fixtures if f["stage"] == "final"][0]
    champion = final["winner"]
    teams = sorted(fmt["teams"])
    rows, brier = [], {}
    for t in teams:
        row = {"team": t}
        for st in ("semi", "final"):
            row["p_" + st] = res.stage_counts.get(t, {}).get(st, 0) / res.n
            row["actual_" + st] = int(t in actual.get(st, set()))
        row["p_champion"] = res.champion.get(t, 0) / res.n
        row["actual_champion"] = int(t == champion)
        rows.append(row)
    for st in ("semi", "final", "champion"):
        brier[st] = sum((r["p_" + st] - r["actual_" + st]) ** 2 for r in rows) / len(rows)
    p_ch = res.champion.get(champion, 0) / res.n
    return {"teams": rows, "brier": brier, "champion": champion, "p_champion": p_ch,
            "log_p_champion": math.log(max(p_ch, 1e-6)),
            "uniform_log_p_champion": math.log(1 / len(teams))}


def sums(res: simulator.Result) -> Dict[str, float]:
    tot: Dict[str, float] = {}
    for v in res.stage_counts.values():
        for st, n in v.items():
            tot[st] = tot.get(st, 0) + n / res.n
    tot["champion"] = sum(res.champion.values()) / res.n
    return {k: round(v, 6) for k, v in tot.items()}


def run(cfg, log_to_mlflow: bool = True, out_root: Optional[str] = None,
        n_backtest: int = N_BACKTEST, n_forecast: int = N_FORECAST) -> Dict[str, object]:
    a_rep = backtest_service.run(cfg, log_to_mlflow=False, out_root=out_root)   # test A, windows
    rows, data_rep = data_service.load_matches(cfg)
    fm = backtest_service.full_members(cfg.FULL_MEMBERS)
    c = elo.compile_matches(rows, fm)
    with serving_reader.connect(cfg.SERVING_DB) as conn:
        known = serving_reader.men_international_teams(conn) | {"Afghanistan"}
    odi = conditions_service.odi_rows(cfg)
    feats = baselines.win_rate_features(c)
    report: Dict[str, object] = {"generated_at": a_rep["generated_at"], "data": data_rep,
                                 "test_a": a_rep["test_a"], "gates_a": a_rep["gates"],
                                 "windows": a_rep["windows"], "tournaments": {}}
    pooled = []
    for tid, spec in PAST.items():
        fmt, fixtures = tournament_service.load(cfg, tid, known)
        wnd = a_rep["windows"][spec["window"]]
        p = _params(wnd["params"])
        until = wnd["cutoff"]
        ratings = _ratings(c, p, until)
        train = [i for i in feats if backtest_service.TRAIN_FROM <= c.matches[i].date < until]
        w = baselines.fit_win_rate(c, feats, train)
        b_rows = test_b(c, fixtures, ratings, p.home, w, until)
        pooled += b_rows
        cond = conditions_service.rates(odi, until, fmt["hosts"], spec["months"])
        sp = simulator.SimParams(home=p.home, k_update=p.k, sigma=0.0, nr=cond["by_country"],
                                 nr_default=cond["global"], tie=cond["tie"])
        t = simulator.Tournament(fmt, fixtures)
        pre = simulator.simulate(t, ratings, sp, n_backtest, SEED, use_known=False)
        frozen = simulator.simulate(t, ratings, sp._replace(k_update=0.0), n_backtest, SEED,
                                    use_known=False)
        replay = simulator.simulate(t, ratings, sp, 50, SEED, replay=True, use_known=True)
        semis = sorted(fmt["final_standings"]["L"][:4])
        rep_semis = sorted(k for k, v in replay.stage_counts.items() if v.get("semi") == replay.n)
        report["tournaments"][tid] = {
            "cutoff": until, "params": wnd["params"], "conditions": cond,
            "test_b": {"elo": metrics.summary([r["p_elo"] for r in b_rows],
                                              [r["y"] for r in b_rows]),
                       "win_rate": metrics.summary([r["p_win_rate"] for r in b_rows],
                                                   [r["y"] for r in b_rows])},
            "test_c": test_c(fmt, fixtures, pre),
            "test_c_without_in_tournament_updates": test_c(fmt, fixtures, frozen)["brier"],
            "sums": sums(pre),
            "replay": {"semi_finalists": rep_semis, "expected": semis,
                       "champion": replay.champion, "ok": rep_semis == semis and
                       replay.champion.get(test_c(fmt, fixtures, pre)["champion"]) == replay.n},
            "eve_ratings": sorted(({"team": t2, "rating": round(ratings[t2], 1)}
                                   for t2 in fmt["teams"]), key=lambda x: -x["rating"]),
            "b_rows": b_rows}
    ys = [r["y"] for r in pooled]
    test_b_pooled = {"elo": metrics.summary([r["p_elo"] for r in pooled], ys),
                     "win_rate": metrics.summary([r["p_win_rate"] for r in pooled], ys)}
    report["test_b_pooled"] = test_b_pooled
    report["forecast"] = forecast_2027(cfg, c, fm, a_rep, odi, known, n_forecast)
    g = dict(a_rep["gates"])
    g["gate3_test_b_not_worse"] = test_b_pooled["elo"]["log_loss"] <= \
        test_b_pooled["win_rate"]["log_loss"]
    g["gate4_replay_and_sums"] = all(v["replay"]["ok"] for v in report["tournaments"].values()) \
        and _sums_ok(report)
    g["gate5_owner_sanity_check"] = "pending"
    g["gates_1_to_4_pass"] = bool(g["test_a_passes"] and g["gate3_test_b_not_worse"] and
                                  g["gate4_replay_and_sums"])
    report["gates"] = g
    out = _write(cfg, report, out_root)
    report["report_dir"] = out
    if log_to_mlflow:
        report["mlflow"] = _log(cfg, report, out)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in report.items()}, f, indent=1, default=str)
    return report


def _sums_ok(report) -> bool:
    want = {"wc2019": {"league": 10, "semi": 4, "final": 2, "champion": 1},
            "wc2023": {"league": 10, "semi": 4, "final": 2, "champion": 1}}
    for tid, w in want.items():
        s = report["tournaments"][tid]["sums"]
        if any(abs(s.get(k, 0) - v) > 1e-9 for k, v in w.items()):
            return False
    s = report["forecast"]["sums"]
    return all(abs(s.get(k, 0) - v) < 1e-9 for k, v in
               {"super_series": 3, "group": 12, "super7": 7, "semi": 4, "final": 2,
                "champion": 1}.items())


def forecast_2027(cfg, c, fm, a_rep, odi, known, n) -> Dict[str, object]:
    fmt, fixtures = tournament_service.load(cfg, "wc2027", known)
    q = tstore.read_format(cfg.TOURNAMENTS_DIR, "wcq2027")
    wnd = a_rep["windows"]["current"]
    p = _params(wnd["params"])
    ratings = _ratings(c, p, wnd["cutoff"])
    data_as_of = a_rep["data"]["data_as_of"]
    days = (datetime.date.fromisoformat(fmt["start"]) -
            datetime.date.fromisoformat(data_as_of)).days
    a = uncertainty.fit(uncertainty.measure(c, p, fm))
    sig = uncertainty.sigma(a, max(days, 0))
    cond = conditions_service.rates(odi, wnd["cutoff"], fmt["hosts"], (10, 11))
    sp = simulator.SimParams(home=p.home, k_update=p.k, sigma=sig, nr=cond["by_country"],
                             nr_default=cond["global"], tie=cond["tie"])
    field = q.get("simulation_field") or []

    def draw(rng, noisy):
        order = simulator.round_robin_order(field, noisy, sp, rng)
        return {"Q%d" % (i + 1): t for i, t in enumerate(order[:4])}

    t = simulator.Tournament(fmt, fixtures)
    res = simulator.simulate(t, ratings, sp, n, SEED, slot_draw=draw if field else None)
    teams = sorted(set(fmt["teams"]) | set(field))
    table = []
    for tm in teams:
        cnt = res.stage_counts.get(tm, {})
        table.append({"team": tm, "rating": round(ratings.get(tm, float("nan")), 1),
                      "direct_qualifier": tm in fmt["teams"],
                      "p_world_cup": cnt.get("qualified", 0) / n if tm in field else 1.0,
                      "p_group_stage": cnt.get("group", 0) / n,
                      "p_super7": cnt.get("super7", 0) / n, "p_semi": cnt.get("semi", 0) / n,
                      "p_final": cnt.get("final", 0) / n,
                      "p_champion": res.champion.get(tm, 0) / n})
    table.sort(key=lambda r: (-r["p_champion"], -r["p_semi"], -r["p_world_cup"]))
    return {"n_simulations": n, "seed": SEED, "data_as_of": data_as_of, "days_to_start": days,
            "sigma": sig, "sigma_a": a, "params": wnd["params"], "conditions": cond,
            "qualifier_field": field, "sums": sums(res), "table": table}


# -- outputs -----------------------------------------------------------------------------------
def _write(cfg, report, out_root) -> str:
    stamp = report["generated_at"].replace(":", "").replace("-", "")
    out = os.path.join(out_root or cfg.REPORT_DIR, "tournament-backtest-%s" % stamp)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "test_b_predictions.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["tournament", "match_no", "date", "stage", "team1", "team2", "y", "p_elo",
                    "p_win_rate"])
        for tid, tr in report["tournaments"].items():
            for r in tr.pop("b_rows"):
                w.writerow([tid, r["match_no"], r["date"], r["stage"], r["team1"], r["team2"],
                            r["y"], "%.4f" % r["p_elo"], "%.4f" % r["p_win_rate"]])
    with open(os.path.join(out, "test_c_stage_probabilities.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["tournament", "team", "p_semi", "actual_semi", "p_final", "actual_final",
                    "p_champion", "actual_champion"])
        for tid, tr in report["tournaments"].items():
            for r in tr["test_c"]["teams"]:
                w.writerow([tid, r["team"], "%.4f" % r["p_semi"], r["actual_semi"],
                            "%.4f" % r["p_final"], r["actual_final"], "%.4f" % r["p_champion"],
                            r["actual_champion"]])
    fc = report["forecast"]
    with open(os.path.join(out, "wc2027_forecast.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fc["table"][0]), lineterminator="\n")
        w.writeheader()
        for r in fc["table"]:
            w.writerow({k: ("%.4f" % v if isinstance(v, float) and k != "rating" else v)
                        for k, v in r.items()})
    with open(os.path.join(out, "sanity_sheet.md"), "w", encoding="utf-8") as f:
        f.write(sanity_sheet(report))
    return out


def _pct(x: float) -> str:
    return "<0.1%" if 0 < x < 0.001 else "%.1f%%" % (100 * x)


def sanity_sheet(report) -> str:
    fc = report["forecast"]
    lines = ["# ODI World Cup 2027 forecast: sanity sheet (publish gate 5)", "",
             "Elo baseline, %d simulations, data to %s, %d days before the start; rating drift "
             "sigma = %.0f Elo points; parameters %s." % (
                 fc["n_simulations"], fc["data_as_of"], fc["days_to_start"], fc["sigma"],
                 fc["params"]), "",
             "| Team | Rating | Reach World Cup | Super 7 | Semi-final | Final | Champion |",
             "|---|---|---|---|---|---|---|"]
    for r in fc["table"]:
        lines.append("| %s | %.0f | %s | %s | %s | %s | %s |" % (
            r["team"], r["rating"], "direct" if r["direct_qualifier"] else _pct(r["p_world_cup"]),
            _pct(r["p_super7"]), _pct(r["p_semi"]), _pct(r["p_final"]), _pct(r["p_champion"])))
    return "\n".join(lines) + "\n"


NOTE = ("Backtests A (walk-forward), B (World Cup matches, eve ratings) and C (pre-tournament "
        "simulation), replay check, publish gates, first 2027 forecast.")


def _log(cfg, report, out) -> Dict[str, str]:
    client = MlflowClient(cfg.MLFLOW_URI)
    try:
        run = client.start_run(backtest_service.EXPERIMENT,
                               "tournament-backtest-%s" % report["generated_at"][:10], {
                                   "cricstat.step": "P1.3",
                                   "cricstat.git_sha": backtest_service._git_sha(),
                                   "cricstat.data_as_of": report["data"]["data_as_of"],
                                   "cricstat.build_id": report["data"]["build_id"],
                                   "mlflow.note.content": NOTE})
    except MlflowError as exc:
        log.warning("MLflow logging skipped: %s", exc)
        return {"error": str(exc)}
    m: Dict[str, float] = {}
    for model, s in (("elo", report["test_a"]["elo"]),
                     ("win_rate", report["test_a"]["baselines"]["win_rate"])):
        m["test_a.%s.log_loss" % model] = s["log_loss"]
        m["test_a.%s.brier" % model] = s["brier"]
    for model, s in report["test_b_pooled"].items():
        for k in ("log_loss", "brier", "accuracy"):
            m["test_b.%s.%s" % (model, k)] = s[k]
    for tid, tr in report["tournaments"].items():
        for st, v in tr["test_c"]["brier"].items():
            m["test_c.%s.brier_%s" % (tid, st)] = v
        m["test_c.%s.p_champion" % tid] = tr["test_c"]["p_champion"]
    for k, v in report["gates"].items():
        if isinstance(v, bool):
            m["gates.%s" % k] = 1.0 if v else 0.0
    fc = report["forecast"]
    for r in fc["table"][:14]:
        m["wc2027.p_champion.%s" % r["team"].replace(" ", "_")] = r["p_champion"]
    params = {"current.%s" % k: v for k, v in fc["params"].items()}
    params.update({"wc2027.n_simulations": fc["n_simulations"],
                   "wc2027.sigma": round(fc["sigma"], 2),
                   "wc2027.days_to_start": fc["days_to_start"],
                   "wc2027.qualifier_field": ", ".join(fc["qualifier_field"])})
    client.log_batch(run["run_id"], params, m)
    for name in ("test_b_predictions.csv", "test_c_stage_probabilities.csv", "wc2027_forecast.csv",
                 "sanity_sheet.md"):
        client.log_artifact(run, os.path.join(out, name))
    client.end_run(run["run_id"])
    return {"run_id": run["run_id"], "experiment_id": run["experiment_id"]}
