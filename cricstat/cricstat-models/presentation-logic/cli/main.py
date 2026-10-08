"""cricstat-models CLI (P1.1: the data layer; ratings, simulation and forecasts come in P1.2–P1.4).

    python3 -m presentation_logic.cli data-check            # rating input + tournaments: all checks
    python3 -m presentation_logic.cli supplement-check      # weekly: propose Afghanistan changes
    python3 -m presentation_logic.cli supplement-draft --out DIR    # rebuild the draft (review)
    python3 -m presentation_logic.cli tournament-draft wc2027       # refresh the 2027 fixtures
    python3 -m presentation_logic.cli backtest [--no-mlflow]        # P1.2: tune Elo + backtest A
    python3 -m presentation_logic.cli forecast [--force]     # daily: champion → forecast.sqlite
    python3 -m presentation_logic.cli train [--owner-approved]   # weekly/manual: backtest + promote
    python3 -m presentation_logic.cli selftest               # cd-pull smoke test: checks, no writes
    python3 -m presentation_logic.cli tournament-backtest [--no-mlflow] [--sims N]
                                         # P1.3: tests A, B, C, replay, gates 1-4, 2027 forecast

stdout gets exactly one JSON line (the run summary); the human log goes to
CRICSTAT_LOG_DIR/models-YYYYMMDD.log and stderr.
Exit codes: 0 success, 1 runtime error, 2 data check failed (nothing downstream runs),
3 supplement-check found something to review (new/changed Afghanistan rows or issues): DSM emails
the run output, which is the proposal.
supplement-check never edits the committed files: a proposal becomes live only through a reviewed
commit and a models-image publish (Wikipedia can be edited by anyone).
"""
import argparse
import json
import sys
import time

from application_logic.services import (
    backtest_service,
    data_service,
    forecast_service,
    supplement_service,
    tournament_backtest_service,
    tournament_service,
)
from db_logic.repository import serving_reader, tournament_store
from shared.config import get_config
from shared.exceptions import DataCheckError
from shared.logger import get_logger, setup_logging

EXIT_OK, EXIT_ERROR, EXIT_CHECK, EXIT_REVIEW = 0, 1, 2, 3
MODES = ("data-check", "supplement-check", "supplement-draft", "tournament-draft", "backtest",
         "tournament-backtest", "train", "forecast", "selftest")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cricstat-models",
                                description="ODI World Cup 2027 predictor jobs.")
    p.add_argument("mode", choices=MODES)
    p.add_argument("tournament", nargs="?", help="tournament-draft: only wc2027 is drafted")
    p.add_argument("--out", help="supplement-draft: folder to write into (default: a review"
                                 " folder under CRICSTAT_DATA_DIR/models, never the committed"
                                 " files)")
    p.add_argument("--sims", type=int, help="tournament-backtest: simulations for the 2027"
                                            " forecast (default 50,000)")
    p.add_argument("--force", action="store_true", help="forecast: even if nothing changed")
    p.add_argument("--owner-approved", action="store_true",
                   help="train: the owner checked the sanity sheet (needed for the first champion)")
    p.add_argument("--no-mlflow", action="store_true", help="backtest: don't log to MLflow")
    p.add_argument("--quiet", action="store_true", help="only warnings and errors on stderr")
    return p


def data_check(cfg) -> dict:
    rows, report = data_service.load_matches(cfg)
    with serving_reader.connect(cfg.SERVING_DB) as conn:
        teams = serving_reader.men_international_teams(conn)
    report["tournaments"] = {}
    for tid in tournament_store.tournament_ids(cfg.TOURNAMENTS_DIR):
        fmt = tournament_store.read_format(cfg.TOURNAMENTS_DIR, tid)
        if fmt.get("status") == "field_tbc":
            report["tournaments"][tid] = "field to be confirmed (no fixtures yet)"
            continue
        _, fixtures = tournament_service.load(cfg, tid, teams)
        report["tournaments"][tid] = "%d fixtures ok" % len(fixtures)
    return report


