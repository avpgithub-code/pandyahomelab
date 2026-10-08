"""CLI contract: one JSON line on stdout; exit 0 ok, 2 when a data check fails."""
import json

from db_logic.repository import supplement_store as store
from presentation_logic.cli.main import main
from tests.conftest import make_serving_db, supp_row, totals_for


def _run(capsys, *argv):
    code = main(list(argv) + ["--quiet"])
    return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_data_check_exit_codes(cfg, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("CRICSTAT_TOURNAMENTS_DIR", str(tmp_path / "none"))
    (tmp_path / "none").mkdir()
    make_serving_db(cfg.SERVING_DB, [("100", "2018-01-10", "India", "Australia", "India", "win",
                                      "India")])
    rows = [supp_row()]
    store.write_results(cfg.SUPPLEMENT_DIR, rows)
    store.write_totals(cfg.SUPPLEMENT_DIR, totals_for(rows))
    code, out = _run(capsys, "data-check")
    assert (code, out["status"], out["matches"]) == (0, "ok", 2)

    store.write_results(cfg.SUPPLEMENT_DIR, [supp_row(check_status="differs")])
    code, out = _run(capsys, "data-check")
    assert (code, out["status"]) == (2, "check_failed")
