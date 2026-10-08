"""The scheduled predictor jobs (P1 plan §4).

    train     (weekly / manual) the full backtest (tests A, B, C, replay, 2027 table) → a candidate.
              It becomes the MLflow alias `champion` of cricstat-wc2027-predictor only if gates 1–4
              pass and it doesn't regress against the current champion (test A log loss + 0.002,
              test B log loss + 0.005). The very first champion also needs the owner's OK
              (--owner-approved), which is publish gate 5.
    forecast  (daily, after the build) ratings with the champion's parameters, 50,000 simulated
              tournaments, written to data/db/forecast.sqlite (atomic swap after checks) and logged
              to MLflow cricstat-wc2027-forecast. Skipped when nothing changed: same rating input,
              same champion, same fixtures (the fingerprint).
    selftest  (cd-pull smoke test on the NAS) every check, no writes.
Results already played in a tournament are read from the rating input by match_id (the fixtures
carry the scorecard ids), so the forecast follows the 2027 World Cup as it happens.
"""
import datetime
import hashlib
import json
import os
from typing import Dict, List, Optional

from application_logic.models import elo, simulator, uncertainty
from application_logic.services import (
    backtest_service,
    data_service,
    tournament_backtest_service,
    tournament_service,
)
from db_logic.repository import forecast_store, serving_reader
from db_logic.repository import tournament_store as tstore
from db_logic.tracking.mlflow_rest import MlflowClient, MlflowError
from shared.exceptions import DataCheckError, ModelsError
from shared.logger import get_logger

log = get_logger("forecast")

MODEL_NAME = "cricstat-wc2027-predictor"
FORECAST_EXPERIMENT = "cricstat-wc2027-forecast"
TOURNAMENT = "wc2027"
TOLERANCE = {"test_a.log_loss": 0.002, "test_b.log_loss": 0.005}
EXPECT = {"super_series": 3, "group": 12, "super7": 7, "semi": 4, "final": 2, "champion": 1}


# -- champion --------------------------------------------------------------------------------------
def load_champion(cfg, client: Optional[MlflowClient] = None) -> Dict[str, object]:
    """The champion's frozen settings: from MLflow (alias), else the copy cached in
    forecast.sqlite when MLflow is down (the forecast must not depend on the tracker)."""
    client = client or MlflowClient(cfg.MLFLOW_URI)
    try:
        alias = client.get_alias(MODEL_NAME, "champion")
        if alias:
            info = client.run_info(alias["run_id"])
            model = json.loads(client.download_artifact(info["experiment_id"], info["run_id"],
                                                        "candidate.json"))
            model.update(model_version="elo-v%s" % alias["version"],
                         registered_version=alias["version"], mlflow_run_id=info["run_id"])
            return model
    except MlflowError as exc:
        log.warning("MLflow unavailable, using the cached champion: %s", exc)
    cached = _cached_champion(cfg)
    if cached:
        return cached
    raise ModelsError("no champion model yet: run `train --owner-approved` once")


def _cached_champion(cfg) -> Optional[Dict[str, object]]:
    last = forecast_store.last_forecast(cfg.FORECAST_DB, TOURNAMENT)
    if not last:
        return None
    params = forecast_store.model_params(cfg.FORECAST_DB, last["model_version"])
    if params:
        params.update(model_version=last["model_version"])
    return params


def promotion_decision(candidate: Dict[str, object], champion: Optional[Dict[str, object]],
                       owner_approved: bool) -> Dict[str, object]:
    reasons = []
    if not all(candidate["gates"].get(k) for k in ("test_a_passes", "gate3_test_b_not_worse",
                                                   "gate4_replay_and_sums")):
        reasons.append("publish gates 1-4 not all passed: %s" % candidate["gates"])
    if champion is None:
        if not owner_approved:
            reasons.append("first champion needs the owner's sanity check (--owner-approved)")
    else:
        for k, tol in TOLERANCE.items():
            new, old = candidate["metrics"][k], champion["metrics"][k]
            if new > old + tol:
                reasons.append("%s regressed: %.4f vs champion %.4f (+%.3f allowed)"
                               % (k, new, old, tol))
    return {"promote": not reasons, "reasons": reasons}


