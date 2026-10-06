"""cricstat-pipeline CLI.

    python3 -m presentation_logic.cli full                 # download all_json.zip, ingest
    python3 -m presentation_logic.cli recent               # download recently_added_7, upsert
    python3 -m presentation_logic.cli full --zip-path F    # ingest a local zip, no network
    python3 -m presentation_logic.cli build                # raw → serving DB (incremental)
    python3 -m presentation_logic.cli build --full         # rebuild the serving DB from scratch
    python3 -m presentation_logic.cli register             # Cricsheet Register → raw store

stdout gets exactly one JSON line (the run summary); the human log goes to
CRICSTAT_LOG_DIR/<ingest|build|register>-YYYYMMDD.log and stderr.
Exit codes: 0 success, 1 runtime error, 2 data-quality gate failed (rolled back / old DB kept).
"""
import argparse
import json
import sys
import time

from application_logic.services import build_service, refresh_service, register_service
from shared.config import get_config
from shared.exceptions import DataQualityError
from shared.logger import get_logger, setup_logging

EXIT_OK, EXIT_ERROR, EXIT_DQ = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cricstat-pipeline",
                                description="Ingest Cricsheet data and build the serving DB.")
    p.add_argument("mode", choices=("full", "recent", "build", "register"),
                   help="full: all_json.zip with removal detection; recent: last-7-days upsert; "
                        "build: raw store → serving DB; register: people.csv + names.csv")
    p.add_argument("--zip-path", help="ingest this local zip instead of downloading")
    kind = p.add_mutually_exclusive_group()
    kind.add_argument("--full", dest="build_mode", action="store_const", const="full",
                      help="build: rebuild everything from the raw store")
    kind.add_argument("--incremental", dest="build_mode", action="store_const",
                      const="incremental", help="build: only changed matches (default)")
    p.add_argument("--people-csv", help="register: read this local people.csv")
    p.add_argument("--names-csv", help="register: read this local names.csv")
    p.add_argument("--quiet", action="store_true", help="only warnings and errors on stderr")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = get_config(reload=True)
    t0 = time.time()
    try:
        prefix = args.mode if args.mode in ("build", "register") else "ingest"
        log_path = setup_logging(cfg.LOG_DIR, cfg.LOG_LEVEL, args.quiet, prefix)
    except OSError as exc:
        print(json.dumps({"mode": args.mode, "status": "error",
                          "error": "log dir: %s" % exc}), flush=True)
        return EXIT_ERROR
    log = get_logger("cli")
    log.info("start %s (db=%s, log=%s)", args.mode, cfg.RAW_DB, log_path)
    try:
        if args.mode == "build":
            summary = build_service.run(cfg, args.build_mode or "incremental")
        elif args.mode == "register":
            summary = register_service.run(cfg, args.people_csv, args.names_csv)
        else:
            summary = refresh_service.run(args.mode, cfg, zip_path=args.zip_path)
        code = EXIT_OK
    except DataQualityError as exc:
        summary = getattr(exc, "summary", {"mode": args.mode, "status": "dq_failed"})
        summary["gate_failures"] = exc.failures
        code = EXIT_DQ
    except Exception as exc:  # every other failure maps to exit 1
        log.exception("run failed")
        summary = getattr(exc, "summary", None) or {"mode": args.mode, "status": "error"}
        summary["error"] = "%s: %s" % (type(exc).__name__, exc)
        code = EXIT_ERROR
    # duration_s = ingest transaction only; total_duration_s includes the download.
    summary.setdefault("duration_s", round(time.time() - t0, 1))
    summary["total_duration_s"] = round(time.time() - t0, 1)
    summary["exit_code"] = code
    print(json.dumps(summary, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
