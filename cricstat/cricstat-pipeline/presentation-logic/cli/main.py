"""cricstat-pipeline CLI.

    python3 -m presentation_logic.cli full                 # download all_json.zip, ingest
    python3 -m presentation_logic.cli recent               # download recently_added_7, upsert
    python3 -m presentation_logic.cli full --zip-path F    # ingest a local zip, no network

stdout gets exactly one JSON line (the run summary); the human log goes to
CRICSTAT_LOG_DIR/ingest-YYYYMMDD.log and stderr.
Exit codes: 0 success, 1 runtime error, 2 data-quality gate failed (rolled back).
"""
import argparse
import json
import sys
import time

from application_logic.services import refresh_service
from shared.config import get_config
from shared.exceptions import DataQualityError
from shared.logger import get_logger, setup_logging

EXIT_OK, EXIT_ERROR, EXIT_DQ = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cricstat-pipeline",
                                description="Ingest Cricsheet JSON zips into the raw SQLite store.")
    p.add_argument("mode", choices=("full", "recent"),
                   help="full: all_json.zip with removal detection; recent: last-7-days upsert")
    p.add_argument("--zip-path", help="ingest this local zip instead of downloading")
    p.add_argument("--quiet", action="store_true", help="only warnings and errors on stderr")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = get_config(reload=True)
    t0 = time.time()
    try:
        log_path = setup_logging(cfg.LOG_DIR, cfg.LOG_LEVEL, args.quiet)
    except OSError as exc:
        print(json.dumps({"mode": args.mode, "status": "error",
                          "error": "log dir: %s" % exc}), flush=True)
        return EXIT_ERROR
    log = get_logger("cli")
    log.info("start %s (db=%s, log=%s)", args.mode, cfg.RAW_DB, log_path)
    try:
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