def train(cfg, owner_approved: bool = False) -> Dict[str, object]:
    rep = tournament_backtest_service.run(cfg, log_to_mlflow=True)
    cand = rep["candidate"]
    client = MlflowClient(cfg.MLFLOW_URI)
    try:
        champion = load_champion(cfg, client)
    except ModelsError:
        champion = None
    decision = promotion_decision(cand, champion, owner_approved)
    out = {"report_dir": rep["report_dir"], "candidate_run": rep.get("mlflow"),
           "decision": decision, "metrics": cand["metrics"],
           "previous_champion": champion and champion.get("model_version")}
    if not decision["promote"]:
        log.warning("candidate not promoted: %s", "; ".join(decision["reasons"]))
        return out
    run_id = rep["mlflow"]["run_id"]
    client.ensure_registered_model(MODEL_NAME, "ODI World Cup 2027 predictor (cricstat). The "
                                   "'champion' alias powers the live forecast.")
    info = client.run_info(run_id)
    version = client.create_model_version(MODEL_NAME, info, {
        "family": cand["family"], "data_as_of": cand["data_as_of"],
        "test_a_log_loss": round(cand["metrics"]["test_a.log_loss"], 5),
        "test_b_log_loss": round(cand["metrics"]["test_b.log_loss"], 5)})
    client.set_alias(MODEL_NAME, "champion", version)
    log.info("promoted %s version %s (run %s)", MODEL_NAME, version, run_id)
    out["promoted_version"] = version
    out["forecast"] = forecast(cfg, force=True)
    return out


# -- forecast --------------------------------------------------------------------------------------
def _fingerprint(rows, model, fixtures, field) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update(("%s|%s|%s|%s|%s|%s\n" % (r["match_key"], r["start_date"], r["team1"], r["team2"],
                                           r["result"], r["winner"])).encode())
    h.update(json.dumps({k: model.get(k) for k in ("model_version", "elo", "sigma_a",
                                                   "conditions", "n_simulations")},
                        sort_keys=True).encode())
    h.update(json.dumps(fixtures, sort_keys=True).encode())
    h.update(json.dumps(field).encode())
    return h.hexdigest()[:16]


def overlay_results(fixtures: List[Dict[str, str]], rows: List[Dict[str, object]]) -> int:
    """Fill in a fixture's actual result from the rating input once its scorecard id is played."""
    played = {str(r["match_key"]): r for r in rows}
    n = 0
    for f in fixtures:
        r = played.get(f.get("match_key") or "")
        if r and not f.get("result"):
            f.update(team1=r["team1"], team2=r["team2"], result=r["result"],
                     winner=r["winner"] or "", has_play=str(r["has_play"]))
            n += 1
    return n


def forecast(cfg, force: bool = False, n: Optional[int] = None) -> Dict[str, object]:
    model = load_champion(cfg)
    rows, data_rep = data_service.load_matches(cfg)
    with serving_reader.connect(cfg.SERVING_DB) as conn:
        known = serving_reader.men_international_teams(conn) | {"Afghanistan"}
    fmt, fixtures = tournament_service.load(cfg, TOURNAMENT, known)
    played = overlay_results(fixtures, rows)
    field = tstore.read_format(cfg.TOURNAMENTS_DIR, "wcq2027").get("simulation_field") or []
    fp = _fingerprint(rows, model, fixtures, field)
    last = forecast_store.last_forecast(cfg.FORECAST_DB, TOURNAMENT)
    if last and last["fingerprint"] == fp and not force:
        return {"result": "unchanged", "forecast_id": last["forecast_id"], "fingerprint": fp}

    fm = backtest_service.full_members(cfg.FULL_MEMBERS)
    c = elo.compile_matches(rows, fm)
    p = elo.EloParams(**{k: model["elo"][k] for k in elo.EloParams._fields})
    _, rating_list, hist = elo.run(c, p, keep_history=True)
    ratings = dict(zip(c.teams, rating_list))
    data_as_of = data_rep["data_as_of"]
    days = max((datetime.date.fromisoformat(fmt["start"]) -
                datetime.date.fromisoformat(data_as_of)).days, 0)
    sig = uncertainty.sigma(model["sigma_a"], days)
    cond = model["conditions"]
    sp = simulator.SimParams(home=p.home, k_update=p.k, sigma=sig, nr=cond["by_country"],
                             nr_default=cond["global"], tie=cond["tie"])

    def draw(rng, noisy):
        order = simulator.round_robin_order(field, noisy, sp, rng)
        return {"Q%d" % (i + 1): t for i, t in enumerate(order[:4])}

    n = n or int(model.get("n_simulations", tournament_backtest_service.N_FORECAST))
    res = simulator.simulate(simulator.Tournament(fmt, fixtures), ratings, sp, n,
                             int(model.get("seed", tournament_backtest_service.SEED)),
                             slot_draw=draw if field else None)
    teams = sorted(set(fmt["teams"]) | set(field))
    probs = {}
    for t in teams:
        cnt = res.stage_counts.get(t, {})
        st = {s: cnt.get(s, 0) / n for s in forecast_store.STAGES if s != "champion"}
        if t not in field:
            st.pop("qualified", None)
        st["champion"] = res.champion.get(t, 0) / n
        probs[t] = st
    created = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    since = last["data_as_of"] if last else data_as_of
    new_inputs = [r for r in rows if r["start_date"] > since] if last else []

    run_id = _log_forecast(cfg, model, data_rep, probs, n, sig, days, fp)
    with forecast_store.ForecastWriter(cfg.FORECAST_DB) as w:
        uids = w.teams({r["team1"] for r in rows} | {r["team2"] for r in rows} | set(teams),
                       known - {"Afghanistan"})          # Afghanistan has no serving team row
        w.model_version(model["model_version"], {k: v for k, v in model.items()
                                                 if k not in ("reliability_test_a",)},
                        model.get("registered_version"), model.get("mlflow_run_id"),
                        model.get("trained_at"))
        w.ratings(model["model_version"],
                  ((uids[c.teams[t]], d, key, r) for key, d, t, r in hist))
        fid = w.forecast({"tournament": TOURNAMENT, "created_at": created, "data_as_of": data_as_of,
                          "build_id": data_rep.get("build_id"), "fingerprint": fp,
                          "n_simulations": n, "model_version": model["model_version"],
                          "mlflow_run_id": run_id, "days_to_start": days, "sigma": sig,
                          "notes": json.dumps({"played_fixtures": played,
                                               "qualifier_field": field})},
                         {uids[t]: v for t, v in probs.items()},
                         [{"match_id": str(r["match_key"]), "start_date": r["start_date"],
                           "team1_uid": uids[r["team1"]], "team2_uid": uids[r["team2"]],
                           "result": r["result"], "winner_uid": uids.get(r["winner"] or ""),
                           "source": r["source"]} for r in new_inputs])
        _store_backtest(w, model)
        expect = dict(EXPECT, **({"qualified": 4} if field else {}))
        errors = w.check(fid, expect)
        if errors:
            raise DataCheckError("forecast checks failed, live forecast kept: %s"
                                 % "; ".join(errors))
        w.commit()
    top = sorted(probs.items(), key=lambda kv: -kv[1]["champion"])[:6]
    return {"result": "written", "forecast_id": fid, "fingerprint": fp, "data_as_of": data_as_of,
            "model_version": model["model_version"], "n_simulations": n, "days_to_start": days,
            "sigma": round(sig, 1), "played_fixtures": played, "new_matches": len(new_inputs),
            "mlflow_run_id": run_id,
            "top": [(t, round(v["champion"], 3)) for t, v in top]}