def _headline(rep: dict) -> dict:
    t = rep["test_a"]
    pick = ("n", "log_loss", "brier", "accuracy", "calibration_slope")
    return {"elo": {k: t["elo"][k] for k in pick},
            "win_rate": {k: t["baselines"]["win_rate"][k] for k in pick},
            "coin": {k: t["baselines"]["coin"][k] for k in pick[:3]}}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = get_config(reload=True)
    t0 = time.time()
    try:
        log_path = setup_logging(cfg.LOG_DIR, cfg.LOG_LEVEL, args.quiet, "models")
    except OSError as exc:
        print(json.dumps({"mode": args.mode, "status": "error", "error": "log dir: %s" % exc}),
              flush=True)
        return EXIT_ERROR
    log = get_logger("cli")
    log.info("start %s (serving=%s, log=%s)", args.mode, cfg.SERVING_DB, log_path)
    summary = {"mode": args.mode}
    try:
        if args.mode == "data-check":
            summary.update(data_check(cfg))
        elif args.mode == "supplement-check":
            summary.update(supplement_service.propose(cfg))
        elif args.mode == "supplement-draft":
            out = args.out or "%s/models/supplement-draft" % cfg.DATA_DIR
            summary.update(supplement_service.draft(cfg, out_dir=out))
        elif args.mode == "backtest":
            rep = backtest_service.run(cfg, log_to_mlflow=not args.no_mlflow)
            summary.update(test_a=_headline(rep), gates=rep["gates"], report_dir=rep["report_dir"],
                           mlflow=rep.get("mlflow"),
                           params={k: v["params"] for k, v in rep["windows"].items()})
        elif args.mode == "forecast":
            summary.update(forecast_service.forecast(cfg, force=args.force, n=args.sims))
        elif args.mode == "train":
            summary.update(forecast_service.train(cfg, owner_approved=args.owner_approved))
        elif args.mode == "selftest":
            summary.update(forecast_service.selftest(cfg))
        elif args.mode == "tournament-backtest":
            kw = {"n_forecast": args.sims} if args.sims else {}
            rep = tournament_backtest_service.run(cfg, log_to_mlflow=not args.no_mlflow, **kw)
            summary.update(gates=rep["gates"], report_dir=rep["report_dir"],
                           mlflow=rep.get("mlflow"),
                           test_b={k: {m: round(v[m], 4) for m in ("n", "log_loss", "brier")}
                                   for k, v in rep["test_b_pooled"].items()},
                           wc2027_top=[(r["team"], round(r["p_champion"], 3))
                                       for r in rep["forecast"]["table"][:10]])
        elif args.mode == "tournament-draft":
            if args.tournament != "wc2027":
                raise ValueError("only wc2027 is drafted from its schedule; past World Cups"
                                 " are fixed")
            d = tournament_service.draft_2027(cfg)
            tournament_store.write_fixtures(cfg.TOURNAMENTS_DIR, "wc2027", d["fixtures"])
            summary.update(fixtures=len(d["fixtures"]), source_revid=d["revid"])
        summary["status"] = "ok"
        code = EXIT_OK
        if args.mode == "supplement-check" and not (summary.get("up_to_date") and
                                                    not summary.get("issues") and
                                                    not summary.get("totals_errors")):
            summary["status"] = "review_needed"
            code = EXIT_REVIEW
    except DataCheckError as exc:
        log.error("data check failed: %s", exc)
        summary.update(status="check_failed", error=str(exc))
        code = EXIT_CHECK
    except Exception as exc:  # every other failure maps to exit 1
        log.exception("run failed")
        summary.update(status="error", error="%s: %s" % (type(exc).__name__, exc))
        code = EXIT_ERROR
    summary["duration_s"] = round(time.time() - t0, 1)
    summary["exit_code"] = code
    print(json.dumps(summary, sort_keys=True, default=str), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