def _store_backtest(w, model) -> None:
    rows = [("summary", "elo" if "win_rate" not in k else "win_rate", k.replace(".win_rate", ""), v)
            for k, v in model.get("metrics", {}).items()]
    bins = [("test_a", "elo", b["bin"], b["n"], b["predicted"], b["observed"])
            for b in model.get("reliability_test_a", [])]
    w.backtest(model["model_version"], rows, bins)


def _log_forecast(cfg, model, data_rep, probs, n, sig, days, fp) -> Optional[str]:
    client = MlflowClient(cfg.MLFLOW_URI)
    try:
        run = client.start_run(FORECAST_EXPERIMENT, "forecast-%s" % data_rep["data_as_of"], {
            "cricstat.model_version": model["model_version"],
            "cricstat.data_as_of": data_rep["data_as_of"],
            "cricstat.build_id": data_rep.get("build_id"), "cricstat.fingerprint": fp})
        client.log_batch(run["run_id"],
                         {"model_version": model["model_version"], "n_simulations": n,
                          "days_to_start": days, "sigma": round(sig, 2),
                          "champion_run": model.get("mlflow_run_id")},
                         {"p_champion.%s" % t.replace(" ", "_"): v["champion"]
                          for t, v in probs.items() if v["champion"] > 0})
        client.end_run(run["run_id"])
        return run["run_id"]
    except MlflowError as exc:
        log.warning("forecast not logged to MLflow: %s", exc)
        return None


def selftest(cfg) -> Dict[str, object]:
    """No writes: the rating input and every tournament config pass their checks, the forecast file
    (if any) opens, and the champion is reachable or cached. Used by cd-pull's NAS smoke test."""
    rows, rep = data_service.load_matches(cfg)
    with serving_reader.connect(cfg.SERVING_DB) as conn:
        known = serving_reader.men_international_teams(conn) | {"Afghanistan"}
    for tid in tstore.tournament_ids(cfg.TOURNAMENTS_DIR):
        if tstore.read_format(cfg.TOURNAMENTS_DIR, tid).get("status") != "field_tbc":
            tournament_service.load(cfg, tid, known)
    last = forecast_store.last_forecast(cfg.FORECAST_DB, TOURNAMENT)
    try:
        champion = load_champion(cfg).get("model_version")
    except ModelsError as exc:
        champion = "none (%s)" % exc
    return {"matches": rep["matches"], "data_as_of": rep["data_as_of"],
            "last_forecast": last and last["forecast_id"], "champion": champion,
            "forecast_db": os.path.exists(cfg.FORECAST_DB)}
